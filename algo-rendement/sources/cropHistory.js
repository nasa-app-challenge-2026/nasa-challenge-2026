/**
 * Source 3 : Historique des cultures par tuile matricielle complète (64 x 64 = 4 096 pixels)
 * en UNE SEULE requête HTTP par année !
 *
 * 1) Canada / Québec / Ontario / Prairies / Maritimes : Agriculture et Agroalimentaire Canada (AAC / AAFC)
 *    `annual_crop_inventory/{year}/ImageServer/exportImage` (GeoTIFF non compressé 8-bit `U8`).
 * 2) États-Unis : USDA Cropland Data Layer (CDL) via Planetary Computer STAC `.npy` ou CropScape.
 *
 * Inclut :
 * - Une polyligne frontalière haute précision Canada / États-Unis (incluant les corridors fluviaux
 *   Détroit/Windsor, Sarnia/Port Huron, Niagara/Buffalo, Sault Ste. Marie et la diagonale Beauce/Maine).
 * - Une fusion pixel par pixel AAFC + USDA CDL lorsque la boîte de 16 km chevauche la frontière,
 *   ainsi qu'un basculement automatique si le fournisseur primaire renvoie 0 pixel cultivé.
 */
import { CONFIG, SATELLITE_CROP_CODES, SATELLITE_CROP_MAPPING_VERSION } from '../config.js';
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
import { computeRegionBbox } from './nasaModisNdvi.js';
import { parseNpyGrid, parseUncompressedTiffU8 } from './rasterParser.js';

/**
 * Interpolation linéaire entre une liste ordonnée de sommets `[x, y]`.
 */
function interpolatePolyline(x, vertices) {
  if (x <= vertices[0][0]) return vertices[0][1];
  for (let i = 0; i < vertices.length - 1; i++) {
    const [x0, y0] = vertices[i];
    const [x1, y1] = vertices[i + 1];
    if (x >= x0 && x <= x1) {
      if (x1 === x0) return y1;
      const t = (x - x0) / (x1 - x0);
      return y0 + t * (y1 - y0);
    }
  }
  return vertices[vertices.length - 1][1];
}

/**
 * Polyligne principale de la frontière Canada / États-Unis (sommets `[lon, lat]` d'ouest en est).
 */
const BORDER_LAT_BY_LON_VERTICES = [
  [-141.0, 60.0],
  [-130.0, 54.7],
  [-125.0, 48.5],
  [-123.2, 48.3], // Détroit de Juan de Fuca (Victoria BC = 48.43°N au nord)
  [-122.75, 49.0], // Boundary Bay / Blaine
  [-95.15, 49.0], // 49e parallèle jusqu'au lac des Bois
  [-94.6, 48.72], // Rainy River
  [-93.4, 48.6], // International Falls / Fort Frances
  [-89.5, 48.0], // Pigeon River (MN / ON)
  [-87.5, 47.75], // Lac Supérieur nord
  [-84.75, 46.508], // Entrée de la rivière St. Marys
  [-84.1, 46.508], // Sault Ste. Marie (ON = 46.52°N >= 46.508, MI = 46.49°N < 46.508)
  [-83.5, 45.95], // Détroit de Mississagi / Île Manitoulin
  [-82.42, 43.02], // Pointe sud du lac Huron (Sarnia / Port Huron)
  [-82.42, 41.68], // Bassin ouest du lac Érié (Île Pelée)
  [-81.2, 42.15], // Milieu du lac Érié (London ON au nord)
  [-78.905, 42.88], // Entrée de la rivière Niagara (Fort Erie ON / Buffalo NY)
  [-78.8, 43.63], // Lac Ontario (au nord de Buffalo / Rochester NY)
  [-76.3, 43.63], // Est du lac Ontario (Toronto / Kingston au nord, Syracuse / Oswego au sud)
  [-76.1, 44.2], // Mille-Îles (Fleuve Saint-Laurent)
  [-74.65, 45.0], // Cornwall / Akwesasne (début du 45e parallèle)
  [-71.5, 45.0], // 45e parallèle (Québec / NY & VT jusqu'à Canaan/Hereford)
  [-71.08, 45.25], // Frontière Woburn / Coburn Gore (Lac-Mégantic QC = 45.58°N au nord)
  [-70.65, 45.79], // Armstrong QC / Jackman ME (Saint-Georges-de-Beauce = 46.12°N au nord)
  [-70.3, 46.05], // Saint-Zacharie / Sainte-Aurélie QC (Montmagny / Saint-Jean-Port-Joli au nord)
  [-70.0, 46.55], // Daaquam / Saint-Juste-de-Bretenières QC
  [-69.45, 47.46], // Pohénégamook / Estcourt (pointe nord du Maine)
  [-69.0, 47.18], // Rivière Saint-François
  [-68.6, 47.255], // Clair NB (47.26°N) vs Fort Kent ME (47.25°N)
  [-68.33, 47.36], // Edmundston NB (47.37°N) vs Madawaska ME (47.35°N)
  [-67.78, 47.08], // Saint-Léonard NB / Van Buren ME
  [-67.78, 45.95], // Méridien est du Maine (Presque Isle ME = -68.01°W à l'ouest)
  [-67.45, 45.55], // Rivière Sainte-Croix
  [-66.95, 44.8], // Baie de Passamaquoddy / Grand Manan
  [-65.0, 43.3], // Sud de la Nouvelle-Écosse
  [-52.0, 46.0], // Terre-Neuve
];

