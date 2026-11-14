/**
 * Wildfires and the farm: pure helpers (no network), tested in
 * tests/wildfire.test.js. The fetching lives in application/fireData.js
 * (network calls in data/access/fireServices.js).
 *
 * The chain, for one farm:
 *   1. where it burns or burned near the farm: hotspots (NASA MODIS/VIIRS,
 *      served by the Canadian CWFIS) grouped into events, mapped burned areas
 *      (NBAC), today's fire danger;
 *   2. did a section really burn, and how hard: dNBR from NASA HLS images
 *      (Landsat + Sentinel-2) taken just before and just after the fire;
 *   3. how fragile the soil is: texture and organic carbon (SoilGrids);
 *   4. what grew there: AAFC Annual Crop Inventory, year by year;
 *   5. what to change in the rotation (the current rotation of the FarmInput:
 *      `currentCrop`, `currentRotation`, `rotationPosition`, ids of sheets).
 *
 * Polygons in the app are [lat, lon] pairs; GeoJSON from the services is
 * [lon, lat] and is converted at the edges (normalize… functions).
 */
import { CROPS, SHEETS } from '../../data/reference/crops.js';
import { ACI_BURNT, aciClass } from '../../data/reference/cropInventory.js';
import { bounds, center, distanceToBoundsM, isClosed } from './geo.js';

const DAY_MS = 86_400_000;
const KM_PER_DEG = 111.32;
/** Hotspots this close to the farm date the burn of its sections. */
const NEAR_KM = 2;

/* ---------- Geometry ---------- */

/** Great-circle distance in km between two [lat, lon] points. */
export function distanceKm([lat1, lon1], [lat2, lon2]) {
  const r = Math.PI / 180;
  const a =
    Math.sin(((lat2 - lat1) * r) / 2) ** 2 +
    Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin(((lon2 - lon1) * r) / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.min(1, Math.sqrt(a)));
}

