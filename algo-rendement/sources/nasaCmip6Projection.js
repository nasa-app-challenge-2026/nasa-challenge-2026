/**
 * Source 5 : Projections climatiques futures NASA NEX-GDDP-CMIP6 (via NASA POWER Projection API).
 *
 * Permet de projeter année par année (ex. 2027 à 2050) l'évolution agro-climatique de la ferme
 * sous les scénarios officiels du GIEC / CMIP6 :
 * - `ssp126` : Réchauffement modéré (forçage 2.6 W/m²)
 * - `ssp245` : Trajectoire intermédiaire (forçage 4.5 W/m², défaut)
 * - `ssp370` : Réchauffement fort (forçage 7.0 W/m²)
 *
 * ZÉRO simulation synthétique ou constante inventée : toutes les séries proviennent
 * de l'API officielle `power.larc.nasa.gov/api/projection/daily/point` (NEX-GDDP-CMIP6).
 */
import { CONFIG } from '../config.js';
import { summarizeGrowingSeasons } from './nasaPower.js';
import { validateClimateSeasons } from './climateValidation.js';
import { readBoundedJson, readCache, regionCellKey, writeCache } from './cache.js';

const POWER_PROJECTION_ENDPOINT = 'https://power.larc.nasa.gov/api/projection/daily/point';

/** Liste blanche stricte des scénarios CMIP6 autorisés */
const ALLOWED_SCENARIOS = new Set(['ssp126', 'ssp245', 'ssp370']);
const SAFE_MODEL_RE = /^[A-Za-z0-9_-]{1,40}$/;

/**
 * Calcule les statistiques de référence historiques (moyenne, écart-type, quartiles)
 * d'une série de saisons `historicalSeasons` (issue de `fetchNasaPowerSeries`).
 */
export function computeClimateBaselineStats(historicalSeasons) {
  validateClimateSeasons(historicalSeasons);
  const n = historicalSeasons.length;
  if (n === 0) {
    throw new Error('Aucune saison historique disponible pour établir la référence climatique.');
  }

  const meanOf = (arr) => arr.reduce((a, b) => a + b, 0) / arr.length;
  const stdOf = (arr, m) =>
    Math.sqrt(arr.reduce((a, b) => a + (b - m) ** 2, 0) / Math.max(1, arr.length - 1)) || 1;

  const gdds = historicalSeasons.map((s) => s.gddBase10);
  const temps = historicalSeasons.map((s) => s.meanTempC);
  const heats = historicalSeasons.map((s) => s.heatStressDays);
  const rains = historicalSeasons.map((s) => s.precipMm);
  const roots = historicalSeasons
    .map((s) => s.soilMoistureRoot)
    .filter((v) => Number.isFinite(v) && v >= 0 && v <= 1);

  const sortedRains = [...rains].sort((a, b) => a - b);
  const sortedTemps = [...temps].sort((a, b) => a - b);

  const meanGdd = meanOf(gdds);
  const meanTemp = meanOf(temps);
  const meanHeat = meanOf(heats);
  const meanRain = meanOf(rains);
  const meanRoot = roots.length > 0 ? meanOf(roots) : 0.5;

  const stdGdd = stdOf(gdds, meanGdd);
  const stdTemp = stdOf(temps, meanTemp);
  const stdHeat = stdOf(heats, meanHeat);
  const stdRain = stdOf(rains, meanRain);

  const years = historicalSeasons.map((s) => s.year);
  const meanYear = meanOf(years);
  const sYY = years.reduce((a, y) => a + (y - meanYear) ** 2, 0) || 1;
  const gddSlopePerYear =
    years.reduce((a, y, i) => a + (y - meanYear) * (gdds[i] - meanGdd), 0) / sYY;
  const tempSlopePerYear =
    years.reduce((a, y, i) => a + (y - meanYear) * (temps[i] - meanTemp), 0) / sYY;

  return {
    period: {
      startYear: Math.min(...years),
      endYear: Math.max(...years),
      yearsCount: n,
    },
    means: {
      gddBase10: Number(meanGdd.toFixed(1)),
      meanTempC: Number(meanTemp.toFixed(2)),
      heatStressDays: Number(meanHeat.toFixed(1)),
      precipMm: Number(meanRain.toFixed(1)),
      soilMoistureRoot: Number(meanRoot.toFixed(3)),
    },
    stds: {
      gddBase10: Number(stdGdd.toFixed(1)),
      meanTempC: Number(stdTemp.toFixed(2)),
      heatStressDays: Number(stdHeat.toFixed(1)),
      precipMm: Number(stdRain.toFixed(1)),
    },
    thresholds: {
      p25RainMm: sortedRains[Math.floor(n * 0.25)],
      p75TempC: sortedTemps[Math.floor(n * 0.75)],
    },
    observedTrends: {
      gddPerDecade: Number((gddSlopePerYear * 10).toFixed(1)),
      tempCPerDecade: Number((tempSlopePerYear * 10).toFixed(2)),
    },
  };
}