/**
 * Corridors fluviaux quasi-méridiens (Nord-Sud) où le partage se fait en longitude `lon` :
 * 1) Rivière Détroit — Lac Sainte-Claire — Rivière Sainte-Claire (MI à l'ouest, ON à l'est)
 * 2) Rivière Niagara (ON à l'ouest, NY à l'est)
 */
const DETROIT_STCLAIR_LON_BY_LAT = [
  [42.04, -83.12],
  [42.15, -83.11],
  [42.31, -83.045], // Windsor ON (-83.036) à l'est, Detroit MI (-83.046) à l'ouest
  [42.34, -83.01],
  [42.45, -82.9],
  [42.6, -82.5],
  [42.97, -82.415], // Sarnia ON (-82.407) à l'est, Port Huron MI (-82.425) à l'ouest
  [43.02, -82.415],
];

const NIAGARA_RIVER_LON_BY_LAT = [
  [42.85, -78.905],
  [42.9, -78.905], // Fort Erie ON (-78.927) à l'ouest, Buffalo NY (-78.878) à l'est
  [43.05, -79.02],
  [43.09, -79.065], // Niagara Falls ON (-79.085) à l'ouest, Niagara Falls NY (-79.038) à l'est
  [43.27, -79.07], // Embouchure sur le lac Ontario (Niagara-on-the-Lake ON vs Youngstown NY)
];

/**
 * Détermine avec précision si une coordonnée `(lat, lon)` se situe au Canada (`true`)
 * ou aux États-Unis (`false`).
 */
export function isLocationInCanada(lat, lon) {
  const numLat = Number(lat);
  const numLon = Number(lon);
  if (
    !Number.isFinite(numLat) ||
    !Number.isFinite(numLon) ||
    numLon < -141.0 ||
    numLon > -52.0 ||
    numLat < 41.65 ||
    numLat > 84.0
  ) {
    return false;
  }

  // Corridor 1 : Rivière Détroit / Lac Sainte-Claire / Rivière Sainte-Claire (Ontario à l'est du chenal)
  if (numLat >= 42.04 && numLat <= 43.02 && numLon >= -83.25 && numLon <= -82.35) {
    const riverLon = interpolatePolyline(numLat, DETROIT_STCLAIR_LON_BY_LAT);
    return numLon >= riverLon;
  }

  // Corridor 2 : Rivière Niagara (Ontario à l'ouest du chenal, État de New York à l'est)
  if (numLat >= 42.85 && numLat <= 43.27 && numLon >= -79.15 && numLon <= -78.8) {
    const riverLon = interpolatePolyline(numLat, NIAGARA_RIVER_LON_BY_LAT);
    return numLon <= riverLon;
  }

  const borderLat = interpolatePolyline(numLon, BORDER_LAT_BY_LON_VERTICES);
  return numLat >= borderLat;
}

/**
 * Vérifie si une boîte régionale `bbox` chevauche la frontière Canada / États-Unis.
 */
