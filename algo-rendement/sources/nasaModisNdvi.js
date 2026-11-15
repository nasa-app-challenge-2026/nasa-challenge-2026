/**
 * Source 2 : Vigueur végétale par satellite (NDVI & EVI) — Ressource #3 du défi NASA Space Apps.
 *
 * Télécharge en UNE SEULE requête HTTP par année une tuile matricielle complète
 * (64 x 64 = 4 096 pixels sur une boîte régionale autour de la ferme) au format NumPy (.npy)
 * depuis la collection officielle NASA MODIS `MOD13Q1 v061` (250m 16-Day NDVI & EVI).
 */
import { CONFIG } from '../config.js';
import {
  readBoundedBuffer,
  readBoundedJson,
  readCache,
  regionCellKey,
  validateHistoricalSamplingParams,
  writeCache,
  bboxCacheKey,
  sameBbox,
  validateBbox,
} from './cache.js';
import { parseNpyGrid } from './rasterParser.js';

const MODIS_SCALE_FACTOR = 0.0001;

/**
 * Calcule la boîte englobante [minLon, minLat, maxLon, maxLat] en degrés WGS84 (EPSG:4326)
 * autour de (lat, lon) pour une demi-largeur de `halfWindowKm` kilomètres.
 */
export function computeRegionBbox(lat, lon, halfWindowKm = 8) {
  const numLat = Number(lat);
  const numLon = Number(lon);
  const hwKm = Number(halfWindowKm);
  if (
    !Number.isFinite(numLat) ||
    !Number.isFinite(numLon) ||
    numLat < -80 ||
    numLat > 80 ||
    numLon < -180 ||
    numLon > 180
  ) {
    throw new RangeError(
      `Coordonnées hors zone valide [-80°, +80°] pour computeRegionBbox : (${lat}, ${lon})`,
    );
  }
  if (!Number.isFinite(hwKm) || hwKm < 1 || hwKm > 25) {
    throw new RangeError(
      `Demi-fenêtre régionale invalide pour computeRegionBbox (halfWindowKm=${halfWindowKm})`,
    );
  }
  const dLat = hwKm / 111.32;
  const dLon = hwKm / (111.32 * Math.cos((numLat * Math.PI) / 180));
  return validateBbox({
    minLon: Number((numLon - dLon).toFixed(5)),
    minLat: Number((numLat - dLat).toFixed(5)),
    maxLon: Number((numLon + dLon).toFixed(5)),
    maxLat: Number((numLat + dLat).toFixed(5)),
  });
}

/**
 * Construit les coordonnées (lat, lon) de chaque pixel (r, c) d'une boîte `bbox` de taille `width x height`.
 */
export function buildBboxGridCoordinates(bbox, width = 64, height = 64) {
  const { minLon, minLat, maxLon, maxLat } = bbox;
  const dLon = (maxLon - minLon) / width;
  const dLat = (maxLat - minLat) / height;

  const coords = new Array(width * height);
  for (let r = 0; r < height; r++) {
    const lat = Number((maxLat - (r + 0.5) * dLat).toFixed(6));
    for (let c = 0; c < width; c++) {
      const lon = Number((minLon + (c + 0.5) * dLon).toFixed(6));
      const index = r * width + c;
      coords[index] = { index, row: r, col: c, lat, lon };
    }
  }
  return coords;
}

/**
 * Trouve le granule MODIS `modis-13Q1-061` couvrant (lat, lon) au pic estival (15 juillet – 10 août).
 */
async function findModisSummerItem({ lat, lon, year }) {
  const res = await fetch(CONFIG.endpoints.planetaryComputerStac, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal: AbortSignal.timeout(CONFIG.httpTimeoutMs),
    body: JSON.stringify({
      collections: ['modis-13Q1-061'],
      intersects: { type: 'Point', coordinates: [lon, lat] },
      datetime: `${year}-07-15T00:00:00Z/${year}-08-10T23:59:59Z`,
      limit: 2,
    }),
  });

  if (!res.ok) {
    throw new Error(`STAC modis-13Q1-061 a répondu HTTP ${res.status} (${year})`);
  }
  const json = await readBoundedJson(res);
  return json.features?.[0] || null;
}

/**
 * Télécharge en UNE SEULE requête HTTP la grille `width x height` (ex. 64x64 = 4 096 pixels)
 * de NDVI et EVI au format binaire `.npy` sur la boîte `bbox`.
 */
async function fetchModisBboxTile({ itemId, bbox, width = 64, height = 64 }) {
  const { minLon, minLat, maxLon, maxLat } = bbox;
  const url = `https://planetarycomputer.microsoft.com/api/data/v1/item/crop/${minLon},${minLat},${maxLon},${maxLat}.npy?collection=modis-13Q1-061&item=${encodeURIComponent(itemId)}&assets=250m_16_days_NDVI&assets=250m_16_days_EVI&width=${width}&height=${height}&coord_crs=epsg:4326`;
  const res = await fetch(url, {
    signal: AbortSignal.timeout(CONFIG.httpTimeoutMs),
  });
  if (!res.ok) {
    throw new Error(`TiTiler MODIS crop .npy HTTP ${res.status}`);
  }
  const buf = await readBoundedBuffer(res);
  const parsed = parseNpyGrid(buf, { expectedWidth: width, expectedHeight: height });
  const rawNdviBand = parsed.bands[0] || [];
  const rawEviBand = parsed.bands[1] || [];

  const pixels = rawNdviBand.map((v) =>
    v > -2000 && v <= 10000 ? Number((v * MODIS_SCALE_FACTOR).toFixed(4)) : null,
  );
  const eviPixels = rawEviBand.map((v) =>
    v > -2000 && v <= 10000 ? Number((v * MODIS_SCALE_FACTOR).toFixed(4)) : null,
  );

  return { pixels, eviPixels };
}

