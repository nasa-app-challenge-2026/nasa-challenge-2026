/**
 * Network calls of the fire page. Every service here is free, needs no key and
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
 * Raw JSON only: application/fireData.js picks what it needs and normalises it
 * with the pure helpers of application/rules/wildfire.js.
 */
const CWFIS = 'https://cwfis.cfs.nrcan.gc.ca/geoserver/public/wfs';
const ACI = 'https://www.agr.gc.ca/imagery-images/rest/services/annual_crop_inventory';
const SOILGRIDS = 'https://rest.isric.org/soilgrids/v2.0/properties/query';
const PC = 'https://planetarycomputer.microsoft.com/api';

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

const postJson = (url, label, body, ms) =>
  getJson(url, label, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
    ms,
  });

/* ---------- CWFIS ---------- */

/** One CWFIS WFS layer (GeoJSON, EPSG:4326). `params` adds or overrides query parameters. */
export function fetchCwfisLayer(typeName, params, label) {
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
  return getJson(url, label);
}

/* ---------- AAFC Annual Crop Inventory ---------- */

/**
 * Raw inventory values of one year at `points` ([lon, lat]), in the order of the
 * points; null when the year failed or did not answer for every point.
 */
export async function fetchCropSamples(year, points) {
  const url = new URL(`${ACI}/${year}/ImageServer/getSamples`);
  url.searchParams.set('geometry', JSON.stringify({ points, spatialReference: { wkid: 4326 } }));
  url.searchParams.set('geometryType', 'esriGeometryMultipoint');
  url.searchParams.set('returnFirstValueOnly', 'true');
  url.searchParams.set('f', 'json');
  try {
    const json = await getJson(url, 'L’inventaire des cultures', { ms: 30_000 });
    const values = [...(json.samples ?? [])]
      .sort((a, b) => a.locationId - b.locationId)
      .map((s) => s.value);
    return values.length === points.length ? values : null;
  } catch {
    return null;
  }
}

/* ---------- SoilGrids ---------- */

/** SoilGrids at a point (0–15 cm). It is slow and sometimes drops a call: one more try. */
export async function fetchSoilGrids(lat, lon) {
  const url = new URL(SOILGRIDS);
  url.searchParams.set('lon', lon.toFixed(4));
  url.searchParams.set('lat', lat.toFixed(4));
  for (const p of ['clay', 'sand', 'silt', 'soc', 'phh2o']) url.searchParams.append('property', p);
  for (const d of ['0-5cm', '5-15cm']) url.searchParams.append('depth', d);
  url.searchParams.set('value', 'mean');
  try {
    return await getJson(url, 'SoilGrids', { ms: 45_000 });
  } catch {
    return getJson(url, 'SoilGrids', { ms: 45_000 });
  }
}

/* ---------- NASA HLS on the Planetary Computer ---------- */

/** STAC search of the Planetary Computer (body: collections, intersects, datetime…). */
export const searchHls = (body) => postJson(`${PC}/stac/v1/search`, 'Le catalogue d’images', body);

/** Statistics of one HLS item over a GeoJSON feature (`params`: assets, expression…). */
export function hlsStatistics(item, params, feature) {
  const url = new URL(`${PC}/data/v1/item/statistics`);
  url.searchParams.set('collection', item.collection);
  url.searchParams.set('item', item.id);
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);
  return postJson(url, 'Les images satellites', feature, 60_000);
}
