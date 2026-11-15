/**
 * Source 4 : USDA NASS QuickStats API (Ressource #19 du défi NASA Space Apps).
 * Récupère les rendements agricoles annuels finaux (`SURVEY` / `ANNUAL` / `YEAR` / `TOTAL`)
 * observés au sol par État américain.
 *
 * Note méthodologique et géographique :
 * - USDA NASS couvre uniquement les États-Unis : si la ferme est située au Canada
 *   (`isLocationInCanada(lat, lon) === true`), la calibration NASS est désactivée
 *   afin de ne jamais appliquer les rendements d'un État américain à une ferme canadienne.
 * - Filtre strictement `source_desc=SURVEY`, `freq_desc=ANNUAL`, `reference_period_desc=YEAR`,
 *   `domain_desc=TOTAL` et `class_desc` pour exclure les prévisions mensuelles (août/septembre)
 *   et les sous-classes hétérogènes.
 */
import { CONFIG } from '../config.js';
import { readBoundedJson, readCache, writeCache } from './cache.js';
import { isLocationInCanada } from './cropHistory.js';
import { validatePhysicalEffectPct } from '../engine/modelUtils.js';

const SAFE_STATE_RE = /^[A-Z]{2}$/;

export const NASS_COMMODITY_MAP = {
  mais: {
    commodity_desc: 'CORN',
    class_desc: 'ALL CLASSES',
    util_practice_desc: 'GRAIN',
    statisticcat_desc: 'YIELD',
    unit_desc: 'BU / ACRE',
    toTonnesPerHa: 0.06277,
  },
  soya: {
    commodity_desc: 'SOYBEANS',
    class_desc: 'ALL CLASSES',
    statisticcat_desc: 'YIELD',
    unit_desc: 'BU / ACRE',
    toTonnesPerHa: 0.06725,
  },
  ble: {
    commodity_desc: 'WHEAT',
    class_desc: 'ALL CLASSES',
    statisticcat_desc: 'YIELD',
    unit_desc: 'BU / ACRE',
    toTonnesPerHa: 0.06725,
  },
  orge: {
    commodity_desc: 'BARLEY',
    class_desc: 'ALL CLASSES',
    statisticcat_desc: 'YIELD',
    unit_desc: 'BU / ACRE',
    toTonnesPerHa: 0.0538,
  },
  patate: {
    commodity_desc: 'POTATOES',
    class_desc: 'ALL CLASSES',
    statisticcat_desc: 'YIELD',
    unit_desc: 'CWT / ACRE',
    toTonnesPerHa: 0.11209,
  },
  luzerne: {
    commodity_desc: 'HAY',
    class_desc: 'ALFALFA',
    statisticcat_desc: 'YIELD',
    unit_desc: 'TONS / ACRE',
    toTonnesPerHa: 2.2417,
  },
};

/**
 * Déduit le code d'État américain (ex. 'IA', 'IL', 'MN', 'NY', 'MI', 'ME') à partir de `(lat, lon)`.
 * Renvoie `null` si les coordonnées sont au Canada (`isLocationInCanada === true`) ou hors des États-Unis.
 */
export function inferUsStateFromLatLon(lat, lon) {
  if (lat === undefined || lon === undefined) return null;
  const numLat = Number(lat);
  const numLon = Number(lon);
  if (!Number.isFinite(numLat) || !Number.isFinite(numLon)) return null;
  if (isLocationInCanada(numLat, numLon) || numLat < 24.5 || numLat > 49.4) {
    return null;
  }

  // Principaux États agricoles du Midwest / Nord-Est américain
  if (numLat >= 40.35 && numLat <= 43.5 && numLon >= -96.6 && numLon <= -90.1) return 'IA';
  if (numLat >= 43.5 && numLat <= 49.4 && numLon >= -97.2 && numLon <= -89.5) return 'MN';
  if (numLat >= 37.0 && numLat <= 42.5 && numLon >= -91.5 && numLon <= -87.5) return 'IL';
  if (numLat >= 42.5 && numLat <= 47.1 && numLon >= -92.9 && numLon <= -86.8) return 'WI';
  if (numLat >= 37.8 && numLat <= 41.8 && numLon >= -88.1 && numLon <= -84.8) return 'IN';
  if (numLat >= 38.4 && numLat <= 42.0 && numLon >= -84.8 && numLon <= -80.5) return 'OH';
  if (numLat >= 41.7 && numLat <= 47.5 && numLon >= -90.4 && numLon <= -82.4) return 'MI';
  if (numLat >= 45.9 && numLat <= 49.0 && numLon >= -104.0 && numLon <= -96.5) return 'ND';
  if (numLat >= 42.5 && numLat <= 45.9 && numLon >= -104.0 && numLon <= -96.4) return 'SD';
  if (numLat >= 40.0 && numLat <= 43.0 && numLon >= -104.0 && numLon <= -95.3) return 'NE';
  if (numLat >= 37.0 && numLat <= 40.0 && numLon >= -102.0 && numLon <= -94.6) return 'KS';
  if (numLat >= 40.5 && numLat <= 45.01 && numLon >= -79.8 && numLon <= -73.3) return 'NY';
  if (numLat >= 42.7 && numLat <= 45.01 && numLon > -73.3 && numLon <= -71.5) return 'VT';
  if (numLat >= 42.7 && numLat <= 45.3 && numLon > -71.5 && numLon <= -70.7) return 'NH';
  if (numLat >= 43.0 && numLat <= 47.46 && numLon >= -71.08 && numLon <= -66.9) return 'ME';
  return null;
}