/** Ray casting: is the [lat, lon] point inside the polygon (list of [lat, lon])? */
export function pointInPolygon([lat, lon], poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [yi, xi] = poly[i];
    const [yj, xj] = poly[j];
    if (yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

/** The polygons that describe a farm (outline + traced sections). */
export function farmPolygons(subject) {
  return [subject.boundary, ...subject.sections.map((s) => s.polygon)].filter(isClosed);
}

/** Bounding box of the farm, or a point box on its location. */
export function farmBox(subject) {
  const b = bounds(farmPolygons(subject));
  if (b) return b;
  const { lat, lon } = subject.location ?? {};
  return typeof lat === 'number'
    ? [
        [lat, lon],
        [lat, lon],
      ]
    : null;
}

export function farmCenter(subject) {
  const b = farmBox(subject);
  return b ? [(b[0][0] + b[1][0]) / 2, (b[0][1] + b[1][1]) / 2] : null;
}

/** Distance in km from the farm box to a point (0 inside). */
export const kmFromFarm = (box, point) => distanceToBoundsM(box, point) / 1000;

/** Farm box grown by `radiusKm` on every side: [minLon, minLat, maxLon, maxLat]. */
export function searchBbox(box, radiusKm) {
  const [[minLat, minLon], [maxLat, maxLon]] = box;
  const dLat = radiusKm / KM_PER_DEG;
  const dLon = radiusKm / (KM_PER_DEG * Math.cos((((minLat + maxLat) / 2) * Math.PI) / 180));
  const r = (n) => Math.round(n * 1e5) / 1e5;
  return [r(minLon - dLon), r(minLat - dLat), r(maxLon + dLon), r(maxLat + dLat)];
}

/** Points sampled inside a section: its centre and 4 points halfway to the first corners. */
export function samplePoints(poly) {
  if (!isClosed(poly)) return [];
  const c = center(poly);
  return [c, ...poly.slice(0, 4).map((p) => [(c[0] + p[0]) / 2, (c[1] + p[1]) / 2])];
}

/* ---------- Fire danger (CWFIS, today) ---------- */

export const DANGER = [
  { code: 0, label: 'Bas', tone: 'ok' },
  { code: 1, label: 'Modéré', tone: 'info' },
  { code: 2, label: 'Élevé', tone: 'warn' },
  { code: 3, label: 'Très élevé', tone: 'bad' },
  { code: 4, label: 'Extrême', tone: 'bad' },
];
export const dangerOf = (code) =>
  code === null || code === undefined ? null : (DANGER[Number(code)] ?? null);

/* ---------- Hotspots and burned areas ---------- */

/**
 * Fuel types of the Canadian fire behaviour system, in plain words.
 * `vegetation: false` = built-up land, water or bare ground: the heat seen by
 * the satellite is more likely a building, a factory or a flare than a field fire.
 */
export function fuelInfo(fuel) {
  const f = String(fuel ?? '');
  const v = (label, agricultural) => ({ label, agricultural, vegetation: true });
  if (f === 'farm') return v('Terres agricoles', true);
  if (/^O1/.test(f)) return v('Herbes et prairies', true);
  if (f === 'low_veg') return v('Végétation basse', true);
  if (/^C/.test(f)) return v('Forêt de conifères', false);
  if (/^D/.test(f)) return v('Forêt de feuillus', false);
  if (/^M/.test(f)) return v('Forêt mixte', false);
  if (/^S/.test(f)) return v('Débris de coupe', false);
  if (f === 'urban') return { label: 'Milieu urbain', agricultural: false, vegetation: false };
  if (f === 'water') return { label: 'Eau', agricultural: false, vegetation: false };
  if (f === 'non_fuel') return { label: 'Non combustible', agricultural: false, vegetation: false };
  return v('Végétation', false);
}

/** A fire that may have burned vegetation (mapped burns always count). */
export const isVegetationFire = (e) => e.kind !== 'hotspots' || fuelInfo(e.fuel).vegetation;

const dayOf = (iso) => (typeof iso === 'string' && iso.length >= 10 ? iso.slice(0, 10) : null);

/** CWFIS hotspots GeoJSON → [{ id, lat, lon, date, day, sensor, satellite, frp, fuel }]. */
export function normalizeHotspots(geojson) {
  return (geojson?.features ?? [])
    .filter((f) => f.geometry?.coordinates && f.properties?.rep_date)
    .map((f, i) => {
      const [lon, lat] = f.geometry.coordinates;
      const p = f.properties;
      return {
        id: f.id ?? `hs-${i}`,
        lat,
        lon,
        date: p.rep_date,
        day: dayOf(p.rep_date),
        sensor: p.sensor ?? null,
        satellite: p.satellite ?? null,
        frp: typeof p.frp === 'number' ? p.frp : null,
        fuel: p.fuel ?? null,
      };
    });
}

/** Keep at most `max` corners of a ring (every k-th one): enough for a map and a distance. */
export function thinRing(ring, max = 80) {
  if (ring.length <= max) return ring;
  const step = ring.length / max;
  return Array.from({ length: max }, (_, i) => ring[Math.floor(i * step)]);
}

const r5 = (n) => Math.round(n * 1e5) / 1e5;

/**
 * GeoJSON (Multi)Polygon → outer rings as [lat, lon], holes dropped, largest
 * first, at most `maxRings` rings of at most 80 corners (the whole state is
 * copied on every update, so big burned areas are kept light).
 */
export function outerRings(geometry, maxRings = 6) {
  if (!geometry) return [];
  const polys =
    geometry.type === 'MultiPolygon'
      ? geometry.coordinates
      : geometry.type === 'Polygon'
        ? [geometry.coordinates]
        : [];
  return polys
    .map((p) => p[0] ?? [])
    .filter((ring) => ring.length >= 4)
    .sort((a, b) => b.length - a.length)
    .slice(0, maxRings)
    .map((ring) => thinRing(ring).map(([lon, lat]) => [r5(lat), r5(lon)]));
}

/** CWFIS NBAC (mapped burned areas) GeoJSON → [{ id, year, day, ha, cause, rings }]. */
export function normalizeBurns(geojson) {
  return (geojson?.features ?? [])
    .map((f, i) => {
      const p = f.properties ?? {};
      return {
        id: String(f.id ?? `nbac-${i}`),
        year: p.year ?? null,
        day: dayOf(p.hs_sdate) ?? dayOf(p.ag_sdate),
        lastDay: dayOf(p.hs_edate) ?? dayOf(p.ag_edate),
        ha: typeof p.adj_ha === 'number' ? p.adj_ha : null,
        cause: p.firecaus ?? null,
        rings: outerRings(f.geometry),
      };
    })
    .filter((b) => b.rings.length);
}

/** CWFIS current-season fire perimeters GeoJSON → [{ id, first, last, ha, rings }]. */
export function normalizePerimeters(geojson) {
  return (geojson?.features ?? [])
    .map((f, i) => ({
      id: String(f.id ?? `m3-${i}`),
      first: dayOf(f.properties?.firstdate),
      last: dayOf(f.properties?.lastdate),
      ha: typeof f.properties?.area === 'number' ? f.properties.area : null,
      rings: outerRings(f.geometry),
    }))
    .filter((p) => p.rings.length);
}

const CAUSES = { Human: 'humaine', Natural: 'naturelle', Undetermined: 'inconnue' };
export const causeLabel = (c) => CAUSES[c] ?? 'inconnue';

/**
 * Group hotspots that belong to the same fire: within `km` of the group centre
 * and at most `days` after its last detection.
 */
export function clusterHotspots(hotspots, { km = 1.5, days = 3 } = {}) {
  const sorted = [...hotspots].sort((a, b) => a.date.localeCompare(b.date));
  const groups = [];
  for (const h of sorted) {
    const t = Date.parse(h.date);
    const g = groups.find(
      (x) => t - x.lastT <= days * DAY_MS && distanceKm([x.lat, x.lon], [h.lat, h.lon]) <= km,
    );
    if (g) {
      g.points.push(h);
      g.lastT = t;
      g.lat = g.points.reduce((a, p) => a + p.lat, 0) / g.points.length;
      g.lon = g.points.reduce((a, p) => a + p.lon, 0) / g.points.length;
    } else {
      groups.push({ points: [h], lat: h.lat, lon: h.lon, lastT: t });
    }
  }
  return groups;
}

function mostCommon(values) {
  const counts = new Map();
  for (const v of values) counts.set(v, (counts.get(v) ?? 0) + 1);
  return [...counts].sort((a, b) => b[1] - a[1])[0]?.[0] ?? null;
}

/** Ids of the sections hit by a point (inside the polygon). */
const sectionsAt = (sections, point) =>
  sections.filter((s) => isClosed(s.polygon) && pointInPolygon(point, s.polygon)).map((s) => s.id);

/** Ids of the sections whose sample points fall inside one of the rings. */
function sectionsInRings(sections, rings) {
  return sections
    .filter((s) =>
      samplePoints(s.polygon).some((pt) => rings.some((ring) => pointInPolygon(pt, ring))),
    )
    .map((s) => s.id);
}

/** Shortest distance from the farm box to a set of rings (0 when they overlap). */
function kmToRings(box, rings) {
  const farmCorners = [box[0], box[1], [box[0][0], box[1][1]], [box[1][0], box[0][1]]];
  const middle = [(box[0][0] + box[1][0]) / 2, (box[0][1] + box[1][1]) / 2];
  if ([middle, ...farmCorners].some((pt) => rings.some((r) => pointInPolygon(pt, r)))) return 0;
  let best = Infinity;
  for (const r of rings) for (const p of r) best = Math.min(best, kmFromFarm(box, p));
  return best;
}

/**
 * Hotspots + burned areas + current perimeters → one list of fire events,
 * closest first. A hotspot group that falls inside a mapped burned area of the
 * same year is merged into it (and gives it a date when the map has none).
 */
export function buildEvents(
  { hotspots = [], burns = [], perimeters = [] },
  subject,
  now = Date.now(),
) {
  const box = farmBox(subject);
  const sections = subject.sections ?? [];
  const groups = clusterHotspots(hotspots);
  const used = new Set();
  const events = [];

  /** Hotspot groups that fall in `rings` and pass `when`; they are merged into that fire. */
  const absorb = (rings, when) => {
    const pts = [];
    groups.forEach((g, i) => {
      if (used.has(i) || !when(g)) return;
      if (!g.points.some((p) => rings.some((r) => pointInPolygon([p.lat, p.lon], r)))) return;
      used.add(i);
      pts.push(...g.points);
    });
    const days = pts.map((p) => p.day).sort();
    // When the fire was close to the farm (≤ 2 km): the window used to measure the burn.
    const near = pts
      .filter((p) => kmFromFarm(box, [p.lat, p.lon]) <= NEAR_KM)
      .map((p) => p.day)
      .sort();
    return {
      pts,
      first: days[0] ?? null,
      last: days[days.length - 1] ?? null,
      farmDays: near.length ? [near[0], near[near.length - 1]] : null,
    };
  };
  const maxDay = (a, b) => (!a ? b : !b ? a : a > b ? a : b);

  // Season perimeters first: a long fire is one event from its first to its last day.
  for (const p of perimeters) {
    const lo = p.first ? Date.parse(p.first) - 3 * DAY_MS : -Infinity;
    // Perimeters lag behind and fires flare up again: 10 days of slack after the last date.
    const hi = p.last ? Date.parse(p.last) + 10 * DAY_MS : Infinity;
    const h = absorb(p.rings, (g) => g.lastT >= lo && Date.parse(g.points[0].date) <= hi);
    const lastDay = maxDay(p.last, h.last);
    events.push({
      id: `perimeter:${p.id}`,
      kind: 'perimeter',
      day: p.first ?? h.first,
      lastDay,
      year: Number((p.first ?? h.first)?.slice(0, 4)) || null,
      ha: p.ha,
      hotspots: h.pts.length,
      farmDays: h.farmDays,
      fuel: mostCommon(h.pts.map((x) => x.fuel)),
      rings: p.rings,
      km: kmToRings(box, p.rings),
      sections: sectionsInRings(sections, p.rings),
      active: !!lastDay && now - Date.parse(lastDay) <= 7 * DAY_MS,
    });
  }

  for (const b of burns) {
    const h = absorb(b.rings, (g) => Number(g.points[0].day?.slice(0, 4)) === b.year);
    events.push({
      id: `burn:${b.id}`,
      kind: 'burn',
      day: b.day ?? h.first,
      lastDay: maxDay(b.lastDay, h.last),
      year: b.year,
      ha: b.ha,
      cause: b.cause,
      hotspots: h.pts.length,
      farmDays: h.farmDays,
      fuel: mostCommon(h.pts.map((x) => x.fuel)),
      rings: b.rings,
      km: kmToRings(box, b.rings),
      sections: sectionsInRings(sections, b.rings),
    });
  }

  groups.forEach((g, i) => {
    if (used.has(i)) return;
    const first = g.points[0];
    const last = g.points[g.points.length - 1];
    const fuel = mostCommon(g.points.map((p) => p.fuel));
    const frps = g.points.map((p) => p.frp).filter((x) => typeof x === 'number');
    events.push({
      id: `hs:${first.id}`,
      kind: 'hotspots',
      day: first.day,
      lastDay: last.day,
      year: Number(first.day?.slice(0, 4)) || null,
      lat: g.lat,
      lon: g.lon,
      hotspots: g.points.length,
      points: g.points.map((p) => [p.lat, p.lon]),
      frpMax: frps.length ? Math.max(...frps) : null,
      fuel,
      km: Math.min(...g.points.map((p) => kmFromFarm(box, [p.lat, p.lon]))),
      sections: [...new Set(g.points.flatMap((p) => sectionsAt(sections, [p.lat, p.lon])))],
      active: now - Date.parse(last.date) <= 7 * DAY_MS,
    });
  });

  return events.sort(
    (a, b) =>
      b.sections.length - a.sections.length ||
      a.km - b.km ||
      String(b.day ?? '').localeCompare(String(a.day ?? '')),
  );
}

/**
 * Days that frame the burn of the farm: when a long fire came within 2 km
 * of it (from its hotspots), else the whole fire.
 */
export const burnWindow = (e) => e.farmDays ?? [e.day, e.lastDay ?? e.day];

/** Short description of an event for lists and tooltips. */
export function eventTitle(e) {
  if (e.kind === 'burn') return `Zone brûlée ${e.year ?? ''}`.trim();
  if (e.kind === 'perimeter') return 'Feu de la saison';
  return e.hotspots > 1 ? `${e.hotspots} points chauds` : 'Point chaud';
}

/** Summary for the dashboard block and the stat cards. */
export function fireSummary(events, { now = Date.now() } = {}) {
  const yearAgo = now - 365 * DAY_MS;
  const recent = events.filter((e) => e.day && Date.parse(e.day) >= yearAgo);
  return {
    total: events.length,
    recent: recent.length,
    active: events.filter((e) => e.active).length,
    onFarm: events.filter((e) => e.sections.length > 0).length,
    nearest: events.length ? events.reduce((a, b) => (b.km < a.km ? b : a)) : null,
    agricultural: events.filter((e) => fuelInfo(e.fuel).agricultural).length,
  };
}

/* ---------- Recent fires and archives ---------- */

/** Fires last seen more than this many days ago go to the archives. */
export const RECENT_DAYS = 365;

const lastSeen = (e) => e.lastDay ?? e.day;

export const isRecent = (e, now = Date.now()) =>
  !!lastSeen(e) && now - Date.parse(lastSeen(e)) <= RECENT_DAYS * DAY_MS;

/** Events of the last 12 months, and the older ones (archives). Order is kept. */
export function splitByAge(events, now = Date.now()) {
  const recent = [];
  const archived = [];
  for (const e of events) (isRecent(e, now) ? recent : archived).push(e);
  return { recent, archived };
}

/**
 * A fire big enough to warn about: a mapped fire, or a group of 3 hotspots or
 * more, or one strong hotspot. A lone weak hotspot is often a farm burn.
 */
export const isMajorFire = (e) =>
  e.kind !== 'hotspots' || (e.hotspots ?? 0) >= 3 || (e.frpMax ?? 0) >= 20;

/**
 * Is there a risk right now? One line for the farmer, calm by default:
 *   alert  a big vegetation fire burning this week within the radius;
 *   warn   today's fire danger is high or worse;
 *   calm   anything else (a lone weak hotspot is not a risk).
 */
export function fireStatus(events, danger = null) {
  const big = events
    .filter((e) => e.active && isVegetationFire(e) && isMajorFire(e))
    .reduce((a, b) => (!a || b.km < a.km ? b : a), null);
  if (big) {
    return {
      tone: 'alert',
      event: big,
      title: `Feu actif ${fmtKm(big.km)}`,
      text: `Détecté le ${fmtDay(lastSeen(big))}. Suivez les consignes de votre municipalité et de la SOPFEU ou du service des incendies de votre province.`,
    };
  }
  if (danger?.code >= 2) {
    return {
      tone: 'warn',
      event: null,
      title: `Danger d’incendie ${danger.label.toLowerCase()} aujourd’hui`,
      text: 'Reportez tout brûlage de résidus.',
    };
  }
  return { tone: 'calm', event: null, title: 'Aucun risque pour le moment', text: '' };
}

/* ---------- Burn severity (NASA HLS) ---------- */

/** NBR band expression for an HLS collection (narrow NIR and SWIR 2.2 µm). */
export const nbrExpression = (collection) =>
  collection === 'hls2-l30' ? '(B05-B07)/(B05+B07)' : '(B8A-B12)/(B8A+B12)';

export const sensorLabel = (collection) =>
  collection === 'hls2-l30' ? 'Landsat (HLS)' : 'Sentinel-2 (HLS)';

/**
 * Share of clear pixels from a categorical Fmask histogram [[counts], [values]].
 * A pixel is not clear when it is cloud, next to a cloud, shadow or snow
 * (HLS Fmask bits 1 to 4).
 */
export function clearFraction(histogram) {
  const [counts = [], values = []] = histogram ?? [];
  let total = 0;
  let clear = 0;
  counts.forEach((n, i) => {
    total += n;
    if ((Math.round(values[i]) & 0b11110) === 0) clear += n;
  });
  return total ? clear / total : 0;
}

/** Burn severity classes on dNBR (international thresholds, see Sources). */
export const SEVERITY = [
  { id: 'repousse', label: 'Végétation en hausse', max: -0.1, level: 0 },
  { id: 'intact', label: 'Non brûlé', max: 0.1, level: 0 },
  { id: 'faible', label: 'Faible', max: 0.27, level: 1 },
  { id: 'moderee', label: 'Modérée', max: 0.44, level: 2 },
  { id: 'elevee', label: 'Élevée', max: 0.66, level: 3 },
  { id: 'tres-elevee', label: 'Très élevée', max: Infinity, level: 3 },
];

export function classifyDnbr(dnbr) {
  if (typeof dnbr !== 'number' || Number.isNaN(dnbr)) return null;
  return SEVERITY.find((s) => dnbr < s.max) ?? SEVERITY[SEVERITY.length - 1];
}

/** Statistics response of the Planetary Computer data API → median (null when too few pixels). */
export function medianFromStats(json) {
  const stats = json?.properties?.statistics;
  const s = stats ? Object.values(stats)[0] : null;
  if (!s || typeof s.median !== 'number' || (s.valid_percent ?? 100) < 50) return null;
  return s.median;
}

/* ---------- Soil (SoilGrids) ---------- */

/** SoilGrids properties/query response → { clay, sand, silt (%), soc (g/kg), ph } or null. */
export function soilFromSoilGrids(json) {
  const layers = json?.properties?.layers ?? [];
  const get = (name) => {
    const l = layers.find((x) => x.name === name);
    const vals = (l?.depths ?? []).map((d) => d.values?.mean).filter((v) => typeof v === 'number');
    if (!vals.length) return null;
    const mean = vals.reduce((a, v) => a + v, 0) / vals.length;
    return Math.round((mean / (l.unit_measure?.d_factor || 1)) * 10) / 10;
  };
  const soil = {
    clay: get('clay'),
    sand: get('sand'),
    silt: get('silt'),
    soc: get('soc'),
    ph: get('phh2o'),
  };
  return Object.values(soil).every((v) => v === null) ? null : soil;
}

/** Simplified texture class and the kind of erosion it fears once bare. */
export function textureOf(soil) {
  const { clay, sand, silt } = soil ?? {};
  if ([clay, sand, silt].some((v) => typeof v !== 'number')) return null;
  if (sand >= 70) return { id: 'sableux', label: 'Sableux', erosion: 'vent', fragile: true };
  if (clay >= 40)
    return { id: 'argileux', label: 'Argileux', erosion: 'ruissellement', fragile: false };
  if (silt >= 50) return { id: 'limoneux', label: 'Limoneux', erosion: 'eau', fragile: true };
  if (sand >= 50)
    return { id: 'loam-sableux', label: 'Loam sableux', erosion: 'vent', fragile: true };
  return { id: 'loam', label: 'Loam', erosion: 'eau', fragile: false };
}

/* ---------- Crop history (AAFC Annual Crop Inventory) ---------- */

/** Most frequent valid class among sampled values, with its share. Clouds and no-data are ignored. */
export function majorityClass(values) {
  const counts = new Map();
  let n = 0;
  for (const v of values ?? []) {
    const c = aciClass(v);
    if (!c || c.code === 10) continue;
    counts.set(c.code, (counts.get(c.code) ?? 0) + 1);
    n += 1;
  }
  if (!n) return null;
  const [code, k] = [...counts].sort((a, b) => b[1] - a[1])[0];
  return { ...aciClass(code), share: k / n };
}

/**
 * Raw samples per year (one array of values per year, in the order of
 * `owners`, the section id of each sampled point) → for each section, one
 * entry per year: { year, class } (class is null when the year failed).
 */
export function cropHistory(samplesByYear, owners) {
  const ids = [...new Set(owners)];
  const out = Object.fromEntries(ids.map((id) => [id, []]));
  for (const [year, values] of samplesByYear) {
    for (const id of ids) {
      const mine = values ? values.filter((_, i) => owners[i] === id) : null;
      out[id].push({ year: Number(year), class: mine ? majorityClass(mine) : null });
    }
  }
  for (const id of ids) out[id].sort((a, b) => a.year - b.year);
  return out;
}

/** Years where the inventory saw the section as burnt. */
export const burntYears = (history) =>
  (history ?? []).filter((y) => y.class?.code === ACI_BURNT).map((y) => y.year);

/* ---------- Impact and rotation ---------- */

export const IMPACT = [
  { level: 0, label: 'Aucun effet mesuré', tone: 'ok' },
  { level: 1, label: 'Effet faible', tone: 'warn' },
  { level: 2, label: 'Effet modéré', tone: 'bad' },
  { level: 3, label: 'Effet élevé', tone: 'bad' },
];

/**
 * What a fire did to one section and what to do about it.
 * Inputs (all optional): severity (classifyDnbr), burnt (inventory saw it
 * burnt), hotspots (vegetation hotspots on the section), soil, rain7 (mm
 * forecast), nearestKm (closest fire), ageYears (years since the fire).
 *
 * `burnLevel` is what the fire did; `level` is what is left of it today: one
 * level less when the fire is 3 years old or more.
 */
export function assessSection({
  severity,
  burnt,
  hotspots,
  soil,
  rain7,
  nearestKm,
  ageYears,
} = {}) {
  const burnLevel = severity ? severity.level : burnt || hotspots ? 1 : 0;
  const old = typeof ageYears === 'number' && ageYears >= 3 && burnLevel > 0;
  const level = old ? burnLevel - 1 : burnLevel;

  const texture = textureOf(soil);
  const lowCarbon = typeof soil?.soc === 'number' && soil.soc < 15;
  const impacts = [];
  const actions = [];
  const result = (lvl) => ({ ...IMPACT[lvl], burnLevel, impacts, actions, texture });

  if (burnLevel === 0) {
    const near = typeof nearestKm === 'number' && nearestKm <= 10;
    impacts.push(
      near
        ? 'Pas de brûlage mesuré sur la section. Un feu est passé à moins de 10 km : la fumée et les cendres peuvent toucher les cultures sur pied.'
        : 'Pas de brûlage mesuré sur la section.',
    );
    if (near)
      actions.push(
        'Après un épisode de fumée, vérifier les feuilles et les fourrages avant de les récolter.',
      );
    return result(0);
  }

  if (level === 0) {
    impacts.push(
      'La section a brûlé faiblement il y a plus de 3 ans : le sol a eu le temps de se refaire.',
    );
    actions.push(
      'Une analyse de sol de routine suffit pour le confirmer (matière organique, azote).',
    );
    return result(0);
  }

  impacts.push(
    'Les résidus de culture ont brûlé : le sol est à nu et s’érode plus vite, au vent comme à la pluie.',
  );
  impacts.push(
    'Une partie de l’azote et du soufre de surface est partie en fumée. Le phosphore et le potassium restent dans les cendres.',
  );
  if (level >= 2)
    impacts.push(
      'La matière organique de surface a brûlé : le sol retient moins l’eau et sèche plus vite.',
    );
  if (level >= 3)
    impacts.push(
      'Feu intense : la structure du sol et sa vie microbienne sont touchées, l’eau ruisselle au lieu d’entrer.',
    );
  if (texture?.fragile) {
    impacts.push(
      `Sol ${texture.label.toLowerCase()} : très sensible à l’érosion par ${texture.erosion === 'vent' ? 'le vent' : 'l’eau'} une fois à nu.`,
    );
  }
  if (typeof rain7 === 'number' && rain7 >= 20) {
    impacts.push(
      `${Math.round(rain7)} mm de pluie prévus cette semaine sur un sol à nu : risque de ruissellement.`,
    );
  }
  if (old)
    impacts.push(
      'Le feu date de plus de 3 ans : l’effet a diminué, à confirmer par une analyse de sol.',
    );

  actions.push(
    'Semer une culture de couverture dès que possible (seigle d’automne, avoine au printemps) pour tenir le sol.',
  );
  actions.push('Faire analyser le sol avant la prochaine saison : azote, matière organique, pH.');
  actions.push(
    'Travailler le sol le moins possible : les racines et les résidus restants le retiennent.',
  );
  if (level >= 2)
    actions.push('Prévoir une légumineuse l’an prochain pour refaire l’azote (soya, trèfle).');
  if (level >= 2)
    actions.push(
      'Éviter le maïs et la pomme de terre l’an prochain : ils demandent un sol riche et bien structuré.',
    );
  if (level >= 3)
    actions.push('Envisager une luzerne sur 3 ans pour reconstruire la matière organique.');
  if (lowCarbon || level >= 2)
    actions.push('Apporter du fumier ou du compost pour remonter la matière organique.');

  return result(level);
}

/** Crop of a sheet id ('luzerne-3' → 'luzerne') or of a crop id; null when unknown. */
export const cropIdOf = (id) => SHEETS[id]?.cropId ?? (CROPS[id] ? id : null);

/** Legumes: they leave nitrogen for the next crop. */
const LEGUMES = new Set(['soya', 'soya-2e', 'luzerne', 'pois', 'haricot-sec']);
/** Crops that need a rich, well-structured soil. */
const DEMANDING = new Set(['mais', 'pomme-de-terre']);
/** Crops that need a forage harvester (`missingEquipment: ['fourragere']` rules them out). */
const NEEDS_HARVESTER = new Set(['luzerne', 'foin']);
/** Sheets tried in order, per impact level, for the first crop sown after the fire. */
const PREFERRED = { 2: ['soya', 'orge'], 3: ['luzerne-3', 'soya', 'orge'] };

/**
 * Change to the section's current rotation (`currentRotation`, step 1 of the
 * FarmInput) for the crop that follows the one in place, the first one sown
 * after the fire: a legume or a light crop instead of a demanding one (level 2),
 * a legume whatever comes next (level 3). A one-crop rotation gets a second crop.
 * The new crop never follows or precedes the same crop; the algorithm then
 * plans from the new rotation, checks the full return delays and places its
 * own rye covers. `seeds` (getSeeds) only flags a seed the farmer
 * lacks; `missingEquipment` rules out alfalfa without a forage harvester.
 * Returns null when nothing needs to change (level 1: a cover crop is enough,
 * see the actions of assessSection).
 */
export function rotationAdvice(section, level, { seeds = null, missingEquipment = [] } = {}) {
  if (!level || level < 2) return null;
  const rotation = section.currentRotation ?? [];
  const L = rotation.length;
  if (!L) return null;
  const at = Math.min(Math.max(section.rotationPosition ?? 0, 0), L - 1);
  const index = L === 1 ? 1 : (at + 1) % L;
  const from = rotation[index % L];
  const fromCrop = cropIdOf(from);
  const wantSwap = level >= 3 ? !LEGUMES.has(fromCrop) : DEMANDING.has(fromCrop);
  if (!wantSwap) return null;
  // Never the same crop twice in a row: not the crop in place, not the one after.
  const inPlace = cropIdOf(section.currentCrop ?? rotation[at]);
  const after = cropIdOf(rotation[(index + 1) % L]);
  const to = (PREFERRED[Math.min(level, 3)] ?? []).find((id) => {
    const crop = cropIdOf(id);
    if (crop === fromCrop || crop === inPlace || crop === after) return false;
    return !(NEEDS_HARVESTER.has(crop) && missingEquipment.includes('fourragere'));
  });
  if (!to) return null;
  const next = [...rotation];
  next[index] = to;
  const seed = SHEETS[to]?.seedId ?? to;
  return {
    index,
    rotation: next,
    changes: [{ kind: 'crop', from, to }],
    missingSeeds: seeds && !seeds.crops.includes(seed) ? [seed] : [],
  };
}

/* ---------- Active fire nearby: what to do on each section ---------- */

/**
 * Farm season of a date (UTC month, so tests do not depend on the time zone):
 *   semis     April–May      seeding, young crops
 *   pousse    June–July      crops growing, cereals start to dry late July
 *   recolte   August–October ripe crops, harvest, fresh stubble
 *   dormance  November–March stubble and residues
 */
export function fieldSeason(now = Date.now()) {
  const m = new Date(now).getUTCMonth() + 1;
  if (m >= 4 && m <= 5) return 'semis';
  if (m >= 6 && m <= 7) return 'pousse';
  if (m >= 8 && m <= 10) return 'recolte';
  return 'dormance';
}

/**
 * How well what is in the field carries a fire, per crop and season:
 * [level, state in words]. Green crops burn poorly; ripe cereals and their
 * dry stubble carry a grass fire fast.
 */
const CEREAL_FUEL = {
  semis: ['faible', 'jeune et vert'],
  pousse: ['moyen', 'commence à sécher fin juillet'],
  recolte: ['eleve', 'mûr ou en chaume sec'],
  dormance: ['eleve', 'chaume sec'],
};
const SOYA_FUEL = {
  semis: ['faible', 'semé, sol travaillé'],
  pousse: ['faible', 'vert'],
  recolte: ['moyen', 'tiges et gousses sèches'],
  dormance: ['faible', 'peu de résidus'],
};
/** Keys are crop ids of data/reference/crops.js (see cropIdOf for a sheet). */
const FIELD_FUEL = {
  'ble-automne': CEREAL_FUEL,
  orge: CEREAL_FUEL,
  mais: {
    semis: ['faible', 'semé, sol travaillé'],
    pousse: ['faible', 'vert'],
    recolte: ['moyen', 'sèche sur pied'],
    dormance: ['moyen', 'tiges sèches au sol'],
  },
  soya: SOYA_FUEL,
  'soya-2e': SOYA_FUEL,
  'pomme-de-terre': {
    semis: ['faible', 'buttes de terre'],
    pousse: ['faible', 'verte'],
    recolte: ['faible', 'défanée ou récoltée'],
    dormance: ['faible', 'sol nu'],
  },
  luzerne: {
    semis: ['faible', 'repousse verte'],
    pousse: ['faible', 'verte'],
    recolte: ['faible', 'verte entre deux coupes'],
    dormance: ['moyen', 'tiges sèches'],
  },
};

/** { level: 'faible' | 'moyen' | 'eleve', state } for a crop (or sheet) in a season, or null. */
export function fieldFuel(crop, season) {
  const row = FIELD_FUEL[cropIdOf(crop)]?.[season];
  return row ? { level: row[0], state: row[1] } : null;
}

/** Distance in km from a section to a fire (0 when the fire touches it), or null. */
export function sectionKm(section, e) {
  if (!isClosed(section.polygon)) return null;
  if (e.sections?.includes(section.id)) return 0;
  const box = bounds([section.polygon]);
  if (e.rings?.length) return kmToRings(box, e.rings);
  const pts = e.points ?? (typeof e.lat === 'number' ? [[e.lat, e.lon]] : []);
  return pts.length ? Math.min(...pts.map((p) => kmFromFarm(box, p))) : null;
}

/** Winter cover for the sections on the fire side: rye greens up early in spring. */
const FIRE_COVER = 'seigle';

/**
 * Winter cover for a section on the fire side: rye sown after the harvest of
 * the crop in place. Advice only: covers are not part of the current rotation
 * (the algorithm places its rye covers in the plan), so the rotation and its
 * return delays do not change. `seeds` (getSeeds) flags rye missing from the
 * reserve. Null without a known crop in place, or under a crop that holds the
 * field several years (alfalfa, hay) or a fallow.
 */
export function fireCoverAdvice(section, seeds = null) {
  const sheet = section.currentCrop;
  const crop = cropIdOf(sheet);
  if (!crop || crop === FIRE_COVER || crop === 'jachere') return null;
  if ((SHEETS[sheet]?.productionYears ?? 0) > 1 || NEEDS_HARVESTER.has(crop)) return null;
  return {
    crop: sheet,
    changes: [{ kind: 'cover', to: FIRE_COVER }],
    missingSeeds: seeds && !seeds.crops.includes(FIRE_COVER) ? [FIRE_COVER] : [],
  };
}

/** Sections within this distance of the closest one are "on the fire side". */
const FRONT_KM = 0.2;
const CEREALS = new Set(['ble-automne', 'orge']);

/**
 * What to do on each section while a big fire burns within the radius (the
 * `alert` of fireStatus). Sections closest to the fire come first. Sections on
 * the fire side get the field work and a rotation change (fireCoverAdvice);
 * a section the fire already touches is left to the burn measurement.
 *
 * `crop` is what grows now (section.currentCrop, a sheet id), `now` sets the
 * season, `seeds` is the farmer's reserve (getSeeds). Returns { season,
 * sections, general }.
 */
export function alertAdvice(e, sections, { now = Date.now(), seeds = null } = {}) {
  const season = fieldSeason(now);
  // "On fire" follows the event (sample points inside the fire, as everywhere
  // on the page): a section whose corner only grazes the outline is beside it.
  const rows = (sections ?? [])
    .map((s) => ({ s, km: sectionKm(s, e) }))
    .filter((r) => r.km !== null)
    .map((r) => ({ ...r, onFire: e.sections ? e.sections.includes(r.s.id) : r.km === 0 }))
    .sort((a, b) => b.onFire - a.onFire || a.km - b.km);
  const clear = rows.filter((r) => !r.onFire);
  const ref = clear.length ? clear[0].km : null;
  const smoke = typeof e.km === 'number' && e.km <= 10;

  const out = rows.map(({ s, km, onFire }) => {
    const sheet = cropIdOf(s.currentCrop) ? s.currentCrop : null;
    const crop = cropIdOf(sheet);
    const fuel = crop ? fieldFuel(crop, season) : null;
    const front = !onFire && km <= ref + FRONT_KM;
    const tips = [];
    let change = null;
    let keep = null;

    if (onFire) {
      tips.push('Le feu touche la section : n’y allez pas et suivez les consignes des pompiers.');
      tips.push(
        'Après le feu, l’appli mesure le brûlage avec les images satellites et propose de changer la prochaine culture de la section.',
      );
      return { id: s.id, km: 0, front: false, onFire: true, crop: sheet, fuel, tips, change, keep };
    }

    const dry = fuel ? fuel.level !== 'faible' : season !== 'pousse';
    if (front && crop && CEREALS.has(crop) && season === 'recolte') {
      tips.push(
        'Si la céréale est encore sur pied, récoltez cette section en premier : un champ mûr brûle vite.',
      );
    }
    if (front && dry) {
      tips.push(
        'Passez le disque sur une bande du côté du feu : la terre nue arrête un feu d’herbe ou de chaume.',
      );
    }
    if (fuel?.level === 'faible') {
      tips.push('Culture verte ou peu de résidus : elle brûle mal, pas de travail du sol à faire.');
    } else if (!fuel && !front) {
      tips.push('Plus loin du feu : à surveiller, rien à faire pour l’instant.');
    } else if (fuel && !front) {
      tips.push('Plus loin du feu : à travailler après les sections côté feu.');
    }
    if (smoke && crop === 'luzerne' && (season === 'pousse' || season === 'recolte')) {
      tips.push(
        'Vérifiez la cendre sur la luzerne avant de la couper ou de la servir aux animaux.',
      );
    }
    if (!tips.length) tips.push('Côté feu : surveillez la bordure du champ.');

    if (front) {
      change = fireCoverAdvice(s, seeds);
      if (!change && crop === 'luzerne') keep = 'luzerne';
    }
    return { id: s.id, km, front, onFire: false, crop: sheet, fuel, tips, change, keep };
  });

  const general = ['Reportez tout brûlage de résidus ou de fossés.'];
  if (season === 'recolte') {
    general.push(
      'Évitez de récolter aux heures chaudes et venteuses : une moissonneuse peut allumer le chaume. Gardez de l’eau et un extincteur sur la machine.',
    );
  }
  if (season === 'semis') {
    general.push('Au printemps, c’est le chaume sec de l’an passé qui porte le feu.');
  }
  if (season === 'dormance') {
    general.push('Sans neige, le chaume sec laissé après la récolte porte le feu.');
  }
  if (out.some((r) => r.change)) {
    general.push(
      'La rotation ne change pas : seules les sections côté feu reçoivent un seigle d’automne après la récolte.',
    );
  }
  return { season, sections: out, general };
}

/* ---------- Formatting ---------- */

const MONTHS = [
  'janv.',
  'févr.',
  'mars',
  'avr.',
  'mai',
  'juin',
  'juil.',
  'août',
  'sept.',
  'oct.',
  'nov.',
  'déc.',
];

/** "2023-05-01" → "1 mai 2023". */
export function fmtDay(day) {
  if (!day) return 'date inconnue';
  const [y, m, d] = day.split('-').map(Number);
  return `${d} ${MONTHS[m - 1]} ${y}`;
}

/** "1 mai 2023", or "du 2 mai au 29 mai 2026" for a fire that lasted. */
export function fmtPeriod(day, lastDay) {
  if (!day || !lastDay || lastDay <= day) return fmtDay(day);
  return `du ${fmtDay(day)} au ${fmtDay(lastDay)}`;
}

/** Distance from the farm in words: "sur la ferme", "à 350 m", "à 4,2 km". */
export function fmtKm(km) {
  if (km === 0) return 'sur la ferme';
  if (km < 1) return `à ${Math.round(km * 1000)} m`;
  return `à ${String(Math.round(km * 10) / 10).replace('.', ',')} km`;
}

/** Years between an ISO day and now (fractional). */
export const yearsSince = (day, now = Date.now()) =>
  day ? (now - Date.parse(day)) / (365.25 * DAY_MS) : null;