export function isBorderStraddlingBbox(bbox) {
  if (!bbox) return false;
  const { minLat, maxLat, minLon, maxLon } = bbox;
  const midLat = (minLat + maxLat) / 2;
  const midLon = (minLon + maxLon) / 2;
  const samplePoints = [
    [minLat, minLon],
    [minLat, maxLon],
    [maxLat, minLon],
    [maxLat, maxLon],
    [midLat, midLon],
    [minLat, midLon],
    [maxLat, midLon],
    [midLat, minLon],
    [midLat, maxLon],
  ];
  let hasCanada = false;
  let hasUs = false;
  for (const [pLat, pLon] of samplePoints) {
    if (isLocationInCanada(pLat, pLon)) {
      hasCanada = true;
    } else {
      hasUs = true;
    }
    if (hasCanada && hasUs) return true;
  }
  return false;
}

function validateTileRequestParams({ bbox, year, gridSize, lat = null, lon = null }) {
  validateBbox(bbox);
  const y = Number(year);
  if (!Number.isInteger(y) || y < 1981 || y > 2030) {
    throw new RangeError(
      `Année de tuile satellite invalide (year=${year}) : entier [1981, 2030] attendu.`,
    );
  }
  const g = Number(gridSize);
  if (!Number.isInteger(g) || g < 4 || g > 128) {
    throw new RangeError(
      `Taille de grille invalide (gridSize=${gridSize}) : entier [4, 128] attendu.`,
    );
  }
  if (
    !bbox ||
    !Number.isFinite(Number(bbox.minLon)) ||
    !Number.isFinite(Number(bbox.minLat)) ||
    !Number.isFinite(Number(bbox.maxLon)) ||
    !Number.isFinite(Number(bbox.maxLat))
  ) {
    throw new RangeError('Boîte englobante (bbox) invalide ou incomplète.');
  }
  if (lat !== null || lon !== null) {
    const numLat = Number(lat);
    const numLon = Number(lon);
    if (
      !Number.isFinite(numLat) ||
      !Number.isFinite(numLon) ||
      numLat < -80 ||
      numLat > 80 ||
      numLon < -180 ||
      numLon > 180
    ) {
      throw new RangeError(`Coordonnées invalides : (${lat}, ${lon})`);
    }
  }
  return { year: y, gridSize: g };
}

/**
 * Projection officielle Albers Equal Area Conic (EPSG:5070 / NAD83 Conus Albers)
 * requise par les services USDA CropScape.
 */
export function latLonToAlbersEpsg5070(latDeg, lonDeg) {
  const a = 6378137.0;
  const e2 = 0.0066943800229;
  const e = Math.sqrt(e2);
  const rad = Math.PI / 180;

  const phi1 = 29.5 * rad;
  const phi2 = 45.5 * rad;
  const phi0 = 23.0 * rad;
  const lam0 = -96.0 * rad;
  const phi = latDeg * rad;
  const lam = lonDeg * rad;

  const calcM = (p) => Math.cos(p) / Math.sqrt(1 - e2 * Math.sin(p) ** 2);
  const calcQ = (p) => {
    const sinP = Math.sin(p);
    return (
      (1 - e2) *
      (sinP / (1 - e2 * sinP ** 2) - (1 / (2 * e)) * Math.log((1 - e * sinP) / (1 + e * sinP)))
    );
  };

  const m1 = calcM(phi1);
  const m2 = calcM(phi2);
  const q0 = calcQ(phi0);
  const q1 = calcQ(phi1);
  const q2 = calcQ(phi2);
  const q = calcQ(phi);

  const n = (m1 ** 2 - m2 ** 2) / (q2 - q1);
  const C = m1 ** 2 + n * q1;
  const rho0 = (a * Math.sqrt(C - n * q0)) / n;
  const rho = (a * Math.sqrt(C - n * q)) / n;
  const theta = n * (lam - lam0);

  const x = rho * Math.sin(theta);
  const y = rho0 - rho * Math.cos(theta);
  return { x: Number(x.toFixed(2)), y: Number(y.toFixed(2)) };
}

