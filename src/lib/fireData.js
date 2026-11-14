/**
 * Network side of the fire page. Every service here is free, needs no key and
 * answers browsers directly (CORS open), so the page works on GitHub Pages:
 *
 *   CWFIS (Natural Resources Canada) WFS  hotspots (NASA MODIS / VIIRS),
 *                                          burned areas (NBAC), current fire
 *                                          perimeters, today's fire danger
 *   Microsoft Planetary Computer          NASA HLS images (Landsat 8/9 and
 *                                          Sentinel-2, since 2020): STAC search
 *                                          + per-polygon statistics (NBR)
 *   AAFC Annual Crop Inventory (ArcGIS)   crop class per year since 2009
 *   ISRIC SoilGrids                        texture and organic carbon
 *
 * Results are normalised with the pure helpers of src/lib/wildfire.js.
 */
import { ACI_FIRST_YEAR, ACI_LAST_YEAR } from '../data/cropInventory.js';
import { bounds, center, isClosed } from './geo.js';
import {
  buildEvents,
  classifyDnbr,
  clearFraction,
  cropHistory,
  dangerOf,
  farmBox,
  farmCenter,
  medianFromStats,
  nbrExpression,
  normalizeBurns,
  normalizeHotspots,
  normalizePerimeters,
  samplePoints,
  searchBbox,
  soilFromSoilGrids,
} from './wildfire.js';

const CWFIS = 'https://cwfis.cfs.nrcan.gc.ca/geoserver/public/wfs';
const ACI = 'https://www.agr.gc.ca/imagery-images/rest/services/annual_crop_inventory';
const SOILGRIDS = 'https://rest.isric.org/soilgrids/v2.0/properties/query';
const PC = 'https://planetarycomputer.microsoft.com/api';

/** HLS v2 on the Planetary Computer starts on 2020-01-01. */
export const HLS_FIRST_DAY = '2020-01-15';
const MAX_HOTSPOTS = 2000;

const timeout = (ms) =>
  typeof AbortSignal !== 'undefined' && AbortSignal.timeout ? AbortSignal.timeout(ms) : undefined;

async function getJson(url, label, { ms = 40_000, ...init } = {}) {
  let res;
  try {
    res = await fetch(url, { signal: timeout(ms), ...init });
  } catch {
    throw new Error(`${label} ne répond pas`);
  }
  if (!res.ok) throw new Error(`${label} indisponible (${res.status})`);
  return res.json();
}

/* ---------- CWFIS: what burns or burned around the farm ---------- */

function wfs(typeName, params) {
  const url = new URL(CWFIS);
  const all = {
    service: 'WFS',
    version: '1.0.0',
    request: 'GetFeature',
    outputFormat: 'application/json',
    srsName: 'EPSG:4326',
    typeName,
    ...params,
  };
  for (const [k, v] of Object.entries(all)) url.searchParams.set(k, String(v));
  return url;
}

/**
 * Fire events within `radiusKm` of the farm over the last `years` years, and
 * today's fire danger at the farm. One failing layer does not sink the others.
 */
export async function fetchFireContext(subject, { radiusKm, years, now = new Date() }) {
  const box = farmBox(subject);
  if (!box) throw new Error('Placez la ferme sur la carte pour chercher les feux autour.');
  const [minLon, minLat, maxLon, maxLat] = searchBbox(box, radiusKm);
  const bbox = (geom) => `BBOX(${geom},${minLon},${minLat},${maxLon},${maxLat},'EPSG:4326')`;
  const since = new Date(now);
  since.setUTCFullYear(since.getUTCFullYear() - years);
  const [lat, lon] = farmCenter(subject);

  const [hs, nbac, m3, fdr] = await Promise.allSettled([
    getJson(
      wfs('public:hotspots', {
        maxFeatures: MAX_HOTSPOTS,
        sortBy: 'rep_date D',
        propertyName: 'rep_date,sensor,satellite,frp,fuel,geometry',
        CQL_FILTER: `${bbox('geometry')} AND rep_date > '${since.toISOString().slice(0, 19)}Z'`,
      }),
      'Les points chauds',
    ),
    getJson(
      wfs('public:nbac', {
        maxFeatures: 300,
        propertyName: 'year,adj_ha,firecaus,hs_sdate,hs_edate,ag_sdate,ag_edate,geometry',
        CQL_FILTER: `${bbox('geometry')} AND year >= ${since.getUTCFullYear()}`,
      }),
      'La carte des zones brûlées',
    ),
    getJson(
      wfs('public:m3_polygons_current', {
        maxFeatures: 100,
        propertyName: 'firstdate,lastdate,area,geometry',
        CQL_FILTER: bbox('geometry'),
      }),
      'Les feux de la saison',
    ),
    getJson(
      wfs('public:fdr_current_shp', {
        propertyName: 'GRIDCODE',
        CQL_FILTER: `INTERSECTS(the_geom, SRID=4326;POINT(${lon} ${lat}))`,
      }),
      'Le danger d’incendie',
    ),
  ]);

  if (hs.status === 'rejected' && nbac.status === 'rejected') throw hs.reason;
  const hotspots = hs.status === 'fulfilled' ? normalizeHotspots(hs.value) : [];
  const burns = nbac.status === 'fulfilled' ? normalizeBurns(nbac.value) : [];
  const perimeters = m3.status === 'fulfilled' ? normalizePerimeters(m3.value) : [];
  const code = fdr.status === 'fulfilled' ? fdr.value.features?.[0]?.properties?.GRIDCODE : null;
  const warnings = [hs, nbac, m3, fdr]
    .filter((r) => r.status === 'rejected')
    .map((r) => r.reason.message);

  return {
    // The query box is a square: keep only what lies within the radius.
    events: buildEvents({ hotspots, burns, perimeters }, subject, now.getTime()).filter(
      (e) => e.km <= radiusKm,
    ),
    hotspotCount: hotspots.length,
    hotspotsCapped: hotspots.length >= MAX_HOTSPOTS,
    danger: dangerOf(code),
    warnings,
    fetchedAt: Date.now(),
  };
}