/**
 * Récupère les tuiles régionales de 64x64 (4 096 pixels) de NDVI et EVI au pic de l'été
 * pour chaque année de [startYear, endYear] (1 seule requête image par année).
 */
export async function fetchRegionalNdviSeries({
  lat,
  lon,
  startYear = CONFIG.sampling.startYear,
  endYear = CONFIG.sampling.endYear,
  halfWindowKm = 8,
  gridSize = 64,
}) {
  const valid = validateHistoricalSamplingParams({
    lat,
    lon,
    startYear,
    endYear,
    gridSize,
    halfWindowKm,
  });

  const bbox = computeRegionBbox(valid.lat, valid.lon, valid.halfWindowKm);
  const legacyKey = `bbox_${regionCellKey(valid.lat, valid.lon, 0.05)}_${valid.startYear}_${valid.endYear}_${valid.gridSize}x${valid.gridSize}_${valid.halfWindowKm}km`;
  const cacheKey = `${legacyKey}_${bboxCacheKey(bbox)}`;
  const matches = (d) =>
    sameBbox(d.bbox, bbox) &&
    d.nrows === valid.gridSize &&
    d.ncols === valid.gridSize &&
    Object.keys(d.gridsByYear).length === valid.endYear - valid.startYear + 1 &&
    Array.from(
      { length: valid.endYear - valid.startYear + 1 },
      (_, i) => valid.startYear + i,
    ).every((year) => Object.hasOwn(d.gridsByYear, year));
  const cached =
    readCache('modis-ndvi', cacheKey, matches) || readCache('modis-ndvi', legacyKey, matches);
  if (cached) return { ...cached, fromCache: true };

  const pixelCoordinates = buildBboxGridCoordinates(bbox, valid.gridSize, valid.gridSize);
  const gridsByYear = {};

  const years = [];
  for (let y = valid.startYear; y <= valid.endYear; y++) years.push(y);

  await Promise.all(
    years.map(async (year) => {
      const item = await findModisSummerItem({ lat: valid.lat, lon: valid.lon, year });
      if (!item) {
        gridsByYear[year] = {
          year,
          itemId: null,
          pixels: new Array(valid.gridSize * valid.gridSize).fill(null),
          eviPixels: new Array(valid.gridSize * valid.gridSize).fill(null),
        };
        return;
      }

      const { pixels, eviPixels } = await fetchModisBboxTile({
        itemId: item.id,
        bbox,
        width: valid.gridSize,
        height: valid.gridSize,
      });

      gridsByYear[year] = {
        year,
        itemId: item.id,
        pixels,
        eviPixels,
      };
    }),
  );

  const payload = {
    source: `NASA MODIS MOD13Q1 v061 (Grille régionale ${valid.gridSize}×${valid.gridSize} = ${valid.gridSize * valid.gridSize} pixels, NDVI & EVI)`,
    coordinates: { lat: valid.lat, lon: valid.lon },
    bbox,
    nrows: valid.gridSize,
    ncols: valid.gridSize,
    halfWindowKm: valid.halfWindowKm,
    pixelCoordinates,
    gridsByYear,
  };

  return writeCache('modis-ndvi', cacheKey, payload);
}

/**
 * Interroge le catalogue public NASA CMR-STAC (LPCLOUD) pour lister les scènes
 * HLS 30m (Landsat 8/9 `HLSL30.v2.0` + Sentinel-2 `HLSS30.v2.0`) disponibles sur la parcelle.
 */
export async function searchHls30mGranules({ lat, lon, year, maxCloudCover = 20 }) {
  const valid = validateHistoricalSamplingParams({
    lat,
    lon,
    startYear: year,
    endYear: year,
  });
  const delta = 0.02;
  const bbox = [valid.lon - delta, valid.lat - delta, valid.lon + delta, valid.lat + delta].join(
    ',',
  );
  const datetime = `${valid.startYear}-07-01T00:00:00Z/${valid.startYear}-08-25T23:59:59Z`;

  const params = new URLSearchParams({
    collections: 'HLSL30.v2.0,HLSS30.v2.0',
    bbox,
    datetime,
    limit: '10',
  });

  const url = `${CONFIG.endpoints.cmrStacSearch}?${params.toString()}`;
  const headers = { Accept: 'application/geo+json' };
  if (CONFIG.credentials.earthdataToken) {
    headers.Authorization = `Bearer ${CONFIG.credentials.earthdataToken}`;
  }

  const res = await fetch(url, {
    headers,
    signal: AbortSignal.timeout(CONFIG.httpTimeoutMs),
  });
  if (!res.ok) {
    throw new Error(`NASA CMR-STAC LPCLOUD a répondu HTTP ${res.status}`);
  }

  const data = await readBoundedJson(res);
  const features = (data.features || []).filter(
    (f) => (f.properties?.['eo:cloud_cover'] ?? 0) <= maxCloudCover,
  );

  return features.map((f) => ({
    id: f.id,
    collection: f.collection,
    datetime: f.properties?.datetime,
    cloudCover: f.properties?.['eo:cloud_cover'],
    redBandHref: f.assets?.B04?.href || null,
    nirBandHref: f.assets?.B8A?.href || f.assets?.B05?.href || null,
  }));
}