/**
 * Télécharge en UNE SEULE requête HTTP la grille `gridSize x gridSize` (4 096 pixels)
 * de l'Inventaire annuel des cultures d'AAC (Canada/Québec) pour une année donnée.
 */
export async function fetchAafcCanadaBboxTile({ bbox, year, gridSize = 64 }) {
  const valid = validateTileRequestParams({ bbox, year, gridSize });
  const { minLon, minLat, maxLon, maxLat } = bbox;
  const params = new URLSearchParams({
    bbox: `${Number(minLon)},${Number(minLat)},${Number(maxLon)},${Number(maxLat)}`,
    bboxSR: '4326',
    imageSR: '4326',
    size: `${valid.gridSize},${valid.gridSize}`,
    interpolation: 'RSP_NearestNeighbor',
    pixelType: 'U8',
    format: 'tiff',
    compression: 'NONE',
    f: 'image',
  });

  const url = `${CONFIG.endpoints.aafcCropInventoryRest}/${valid.year}/ImageServer/exportImage?${params.toString()}`;
  const res = await fetch(url, {
    signal: AbortSignal.timeout(CONFIG.httpTimeoutMs),
  });
  if (!res.ok) {
    throw new Error(`AAFC exportImage HTTP ${res.status} (${valid.year})`);
  }
  const buf = await readBoundedBuffer(res);
  const { pixels } = parseUncompressedTiffU8(buf, {
    expectedWidth: valid.gridSize,
    expectedHeight: valid.gridSize,
  });
  return pixels.map((rawCode) => ({
    rawCode,
    cropId: SATELLITE_CROP_CODES.aafcCanada[rawCode] ?? null,
  }));
}

/**
 * Télécharge en UNE SEULE requête HTTP la grille `gridSize x gridSize` (4 096 pixels)
 * du USDA Cropland Data Layer (`usda-cdl`) via l'API STAC/TiTiler `.npy` pour une année donnée.
 */
export async function fetchUsdaCdlBboxTile({ lat, lon, bbox, year, gridSize = 64 }) {
  const valid = validateTileRequestParams({ bbox, year, gridSize, lat, lon });
  const stacRes = await fetch(CONFIG.endpoints.planetaryComputerStac, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal: AbortSignal.timeout(CONFIG.httpTimeoutMs),
    body: JSON.stringify({
      collections: ['usda-cdl'],
      intersects: { type: 'Point', coordinates: [Number(lon), Number(lat)] },
      datetime: `${valid.year}-01-01T00:00:00Z/${valid.year}-12-31T23:59:59Z`,
      limit: 5,
    }),
  });
  if (!stacRes.ok) return null;
  const stacJson = await readBoundedJson(stacRes);
  const item = (stacJson.features || []).find((f) => f.assets?.cropland);
  if (!item) return null;

  const { minLon, minLat, maxLon, maxLat } = bbox;
  const url = `https://planetarycomputer.microsoft.com/api/data/v1/item/crop/${Number(minLon)},${Number(minLat)},${Number(maxLon)},${Number(maxLat)}.npy?collection=usda-cdl&item=${encodeURIComponent(item.id)}&assets=cropland&width=${valid.gridSize}&height=${valid.gridSize}&coord_crs=epsg:4326`;
  const res = await fetch(url, {
    signal: AbortSignal.timeout(CONFIG.httpTimeoutMs),
  });
  if (!res.ok) return null;
  const buf = await readBoundedBuffer(res);
  const parsed = parseNpyGrid(buf, {
    expectedWidth: valid.gridSize,
    expectedHeight: valid.gridSize,
  });
  const rawCodes = parsed.bands[0] || [];
  return rawCodes.map((rawCode) => ({
    rawCode,
    cropId: SATELLITE_CROP_CODES.usdaCdl[rawCode] ?? null,
  }));
}

async function fetchTilesForProvider({ provider, lat, lon, regionBbox, gridSize, years }) {
  const tilesByYear = {};
  await Promise.all(
    years.map(async (year) => {
      if (provider === 'AAFC_CANADA') {
        tilesByYear[year] = await fetchAafcCanadaBboxTile({ bbox: regionBbox, year, gridSize });
      } else {
        tilesByYear[year] = await fetchUsdaCdlBboxTile({
          lat,
          lon,
          bbox: regionBbox,
          year,
          gridSize,
        });
      }
    }),
  );
  return tilesByYear;
}