/**
 * Classifie une saison projetée `{ meanTempC, precipMm }` en régime ('normal', 'sec', 'chaud')
 * par rapport aux seuils d'une région de référence (`baselineStats.thresholds`).
 */
export function classifySeasonAgainstBaseline(season, baselineStats) {
  const { thresholds } = baselineStats;
  if (season.precipMm <= thresholds.p25RainMm) return 'sec';
  if (season.meanTempC >= thresholds.p75TempC) return 'chaud';
  return 'normal';
}

/**
 * Recalcule l'ensemble des anomalies, Z-scores, régimes et dérives séculaires d'un tableau de saisons
 * par rapport à `baselineStats` (utilisé à la fois lors du téléchargement et lors d'un hit de cache,
 * garantissant qu'aucun champ dérivé en cache ne reste périmé si `baselineStats` change).
 */
export function recalibrateSeasonsWithBaseline(rawSeasons, baselineStats) {
  const n = rawSeasons?.length || 0;
  if (n === 0) return [];
  const { means, stds } = baselineStats;

  const sorted = [...rawSeasons].sort((a, b) => a.year - b.year);
  validateClimateSeasons(sorted);

  return sorted.map((s) => {
    const rainZScore = Number(((s.precipMm - means.precipMm) / stds.precipMm).toFixed(2));
    const tempZScore = Number(((s.meanTempC - means.meanTempC) / stds.meanTempC).toFixed(2));
    const regime = classifySeasonAgainstBaseline(s, baselineStats);

    return {
      year: s.year,
      meanTempC: s.meanTempC,
      gddBase10: s.gddBase10,
      heatStressDays: s.heatStressDays,
      precipMm: s.precipMm,
      rainZScore,
      tempZScore,
      deltaGddVsBaseline: Number((s.gddBase10 - means.gddBase10).toFixed(1)),
      deltaTempCVsBaseline: Number((s.meanTempC - means.meanTempC).toFixed(2)),
      secularDeltaGdd: Number(Math.max(0, s.gddBase10 - means.gddBase10).toFixed(1)),
      secularDeltaTempC: Number(Math.max(0, s.meanTempC - means.meanTempC).toFixed(2)),
      regime,
    };
  });
}

/**
 * Résume les saisons futures (mai–septembre) depuis les séries quotidiennes NASA POWER Projection.
 */
function summarizeProjectedSeasons(parametersByDate, baselineStats) {
  return recalibrateSeasonsWithBaseline(summarizeGrowingSeasons(parametersByDate), baselineStats);
}

function unwrapScenarioParam(paramObj, scenario) {
  if (
    !paramObj ||
    !Object.hasOwn(paramObj, scenario) ||
    !paramObj[scenario] ||
    typeof paramObj[scenario] !== 'object'
  ) {
    throw new Error(`Scénario ${scenario} absent de la réponse NASA POWER Projection.`);
  }
  return paramObj[scenario];
}

/**
 * Récupère les saisons projetées (`startYear` à `endYear`) pour `(lat, lon)` selon `scenario`
 * (`ssp126`, `ssp245`, `ssp370`) depuis l'API officielle NASA POWER Projection (`NEX-GDDP-CMIP6`).
 */
