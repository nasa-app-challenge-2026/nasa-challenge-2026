/**
 * Cache disque sécurisé et atomique par cellule géographique + validateurs d'entrées et de flux HTTP.
 * - Protégé contre toute traversée de répertoire (Path Traversal) sur `namespace` et `key`.
 * - Écriture atomique via fichier temporaire `.tmp` + `renameSync` pour éviter tout JSON tronqué en concurrence.
 * - Validation stricte des bornes historiques (`startYear`, `endYear`, `gridSize`, `halfWindowKm`).
 * - Plafond de taille mémoire (`MAX_HTTP_RESPONSE_BYTES`) sur les réponses réseau.
 */
import {
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  statSync,
  unlinkSync,
  writeFileSync,
} from 'node:fs';
import { resolve, sep } from 'node:path';
import { createHash, randomUUID } from 'node:crypto';
import { CONFIG, CROP_TAXONOMY } from '../config.js';
import { validateClimateSeasons } from './climateValidation.js';

const SAFE_KEY_RE = /^[A-Za-z0-9._+-]+$/;
const WINDOWS_RESERVED_NAME_RE = /^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..+)?$/i;
const MAX_HTTP_RESPONSE_BYTES = 10 * 1024 * 1024; // 10 Mo max par réponse HTTP

export function validateBbox(bbox) {
  if (
    !bbox ||
    !['minLon', 'minLat', 'maxLon', 'maxLat'].every((k) => Number.isFinite(bbox[k])) ||
    bbox.minLon < -180 ||
    bbox.maxLon > 180 ||
    bbox.minLat < -90 ||
    bbox.maxLat > 90 ||
    bbox.minLon >= bbox.maxLon ||
    bbox.minLat >= bbox.maxLat
  ) {
    throw new RangeError('Boîte englobante (bbox) invalide ou hors bornes.');
  }
  return bbox;
}

export function sameBbox(a, b) {
  return (
    !!a &&
    !!b &&
    ['minLon', 'minLat', 'maxLon', 'maxLat'].every(
      (k) => Number.isFinite(a[k]) && Number.isFinite(b[k]) && Math.abs(a[k] - b[k]) < 1e-8,
    )
  );
}

export function bboxCacheKey(bbox) {
  validateBbox(bbox);
  return createHash('sha256')
    .update(JSON.stringify(['minLon', 'minLat', 'maxLon', 'maxLat'].map((k) => bbox[k])))
    .digest('hex')
    .slice(0, 16);
}

const isRecord = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
const isGridSize = (v) => Number.isInteger(v) && v >= 4 && v <= 128;
const isVigor = (v) => v === null || (Number.isFinite(v) && v >= -0.2 && v <= 1);
const validYearEntries = (v) =>
  isRecord(v) &&
  Object.keys(v).length > 0 &&
  Object.keys(v).length <= 21 &&
  Object.keys(v).every((y) => /^\d{4}$/.test(y) && +y >= 1981 && +y <= 2030);

/**
 * Schémas de validation structurelle minimale par espace de cache pour rejeter
 * tout fichier JSON bien formé mais incomplet ou corrompu.
 */
const NAMESPACE_VALIDATORS = {
  'nasa-power': (d) => !!validateClimateSeasons(d.seasons),
  'modis-ndvi': (d) =>
    isGridSize(d.nrows) &&
    isGridSize(d.ncols) &&
    !!validateBbox(d.bbox) &&
    validYearEntries(d.gridsByYear) &&
    Object.values(d.gridsByYear).every(
      (g) =>
        Array.isArray(g?.pixels) &&
        g.pixels.length === d.nrows * d.ncols &&
        g.pixels.every(isVigor) &&
        (!g.eviPixels ||
          (Array.isArray(g.eviPixels) &&
            g.eviPixels.length === d.nrows * d.ncols &&
            g.eviPixels.every(isVigor))),
    ),
  'crop-history': (d) =>
    isGridSize(d.gridSize) &&
    !!validateBbox(d.bbox) &&
    validYearEntries(d.cropIdsByYear) &&
    Object.values(d.cropIdsByYear).every(
      (arr) =>
        Array.isArray(arr) &&
        (arr.length === 0 || arr.length === d.gridSize ** 2) &&
        arr.every((c) => c === null || (typeof c === 'string' && Object.hasOwn(CROP_TAXONOMY, c))),
    ),
  'cmip6-projection': (d) =>
    !!validateClimateSeasons(d.projectedSeasons) && isRecord(d.baselineStats),
  'nass-quickstats': (d) => isRecord(d.yieldsByCropYear),
};

function isWindowsReservedName(segment) {
  return WINDOWS_RESERVED_NAME_RE.test(segment);
}

function resolveSafeCachePath(namespace, key) {
  const ns = String(namespace ?? '');
  const k = String(key ?? '');
  if (
    !SAFE_KEY_RE.test(ns) ||
    !SAFE_KEY_RE.test(k) ||
    ns.includes('..') ||
    k.includes('..') ||
    isWindowsReservedName(ns) ||
    isWindowsReservedName(k)
  ) {
    throw new Error(
      `Clé ou espace de cache invalide (caractères ou nom réservé interdit) : ${ns}/${k}`,
    );
  }

  const rootDir = resolve(CONFIG.cacheDir);
  const targetDir = resolve(rootDir, ns);
  const targetFile = resolve(targetDir, `${k}.json`);

  if (!targetDir.startsWith(`${rootDir}${sep}`) || !targetFile.startsWith(`${targetDir}${sep}`)) {
    throw new Error(`Accès hors du dossier de cache refusé : ${ns}/${k}`);
  }

  return { targetDir, targetFile };
}