/**
 * Fusionne deux jeux de tuiles (ex. AAFC Canada + USDA CDL sur une boîte transfrontalière)
 * pixel par pixel : conserve le pixel primaire s'il est reconnu, sinon utilise le pixel secondaire.
 */
export function mergeCrossBorderTilesByYear(
  primaryTilesByYear,
  secondaryTilesByYear,
  years,
  nPixels,
) {
  const merged = {};
  let primaryCount = 0;
  let secondaryAddedCount = 0;

  for (const y of years) {
    const pTile = primaryTilesByYear?.[y] || [];
    const sTile = secondaryTilesByYear?.[y] || [];
    const row = new Array(nPixels);
    for (let i = 0; i < nPixels; i++) {
      const pCell = pTile[i] || null;
      const sCell = sTile[i] || null;
      if (pCell?.cropId) {
        row[i] = pCell;
        primaryCount += 1;
      } else if (sCell?.cropId) {
        row[i] = sCell;
        secondaryAddedCount += 1;
      } else {
        row[i] = pCell || sCell || { rawCode: 0, cropId: null };
      }
    }
    merged[y] = row;
  }

  return { mergedTilesByYear: merged, primaryCount, secondaryAddedCount };
}

function countRecognizedCropPixels(tilesByYear, years) {
  let total = 0;
  for (const y of years) {
    const tile = tilesByYear[y] || [];
    for (const cell of tile) {
      if (cell?.cropId) total += 1;
    }
  }
  return total;
}

/**
 * Récupère en parallèle (1 requête par année) les tuiles complètes de cultures (`64x64 = 4 096 pixels`)
 * sur toute la période `[startYear, endYear]`, avec fusion transfrontalière ou basculement automatique.
 */