export async function fetchFutureClimateProjection({
  lat,
  lon,
  historicalSeasons,
  startYear = 2027,
  endYear = 2040,
  scenario = 'ssp245',
  model = 'ensemble',
}) {
  const cleanScenario = String(scenario || 'ssp245').toLowerCase();
  if (!ALLOWED_SCENARIOS.has(cleanScenario)) {
    throw new Error(
      `Scénario CMIP6 invalide : "${scenario}". Valeurs autorisées : ${[...ALLOWED_SCENARIOS].join(', ')}`,
    );
  }
  const cleanModel = String(model || 'ensemble');
  if (!SAFE_MODEL_RE.test(cleanModel)) {
    throw new Error(`Identifiant de modèle CMIP6 invalide : "${model}"`);
  }

  const sYear = Number(startYear);
  const eYear = Number(endYear);
  if (
    !Number.isInteger(sYear) ||
    !Number.isInteger(eYear) ||
    sYear < 2015 ||
    eYear > 2100 ||
    eYear < sYear ||
    eYear - sYear > 80
  ) {
    throw new RangeError(`Plage d'années de projection invalide : ${startYear}–${endYear}`);
  }

  const baselineStats = computeClimateBaselineStats(historicalSeasons);
  const cacheKey = `cmip6_${regionCellKey(lat, lon, 0.25)}_${cleanScenario}_${cleanModel}_${sYear}_${eYear}`;
  const cached = readCache('cmip6-projection', cacheKey, (d) => {
    validateClimateSeasons(d.projectedSeasons, { startYear: sYear, endYear: eYear });
    return d.scenario === cleanScenario && d.model === cleanModel;
  });
  if (cached) {
    return {
      ...cached,
      baselineStats,
      projectedSeasons: recalibrateSeasonsWithBaseline(cached.projectedSeasons, baselineStats),
      fromCache: true,
    };
  }

  const params = new URLSearchParams({
    parameters: 'T2M,T2M_MAX,T2M_MIN,PRECTOTCORR',
    community: 'AG',
    longitude: String(lon),
    latitude: String(lat),
    start: `${sYear}0101`,
    end: `${eYear}1231`,
    model: cleanModel,
    scenario: cleanScenario,
    'time-standard': 'UTC',
    format: 'JSON',
  });

  const url = `${POWER_PROJECTION_ENDPOINT}?${params.toString()}`;
  const res = await fetch(url, {
    headers: { Accept: 'application/json' },
    signal: AbortSignal.timeout(CONFIG.httpTimeoutMs),
  });

  if (!res.ok) {
    throw new Error(
      `NASA POWER Projection API (NEX-GDDP-CMIP6) a répondu HTTP ${res.status} sur ${url}`,
    );
  }

  const raw = await readBoundedJson(res);
  const p = raw?.properties?.parameter;
  if (!p) {
    throw new Error('Réponse NASA POWER Projection API invalide : properties.parameter manquant.');
  }

  const unwrapped = {
    T2M: unwrapScenarioParam(p.T2M, cleanScenario),
    T2M_MAX: unwrapScenarioParam(p.T2M_MAX, cleanScenario),
    T2M_MIN: unwrapScenarioParam(p.T2M_MIN, cleanScenario),
    PRECTOTCORR: unwrapScenarioParam(p.PRECTOTCORR, cleanScenario),
  };
  const projectedSeasons = validateClimateSeasons(
    summarizeProjectedSeasons(unwrapped, baselineStats),
    { startYear: sYear, endYear: eYear },
  );
  if (projectedSeasons.length === 0) {
    throw new Error(
      `Aucune saison estivale projetée retournée par NASA NEX-GDDP-CMIP6 pour (${lat}, ${lon}) sur ${sYear}–${eYear}.`,
    );
  }

  const payload = {
    source: `NASA POWER Projection API (NEX-GDDP-CMIP6 · ${cleanModel} · ${cleanScenario})`,
    nature: 'model_projection',
    scenario: cleanScenario,
    model: cleanModel,
    coordinates: { lat: Number(lat), lon: Number(lon) },
    period: { startYear: sYear, endYear: eYear },
    baselineStats,
    projectedSeasons,
  };
  return writeCache('cmip6-projection', cacheKey, payload);
}