/* ---------- AAFC: what grew on each section, year by year ---------- */

/** Crop class per section and per year, from 5 sampled points per section. */
export async function fetchCropHistory(
  sections,
  { from = ACI_FIRST_YEAR, to = ACI_LAST_YEAR } = {},
) {
  const points = [];
  const owners = [];
  for (const s of sections) {
    for (const [lat, lon] of samplePoints(s.polygon)) {
      points.push([Math.round(lon * 1e5) / 1e5, Math.round(lat * 1e5) / 1e5]);
      owners.push(s.id);
    }
  }
  if (!points.length) return {};
  const geometry = JSON.stringify({ points, spatialReference: { wkid: 4326 } });
  const years = Array.from({ length: to - from + 1 }, (_, i) => from + i);
  const results = await Promise.all(
    years.map(async (y) => {
      const url = new URL(`${ACI}/${y}/ImageServer/getSamples`);
      url.searchParams.set('geometry', geometry);
      url.searchParams.set('geometryType', 'esriGeometryMultipoint');
      url.searchParams.set('returnFirstValueOnly', 'true');
      url.searchParams.set('f', 'json');
      try {
        const json = await getJson(url, 'L’inventaire des cultures', { ms: 30_000 });
        const values = [...(json.samples ?? [])]
          .sort((a, b) => a.locationId - b.locationId)
          .map((s) => s.value);
        return [y, values.length === points.length ? values : null];
      } catch {
        return [y, null];
      }
    }),
  );
  return cropHistory(results, owners);
}

/* ---------- SoilGrids: how fragile the soil is ---------- */

const soilCache = new Map();

/** SoilGrids is slow and sometimes drops a call: one more try before giving up. */
async function soilAt([lat, lon]) {
  const url = new URL(SOILGRIDS);
  url.searchParams.set('lon', lon.toFixed(4));
  url.searchParams.set('lat', lat.toFixed(4));
  for (const p of ['clay', 'sand', 'silt', 'soc', 'phh2o']) url.searchParams.append('property', p);
  for (const d of ['0-5cm', '5-15cm']) url.searchParams.append('depth', d);
  url.searchParams.set('value', 'mean');
  try {
    return soilFromSoilGrids(await getJson(url, 'SoilGrids', { ms: 45_000 }));
  } catch {
    return soilFromSoilGrids(await getJson(url, 'SoilGrids', { ms: 45_000 }));
  }
}

/**
 * Soil of each section (null where SoilGrids has no data, e.g. built-up land).
 * SoilGrids allows a few calls per minute, so calls go one by one, sections
 * closer than ~1 km share one, and answers are kept for the session. Fails
 * only when no section could be read.
 */
export async function fetchSoils(sections) {
  const out = {};
  let failed = 0;
  let lastError = null;
  for (const s of sections) {
    const c = isClosed(s.polygon) ? center(s.polygon) : null;
    if (!c) continue;
    const key = `${c[0].toFixed(2)},${c[1].toFixed(2)}`;
    if (!soilCache.has(key)) soilCache.set(key, soilAt(c));
    try {
      out[s.id] = await soilCache.get(key);
    } catch (err) {
      soilCache.delete(key);
      out[s.id] = null;
      failed += 1;
      lastError = err;
    }
  }
  if (failed && failed === Object.keys(out).length) throw lastError;
  return out;
}

/* ---------- NASA HLS: did the section burn, and how hard ---------- */

const isoDay = (t) => new Date(t).toISOString().slice(0, 10);
const DAY = 86_400_000;