export async function fetchRegionalCropHistory({
  lat,
  lon,
  bbox,
  gridSize = 64,
  halfWindowKm = 8,
  startYear = CONFIG.sampling.startYear,
  endYear = CONFIG.sampling.endYear,
}) {
  const valid = validateHistoricalSamplingParams({
    lat,
    lon,
    startYear,
    endYear,
    gridSize,
    halfWindowKm,
  });
  const primaryIsCanada = isLocationInCanada(valid.lat, valid.lon);
  let provider = primaryIsCanada ? 'AAFC_CANADA' : 'USDA_CDL';
  const regionBbox = bbox || computeRegionBbox(valid.lat, valid.lon, valid.halfWindowKm);
  validateBbox(regionBbox);
  const borderStraddling = isBorderStraddlingBbox(regionBbox);

  const legacySuffix = `${regionCellKey(valid.lat, valid.lon, 0.05)}_${valid.startYear}_${valid.endYear}_${valid.gridSize}x${valid.gridSize}_${valid.halfWindowKm}km`;
  const cellSuffix = `${legacySuffix}_${bboxCacheKey(regionBbox)}`;
  const primaryCacheKey = `bbox_${provider}_${cellSuffix}`;
  const altProvider = provider === 'AAFC_CANADA' ? 'USDA_CDL' : 'AAFC_CANADA';
  const altCacheKey = `bbox_${altProvider}_${cellSuffix}`;
  const mergedCacheKey = `bbox_MERGED_${cellSuffix}`;

  const matches = (d) =>
    // Sans version, une « luzerne » peut provenir de l'ancienne conversion erronée
    // AAFC 122, même dans un cache fusionné : ne pas réutiliser ces observations.
    (d.cropMappingVersion === SATELLITE_CROP_MAPPING_VERSION ||
      (d.cropMappingVersion === undefined &&
        !Object.values(d.cropIdsByYear).some((crops) => crops.includes('luzerne')))) &&
    sameBbox(d.bbox, regionBbox) &&
    d.gridSize === valid.gridSize &&
    Object.keys(d.cropIdsByYear).length === valid.endYear - valid.startYear + 1 &&
    Array.from(
      { length: valid.endYear - valid.startYear + 1 },
      (_, i) => valid.startYear + i,
    ).every((year) => Object.hasOwn(d.cropIdsByYear, year));
  const cached = [
    mergedCacheKey,
    primaryCacheKey,
    altCacheKey,
    `bbox_MERGED_${legacySuffix}`,
    `bbox_${provider}_${legacySuffix}`,
    `bbox_${altProvider}_${legacySuffix}`,
  ]
    .map((key) => readCache('crop-history', key, matches))
    .find(Boolean);
  if (cached) return { ...cached, fromCache: true };

  const years = [];
  for (let y = valid.startYear; y <= valid.endYear; y++) years.push(y);
  const nPixels = valid.gridSize * valid.gridSize;

  let tilesByYear = {};
  tilesByYear = await fetchTilesForProvider({
    provider,
    lat: valid.lat,
    lon: valid.lon,
    regionBbox,
    gridSize: valid.gridSize,
    years,
  });

  const primaryRecognized = countRecognizedCropPixels(tilesByYear, years);

  // Si la boîte chevauche la frontière OU si le fournisseur primaire renvoie 0 pixel cultivé,
  // on interroge également le second fournisseur pour fusionner ou basculer.
  if (borderStraddling || primaryRecognized === 0) {
    const altTiles = await fetchTilesForProvider({
      provider: altProvider,
      lat: valid.lat,
      lon: valid.lon,
      regionBbox,
      gridSize: valid.gridSize,
      years,
    }).catch(() => ({}));
    const altRecognized = countRecognizedCropPixels(altTiles, years);

    if (primaryRecognized === 0 && altRecognized > 0) {
      provider = altProvider;
      tilesByYear = altTiles;
    } else if (primaryRecognized > 0 && altRecognized > 0) {
      const { mergedTilesByYear, secondaryAddedCount } = mergeCrossBorderTilesByYear(
        tilesByYear,
        altTiles,
        years,
        nPixels,
      );
      if (secondaryAddedCount > 0) {
        provider = 'AAFC_CANADA+USDA_CDL';
        tilesByYear = mergedTilesByYear;
      }
    }
  }

  const recognizedCount = countRecognizedCropPixels(tilesByYear, years);
  if (recognizedCount === 0) {
    throw new Error(
      `Aucune donnée satellite de cultures (AAFC / USDA CDL) trouvée autour de (${valid.lat}, ${valid.lon}) sur ${valid.startYear}–${valid.endYear}.`,
    );
  }

  const cropIdsByYear = {};
  const cropCountsByYear = {};
  for (const year of years) {
    const tile = tilesByYear[year] || [];
    cropIdsByYear[year] = tile.map((cell) => cell?.cropId ?? null);
    const counts = {};
    for (const c of cropIdsByYear[year]) {
      if (c) counts[c] = (counts[c] || 0) + 1;
    }
    cropCountsByYear[year] = counts;
  }

  const sourceLabel =
    provider === 'AAFC_CANADA+USDA_CDL'
      ? `Fusion transfrontalière AAC Canada + USDA CDL (Tuile matricielle ${valid.gridSize}×${valid.gridSize} = ${nPixels} pixels)`
      : provider === 'AAFC_CANADA'
        ? `AAC / AAFC Inventaire annuel des cultures (Tuile matricielle ${valid.gridSize}×${valid.gridSize} = ${nPixels} pixels)`
        : `USDA NASS Cropland Data Layer (Tuile matricielle ${valid.gridSize}×${valid.gridSize} = ${nPixels} pixels)`;

  const finalCacheKey =
    provider === 'AAFC_CANADA+USDA_CDL' ? mergedCacheKey : `bbox_${provider}_${cellSuffix}`;

  const payload = {
    source: sourceLabel,
    provider,
    cropMappingVersion: SATELLITE_CROP_MAPPING_VERSION,
    excludedSatelliteClasses: provider.includes('AAFC_CANADA')
      ? [{ provider: 'AAFC_CANADA', rawCode: 122, reason: 'pasture_forage_not_alfalfa_specific' }]
      : [],
    borderStraddling,
    bbox: regionBbox,
    gridSize: valid.gridSize,
    sampledPointsCount: nPixels,
    cropCountsByYear,
    cropIdsByYear,
  };

  return writeCache('crop-history', finalCacheKey, payload);
}