/**
 * Construit les paramètres de requête NASS QuickStats filtrés sur le bilan annuel final (`YEAR`).
 */
export function buildNassQueryParams({ apiKey, cropId, stateAlpha, startYear, endYear }) {
  const query = NASS_COMMODITY_MAP[cropId];
  if (!query) {
    throw new Error(`Culture NASS inconnue : ${cropId}`);
  }
  const params = new URLSearchParams({
    key: apiKey,
    source_desc: 'SURVEY',
    sector_desc: 'CROPS',
    commodity_desc: query.commodity_desc,
    class_desc: query.class_desc,
    statisticcat_desc: query.statisticcat_desc,
    unit_desc: query.unit_desc,
    domain_desc: 'TOTAL',
    agg_level_desc: 'STATE',
    freq_desc: 'ANNUAL',
    reference_period_desc: 'YEAR',
    state_alpha: stateAlpha,
    year__GE: String(startYear),
    year__LE: String(endYear),
    format: 'JSON',
  });
  if (query.util_practice_desc) {
    params.set('util_practice_desc', query.util_practice_desc);
  }
  return params;
}

/**
 * Filtre les lignes NASS QuickStats pour ne retenir que le rendement annuel final (`reference_period_desc === 'YEAR'`,
 * `source_desc === 'SURVEY'`, `domain_desc === 'TOTAL'`), en rejetant toute prévision mensuelle (`YEAR - AUG FORECAST`, etc.).
 */
export function extractAnnualSurveyYields(rows, cropId) {
  const query = NASS_COMMODITY_MAP[cropId];
  const expectedClass = query?.class_desc || 'ALL CLASSES';
  const result = {};
  const exactClassMatchedYear = new Set();

  for (const r of rows || []) {
    if (!r || typeof r !== 'object') continue;
    const year = Number(r.year);
    if (!Number.isInteger(year)) continue;

    // Rejeter toute prévision mensuelle (ex. 'YEAR - AUG FORECAST', 'YEAR - SEP FORECAST')
    if (r.reference_period_desc && String(r.reference_period_desc).toUpperCase() !== 'YEAR') {
      continue;
    }
    if (r.source_desc && String(r.source_desc).toUpperCase() !== 'SURVEY') {
      continue;
    }
    if (r.domain_desc && String(r.domain_desc).toUpperCase() !== 'TOTAL') {
      continue;
    }
    if (r.freq_desc && String(r.freq_desc).toUpperCase() !== 'ANNUAL') {
      continue;
    }

    const val = Number(
      String(r.Value ?? '')
        .replace(/,/g, '')
        .trim(),
    );
    if (!Number.isFinite(val) || val <= 0) continue;

    const rowClass = r.class_desc ? String(r.class_desc).toUpperCase() : expectedClass;
    if (rowClass === expectedClass) {
      result[year] = val;
      exactClassMatchedYear.add(year);
    } else if (!exactClassMatchedYear.has(year) && rowClass === 'ALL CLASSES') {
      result[year] = val;
    }
  }

  return result;
}