function boxFeature(polys) {
  const [[minLat, minLon], [maxLat, maxLon]] = bounds(polys);
  return {
    type: 'Feature',
    properties: {},
    geometry: {
      type: 'Polygon',
      coordinates: [
        [
          [minLon, minLat],
          [maxLon, minLat],
          [maxLon, maxLat],
          [minLon, maxLat],
          [minLon, minLat],
        ],
      ],
    },
  };
}

const polygonFeature = (poly) => ({
  type: 'Feature',
  properties: {},
  geometry: { type: 'Polygon', coordinates: [[...poly, poly[0]].map(([lat, lon]) => [lon, lat])] },
});

function statistics(item, params, feature) {
  const url = new URL(`${PC}/data/v1/item/statistics`);
  url.searchParams.set('collection', item.collection);
  url.searchParams.set('item', item.id);
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);
  return getJson(url, 'Les images satellites', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(feature),
    ms: 60_000,
  });
}

/**
 * The HLS image closest to the fire (going back in time for "before", forward
 * for "after") where at least 80 % of the farm is free of cloud, shadow and snow.
 */
async function pickScene(area, from, to, direction) {
  const search = await getJson(`${PC}/stac/v1/search`, 'Le catalogue d’images', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      collections: ['hls2-s30', 'hls2-l30'],
      intersects: area.geometry,
      datetime: `${from}T00:00:00Z/${to}T23:59:59Z`,
      query: { 'eo:cloud_cover': { lt: 50 } },
      sortby: [{ field: 'properties.datetime', direction }],
      limit: 12,
      fields: {
        include: ['id', 'collection', 'properties.datetime', 'properties.eo:cloud_cover'],
        exclude: ['assets', 'links'],
      },
    }),
  });
  for (const item of (search.features ?? []).slice(0, 8)) {
    const st = await statistics(item, { assets: 'Fmask', categorical: 'true' }, area);
    const clear = clearFraction(st?.properties?.statistics?.Fmask_b1?.histogram);
    if (clear >= 0.8) {
      return {
        id: item.id,
        collection: item.collection,
        day: item.properties.datetime.slice(0, 10),
        clear,
      };
    }
  }
  return null;
}

/**
 * dNBR of every traced section for a fire from `day` to `lastDay` (YYYY-MM-DD).
 * "Before" = last clear image in the 120 days before the fire started; for a
 * spring fire (snow until April), else the previous autumn, after harvest.
 * "After" = first clear image in the 45 days after the fire ended, so a long
 * fire is seen whole. `gapDays` between the two images tells how much the crop
 * may have grown or been harvested in between.
 */
export async function measureSeverity(sections, day, { lastDay = day, now = Date.now() } = {}) {
  const traced = sections.filter((s) => isClosed(s.polygon));
  if (!traced.length) throw new Error('Tracez vos sections sur la carte pour mesurer le brûlage.');
  if (!day) throw new Error('La date de ce feu est inconnue.');
  if (day < HLS_FIRST_DAY) {
    throw new Error('Les images HLS commencent en 2020 : la gravité ne se mesure pas pour ce feu.');
  }
  const t = Date.parse(day);
  const end = Math.max(t, Date.parse(lastDay ?? day) || t);
  if (now - end < 2 * DAY) {
    throw new Error(
      'Le feu est trop récent : les images d’après le feu arrivent dans quelques jours.',
    );
  }
  const area = boxFeature(traced.map((s) => s.polygon));
  const year = Number(day.slice(0, 4));
  const spring = Number(day.slice(5, 7)) <= 5;

  const [pre, post] = await Promise.all([
    pickScene(area, isoDay(t - 120 * DAY), isoDay(t - DAY), 'desc').then((s) =>
      s || !spring ? s : pickScene(area, `${year - 1}-09-01`, `${year - 1}-11-20`, 'desc'),
    ),
    pickScene(area, isoDay(end + DAY), isoDay(Math.min(end + 45 * DAY, now)), 'asc'),
  ]);
  if (!pre) throw new Error('Aucune image assez dégagée avant le feu.');
  if (!post) {
    throw new Error(
      now - end < 20 * DAY
        ? 'Les images d’après le feu ne sont pas encore disponibles. Revenez dans quelques jours.'
        : 'Aucune image assez dégagée dans les 45 jours après le feu.',
    );
  }

  const out = {};
  await Promise.all(
    traced.map(async (s) => {
      const f = polygonFeature(s.polygon);
      const [a, b] = await Promise.all(
        [pre, post].map((sc) =>
          statistics(sc, { expression: nbrExpression(sc.collection), asset_as_band: 'true' }, f)
            .then(medianFromStats)
            .catch(() => null),
        ),
      );
      const dnbr = a !== null && b !== null ? Math.round((a - b) * 1000) / 1000 : null;
      out[s.id] = { pre: a, post: b, dnbr, severity: classifyDnbr(dnbr) };
    }),
  );
  const gapDays = Math.round((Date.parse(post.day) - Date.parse(pre.day)) / DAY);
  return { day, lastDay, pre, post, gapDays, sections: out };
}