export function readCache(namespace, key, validator = null) {
  const { targetFile } = resolveSafeCachePath(namespace, key);
  if (!existsSync(targetFile)) return null;
  try {
    if (statSync(targetFile).size > MAX_HTTP_RESPONSE_BYTES) return null;
    const parsed = JSON.parse(readFileSync(targetFile, 'utf8'));
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return null;
    }
    if (
      [NAMESPACE_VALIDATORS[namespace], validator].some(
        (check) => typeof check === 'function' && !check(parsed),
      )
    ) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

/**
 * Écriture atomique dans le cache : écrit d'abord dans un fichier temporaire unique
 * puis le renomme atomiquement vers `targetFile`.
 */
export function writeCache(namespace, key, data) {
  const { targetDir, targetFile } = resolveSafeCachePath(namespace, key);
  mkdirSync(targetDir, { recursive: true });
  const tmpFile = `${targetFile}.${process.pid}.${randomUUID()}.tmp`;
  try {
    writeFileSync(tmpFile, JSON.stringify(data, null, 2), 'utf8');
    renameSync(tmpFile, targetFile);
  } catch (err) {
    try {
      if (existsSync(tmpFile)) unlinkSync(tmpFile);
    } catch {
      // Ignore cleanup error
    }
    throw err;
  }
  return data;
}

/** Arrondit lat/lon au centre de la cellule régionale (~10 km par défaut : 0.1°) */
export function regionCellKey(lat, lon, step = 0.1) {
  const numLat = Number(lat);
  const numLon = Number(lon);
  if (!Number.isFinite(step) || step <= 0 || step > 1) {
    throw new RangeError('Pas de cellule invalide.');
  }
  if (
    !Number.isFinite(numLat) ||
    !Number.isFinite(numLon) ||
    numLat < -80 ||
    numLat > 80 ||
    numLon < -180 ||
    numLon > 180
  ) {
    throw new RangeError(
      `Coordonnées géographiques invalides ou hors zone agricole [-80°, +80°] : (${lat}, ${lon})`,
    );
  }
  const rLat = (Math.round(numLat / step) * step).toFixed(2);
  const rLon = (Math.round(numLon / step) * step).toFixed(2);
  return `lat${rLat}_lon${rLon}`;
}

/**
 * Valide les paramètres d'échantillonnage historique (`lat`, `lon`, `startYear`, `endYear`, `gridSize`, `halfWindowKm`)
 * afin d'empêcher tout déni de service par plage d'années géante, singularité polaire ou allocation de grille démesurée.
 */
export function validateHistoricalSamplingParams({
  lat,
  lon,
  startYear = CONFIG.sampling.startYear,
  endYear = CONFIG.sampling.endYear,
  gridSize = 64,
  halfWindowKm = 8,
}) {
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
    throw new RangeError(
      `Coordonnées géographiques invalides ou hors zone agricole [-80°, +80°] : (${lat}, ${lon})`,
    );
  }

  const sYear = Number(startYear);
  const eYear = Number(endYear);
  if (
    !Number.isInteger(sYear) ||
    !Number.isInteger(eYear) ||
    sYear < 1981 ||
    eYear > 2030 ||
    eYear < sYear ||
    eYear - sYear > 20
  ) {
    throw new RangeError(
      `Plage d'années historiques invalide (${startYear}–${endYear}) : entiers attendus dans [1981, 2030] avec un écart maximal de 20 ans.`,
    );
  }

  const gSize = Number(gridSize);
  if (!Number.isInteger(gSize) || gSize < 4 || gSize > 128) {
    throw new RangeError(
      `Taille de grille invalide (gridSize=${gridSize}) : entier attendu entre 4 et 128.`,
    );
  }

  const hwKm = Number(halfWindowKm);
  if (!Number.isFinite(hwKm) || hwKm < 1 || hwKm > 25) {
    throw new RangeError(
      `Demi-fenêtre régionale invalide (halfWindowKm=${halfWindowKm}) : valeur attendue entre 1 et 25 km.`,
    );
  }

  return {
    lat: numLat,
    lon: numLon,
    startYear: sYear,
    endYear: eYear,
    gridSize: gSize,
    halfWindowKm: hwKm,
  };
}

/**
 * Lit le corps binaire d'une réponse HTTP en imposant un plafond strict d'octets (`maxBytes`)
 * pour empêcher tout épuisement mémoire.
 */
export async function readBoundedBuffer(res, maxBytes = MAX_HTTP_RESPONSE_BYTES) {
  const contentLength = Number(res.headers?.get?.('content-length') || 0);
  if (contentLength > maxBytes) {
    throw new Error(
      `Réponse HTTP trop volumineuse (${contentLength} octets > limite de ${maxBytes} octets)`,
    );
  }

  if (!res.body || typeof res.body.getReader !== 'function') {
    const ab = await res.arrayBuffer();
    if (ab.byteLength > maxBytes) {
      throw new Error(
        `Réponse HTTP trop volumineuse (${ab.byteLength} octets > limite de ${maxBytes} octets)`,
      );
    }
    return Buffer.from(ab);
  }

  const reader = res.body.getReader();
  const chunks = [];
  let total = 0;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > maxBytes) {
      await reader.cancel().catch(() => {});
      throw new Error(`Flux HTTP interrompu : dépassement de la limite de ${maxBytes} octets`);
    }
    chunks.push(Buffer.from(value));
  }

  return Buffer.concat(chunks, total);
}

/**
 * Lit et parse une réponse JSON HTTP avec plafond de taille mémoire (`maxBytes`).
 */
export async function readBoundedJson(res, maxBytes = MAX_HTTP_RESPONSE_BYTES) {
  const buf = await readBoundedBuffer(res, maxBytes);
  return JSON.parse(buf.toString('utf8'));
}