export async function fetchNassStateYields({
  lat,
  lon,
  stateAlpha = null,
  startYear = CONFIG.sampling.startYear,
  endYear = CONFIG.sampling.endYear,
}) {
  const resolvedState =
    stateAlpha !== null ? String(stateAlpha).toUpperCase() : inferUsStateFromLatLon(lat, lon);

  if (resolvedState === null) {
    return {
      available: false,
      stateAlpha: null,
      reason:
        'Localisation hors États-Unis (ou État non spécifié) — USDA NASS couvre uniquement les États-Unis.',
      yieldsByCropYear: {},
    };
  }

  if (!SAFE_STATE_RE.test(resolvedState)) {
    throw new Error(`Code d'État NASS invalide (2 lettres majuscules attendues) : ${stateAlpha}`);
  }

  if (!CONFIG.credentials.nassApiKey) {
    return {
      available: false,
      stateAlpha: resolvedState,
      reason: 'Variable USDA_NASS_API_KEY absente — écarts en % de vigueur satellite uniquement.',
      yieldsByCropYear: {},
    };
  }

  const cacheKey = `nass_${resolvedState}_${Number(startYear)}_${Number(endYear)}`;
  const cached = readCache('nass-quickstats', cacheKey);
  if (cached) return { ...cached, fromCache: true };

  const yieldsByCropYear = {};
  for (const cropId of Object.keys(NASS_COMMODITY_MAP)) {
    const params = buildNassQueryParams({
      apiKey: CONFIG.credentials.nassApiKey,
      cropId,
      stateAlpha: resolvedState,
      startYear,
      endYear,
    });

    const url = `${CONFIG.endpoints.usdaNassQuickStats}?${params.toString()}`;
    const res = await fetch(url, {
      signal: AbortSignal.timeout(CONFIG.httpTimeoutMs),
    });
    if (!res.ok) continue;
    const json = await readBoundedJson(res);
    yieldsByCropYear[cropId] = extractAnnualSurveyYields(json?.data || [], cropId);
  }

  return writeCache('nass-quickstats', cacheKey, {
    available: true,
    source: 'USDA NASS QuickStats API (SURVEY / ANNUAL / YEAR)',
    stateAlpha: resolvedState,
    yieldsByCropYear,
  });
}

/**
 * Associe les rendements physiques de référence d'un État américain (lorsque disponibles via NASS)
 * aux écarts relatifs (%) de `pairMatrix` (sous l'hypothèse de proportionnalité relative 1:1 entre
 * anomalie de vigueur au pic estival et anomalie de rendement autour de la moyenne de l'État).
 */
export function calibratePairMatrixWithNassYields(pairMatrix, nassYields) {
  if (!nassYields?.available || !nassYields?.stateAlpha || !pairMatrix?.pairs) {
    return pairMatrix;
  }

  const meanYieldByCrop = {};
  for (const [cropId, yearMap] of Object.entries(nassYields.yieldsByCropYear || {})) {
    const vals = Object.values(yearMap);
    if (vals.some((v) => !Number.isFinite(v) || v < 0)) {
      throw new RangeError(
        `Rendement NASS invalide pour ${cropId} : valeur finie non négative attendue.`,
      );
    }
    if (vals.length > 0) {
      const meanNative = vals.reduce((sum, value) => sum + value / vals.length, 0);
      const meta = NASS_COMMODITY_MAP[cropId];
      const meanTonnesPerHa = meanNative * (meta?.toTonnesPerHa || 1);
      if (!Number.isFinite(meanNative) || !Number.isFinite(meanTonnesPerHa)) {
        throw new RangeError(`Conversion NASS non finie pour ${cropId}.`);
      }
      meanYieldByCrop[cropId] = {
        meanNative: Number(meanNative.toFixed(2)),
        nativeUnit: meta?.unit_desc || 'UNIT / ACRE',
        meanTonnesPerHa: Number(meanTonnesPerHa.toFixed(2)),
      };
    }
  }

  for (const stat of Object.values(pairMatrix.pairs)) {
    const ref = meanYieldByCrop[stat.to];
    if (!ref) continue;
    const deltaFactor = validatePhysicalEffectPct(stat.meanEffectPct) / 100;
    const expectedTonnesPerHa = ref.meanTonnesPerHa * (1 + deltaFactor);
    const deltaNative = ref.meanNative * deltaFactor;
    if (!Number.isFinite(expectedTonnesPerHa) || !Number.isFinite(deltaNative)) {
      throw new RangeError('Estimation NASS non finie.');
    }
    stat.calibratedYield = {
      nature: 'conditional_yield_estimate',
      empiricallyCalibrated: false,
      assumption: 'relative_vigor_anomaly_equals_relative_yield_anomaly',
      relativeVigorToYieldSlope: 1,
      stateAlpha: nassYields.stateAlpha,
      calibrationMethod: 'linear_proportional_to_state_mean',
      baselineTonnesPerHa: ref.meanTonnesPerHa,
      deltaTonnesPerHa: Number((ref.meanTonnesPerHa * deltaFactor).toFixed(3)),
      expectedTonnesPerHa: Number(expectedTonnesPerHa.toFixed(2)),
      baselineNative: ref.meanNative,
      deltaNative: Number(deltaNative.toFixed(2)),
      nativeUnit: ref.nativeUnit,
    };
  }

  return pairMatrix;
}
