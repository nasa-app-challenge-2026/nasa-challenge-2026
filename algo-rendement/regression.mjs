import assert from 'node:assert/strict';
import './tests/returnDelays.test.mjs';
import './tests/forage.test.mjs';
import './tests/physicalValues.test.mjs';
import { test } from 'node:test';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve, sep } from 'node:path';
import { CONFIG } from './config.js';
import { runRegionalYieldPipeline } from './index.js';
import {
  evaluateRotationYieldFromPairs,
  findBestMultiCropRotationsForYield,
} from './engine/yieldOptimizer.js';
import {
  blendPairEffectForSeason,
  computeYearlyBlendingAlpha,
  forecastFutureRotationYield,
} from './engine/climateTwins.js';
import {
  buildTransitionObservations,
  computeRegionalPairMatrix,
} from './engine/pairTransitions.js';
import {
  computeClimateBaselineStats,
  fetchFutureClimateProjection,
  recalibrateSeasonsWithBaseline,
} from './sources/nasaCmip6Projection.js';
import { summarizeGrowingSeasons } from './sources/nasaPower.js';
import { computeRegionBbox, fetchRegionalNdviSeries } from './sources/nasaModisNdvi.js';
import { fetchRegionalCropHistory } from './sources/cropHistory.js';
import { calibratePairMatrixWithNassYields } from './sources/nassQuickStats.js';
import { bboxCacheKey, readCache, regionCellKey, writeCache } from './sources/cache.js';

const season = (year, gddBase10 = 1000) => ({
  year,
  gddBase10,
  meanTempC: 20,
  heatStressDays: 5,
  precipMm: 500,
  regime: 'normal',
});
const baseline = computeClimateBaselineStats([season(2022), season(2023), season(2024)]);
const twinBaseline = { ...baseline, means: { ...baseline.means, gddBase10: 1500 } };
const rotation = [
  { crop: 'mais', years: 1 },
  { crop: 'soya', years: 1 },
];
function stat(meanEffectPct, sampleCount = 30, effectiveYearsCount = 6) {
  const evidence = {
    meanEffectPct,
    sampleCount,
    effectiveYearsCount,
    stdErrorPct: 1,
    intervalPct: [meanEffectPct - 1, meanEffectPct + 1],
  };
  return {
    ...evidence,
    confidence: sampleCount >= 15 && effectiveYearsCount >= 3 ? 'elevee' : 'faible',
    byRegime: { normal: { ...evidence }, sec: { ...evidence }, chaud: { ...evidence } },
  };
}
const matrix = {
  pairs: {
    'mais>soya': stat(10),
    'soya>mais': stat(0),
    'mais>mais': stat(-10),
    'soya>soya': stat(-10),
  },
};

function isolateSources(
  t,
  fetchImpl = async () => {
    throw new Error('network-disabled');
  },
) {
  const root = resolve(tmpdir());
  const dir = mkdtempSync(join(root, 'fieldshift-regression-'));
  const previous = { cacheDir: CONFIG.cacheDir, fetch: globalThis.fetch };
  CONFIG.cacheDir = dir;
  globalThis.fetch = fetchImpl;
  t.after(() => {
    CONFIG.cacheDir = previous.cacheDir;
    globalThis.fetch = previous.fetch;
    const checked = resolve(dir);
    assert.ok(checked.startsWith(root + sep) && checked !== root);
    rmSync(checked, { recursive: true, force: true });
  });
}

function daily(years = [2027], scenario = 'ssp245') {
  const parameter = Object.fromEntries(
    ['T2M', 'T2M_MAX', 'T2M_MIN', 'PRECTOTCORR'].map((key) => [key, { [scenario]: {} }]),
  );
  for (const year of years) {
    for (
      let day = new Date(`${year}-05-01T00:00:00Z`);
      day < new Date(`${year}-10-01T00:00:00Z`);
      day.setUTCDate(day.getUTCDate() + 1)
    ) {
      const date = day.toISOString().slice(0, 10).replaceAll('-', '');
      for (const key of Object.keys(parameter))
        parameter[key][scenario][date] = key === 'PRECTOTCORR' ? 3 : 20;
    }
  }
  return { properties: { parameter } };
}

test('durées rejetées avant allocation, dans les deux évaluateurs', () => {
  for (const years of [1e12, Infinity, NaN, -1, 0, 1.5, '3']) {
    const bad = [{ crop: 'mais', years }];
    assert.throws(
      () => evaluateRotationYieldFromPairs({ rotation: bad, pairMatrix: matrix }),
      RangeError,
    );
    assert.throws(
      () => forecastFutureRotationYield({ rotation: bad, projectedSeasons: [season(2027)] }),
      RangeError,
    );
  }
  assert.throws(
    () => evaluateRotationYieldFromPairs({ rotation: [{ crop: 'constructor', years: 1 }] }),
    RangeError,
  );
  assert.throws(
    () => evaluateRotationYieldFromPairs({ rotation: [{ crop: 'luzerne', years: 1 }] }),
    RangeError,
  );
});

test('dédupliquer les cultures conserve exactement la recherche et les résultats', () => {
  const options = { pairMatrix: matrix, cycleYears: 6, topK: 50 };
  const unique = findBestMultiCropRotationsForYield({
    ...options,
    availableCrops: ['mais', 'soya'],
  });
  const repeated = findBestMultiCropRotationsForYield({
    ...options,
    availableCrops: Array(100).fill(['mais', 'soya']).flat(),
  });
  assert.deepEqual(repeated, unique);
  assert.equal(new Set(repeated.map((r) => JSON.stringify(r.rotation))).size, repeated.length);
});

test('la culture actuelle remplace la fermeture du cycle sans bonus supplémentaire', () => {
  const best = findBestMultiCropRotationsForYield({
    pairMatrix: matrix,
    cycleYears: 2,
    availableCrops: ['mais', 'soya'],
    currentCrop: 'mais',
  })[0];
  assert.equal(best.rankingScore, 5);
  assert.equal(best.rankingScore, best.meanYieldGainPct);
  const m = { pairs: { 'ble>soya': stat(-10), 'mais>soya': stat(10), 'soya>ble': stat(0) } };
  const r = [
    { crop: 'soya', years: 1 },
    { crop: 'ble', years: 1 },
  ];
  assert.equal(evaluateRotationYieldFromPairs({ rotation: r, pairMatrix: m }).meanYieldGainPct, -5);
  assert.equal(
    evaluateRotationYieldFromPairs({ rotation: r, pairMatrix: m, currentCrop: 'mais' })
      .meanYieldGainPct,
    5,
  );
});

test('les années pérennes participent aux moyennes historique et future', () => {
  const r = [
    { crop: 'luzerne', years: 3 },
    { crop: 'mais', years: 1 },
  ];
  const m = {
    pairs: { 'mais>luzerne': stat(10), 'luzerne>luzerne': stat(-20), 'luzerne>mais': stat(0) },
  };
  const h = evaluateRotationYieldFromPairs({ rotation: r, currentCrop: 'mais', pairMatrix: m });
  const f = forecastFutureRotationYield({
    rotation: r,
    currentCrop: 'mais',
    localPairMatrix: m,
    projectedSeasons: [2027, 2028, 2029, 2030].map((y) => season(y)),
    localBaselineStats: baseline,
  });
  assert.equal(h.transitions.length, 4);
  assert.equal(h.meanYieldGainPct, -7.5);
  assert.equal(f.meanFutureYieldGainPct, -7.5);
  assert.equal(
    f.yearlyForecast.reduce((s, y) => s + y.expectedYieldGainPct, 0) / 4,
    f.meanFutureYieldGainPct,
  );
  assert.equal(f.yearlyForecast.filter((y) => y.isMultiYearContinuation).length, 2);
});

test('comparaison monoculture par ratio et référence manquante explicite', () => {
  const m = { pairs: { ...matrix.pairs, 'soya>mais': stat(10) } };
  const e = evaluateRotationYieldFromPairs({ rotation, pairMatrix: m });
  assert.equal(e.gainVsMonocultureCyclePct, 22.22);
  assert.ok(e.transitions.every((t) => t.gainVsMonoculturePct === 22.22));
  delete m.pairs['mais>mais'];
  assert.equal(
    evaluateRotationYieldFromPairs({ rotation, pairMatrix: m }).gainVsMonocultureCyclePct,
    null,
  );
});

test('une seule année indépendante reste une confiance faible malgré N=20', () => {
  const obs = [];
  for (const [prevCrop, currCrop] of [
    ['mais', 'soya'],
    ['soya', 'mais'],
  ]) {
    for (let i = 0; i < 20; i++)
      obs.push({
        fieldId: obs.length + 1,
        prevCrop,
        currCrop,
        currYear: 2024,
        pairKey: `${prevCrop}>${currCrop}`,
        isMonoculture: false,
        ndvi: 0.6,
        climate: null,
      });
  }
  const m = computeRegionalPairMatrix(obs);
  assert.equal(m.pairs['mais>soya'].confidence, 'faible');
  assert.equal(evaluateRotationYieldFromPairs({ rotation, pairMatrix: m }).confidence, 'faible');
});

test('le même climat annuel donne le même alpha quel que soit l’horizon', () => {
  const project = (start, end) =>
    recalibrateSeasonsWithBaseline(
      Array.from({ length: end - start + 1 }, (_, i) => season(start + i, 1200)),
      baseline,
    ).find((s) => s.year === 2029);
  const alpha = (s) =>
    computeYearlyBlendingAlpha({
      projectedSeason: s,
      localBaselineStats: baseline,
      twinBaselineStats: twinBaseline,
    });
  assert.equal(alpha(project(2027, 2030)), 0.4);
  assert.equal(alpha(project(2027, 2042)), 0.4);
  assert.equal(alpha(project(2029, 2042)), 0.4);
});

test('effet, effectif et confiance suivent les sources de poids non nul', () => {
  const args = {
    pairKey: 'mais>soya',
    projectedSeason: season(2027),
    localPairMatrix: { pairs: { 'mais>soya': stat(2, 100, 6) } },
    twinPairMatrix: { pairs: { 'mais>soya': stat(10, 1, 1) } },
    localBaselineStats: baseline,
    twinBaselineStats: twinBaseline,
  };
  const local = blendPairEffectForSeason({ ...args, alpha: 0 });
  assert.equal(local.meanEffectPct, 2);
  assert.equal(local.sampleCount, 100);
  assert.equal(local.confidence, 'elevee');
  const mixed = blendPairEffectForSeason({ ...args, alpha: 0.5 });
  assert.equal(mixed.meanEffectPct, 6);
  assert.equal(mixed.confidence, 'faible');
  const twin = blendPairEffectForSeason({ ...args, alpha: 1 });
  assert.equal(twin.meanEffectPct, 10);
  assert.equal(twin.sampleCount, 1);
  assert.equal(twin.effectiveYearsCount, 1);
  assert.equal(twin.confidence, 'faible');
});

test('l’incertitude d’une même année utilise la distance à la référence historique', () => {
  const options = {
    rotation: [{ crop: 'mais', years: 1 }],
    localPairMatrix: matrix,
    localBaselineStats: baseline,
  };
  const long = forecastFutureRotationYield({
    ...options,
    projectedSeasons: [2027, 2028, 2029].map((y) => season(y)),
  });
  const short = forecastFutureRotationYield({ ...options, projectedSeasons: [season(2029)] });
  assert.deepEqual(long.yearlyForecast[2].intervalPct, short.yearlyForecast[0].intervalPct);
});

test('une source inconnue reçoit sa pénalité avec son poids réel, des deux côtés', () => {
  const args = {
    pairKey: 'mais>soya',
    projectedSeason: season(2027),
    alpha: 0.5,
    localBaselineStats: baseline,
    twinBaselineStats: twinBaseline,
    unobservedPenaltyPct: -2,
  };
  for (const [localPairMatrix, twinPairMatrix] of [
    [{ pairs: { 'mais>soya': stat(10) } }, { pairs: {} }],
    [{ pairs: {} }, { pairs: { 'mais>soya': stat(10) } }],
  ]) {
    const r = blendPairEffectForSeason({ ...args, localPairMatrix, twinPairMatrix });
    assert.equal(r.meanEffectPct, 4);
    assert.equal(r.observedWeight, 0.5);
    assert.equal(r.confidence, 'faible');
  }
  const r = blendPairEffectForSeason({
    ...args,
    alpha: 1,
    localPairMatrix: { pairs: {} },
    twinPairMatrix: { pairs: { 'mais>soya': stat(10) } },
  });
  assert.equal(r.observed, true);
  assert.equal(r.sampleCount, 30);
});

test('le régime réellement utilisé limite la confiance', () => {
  const s = stat(10, 100, 6);
  s.byRegime.sec = { ...s.byRegime.sec, sampleCount: 20, effectiveYearsCount: 1 };
  assert.equal(
    evaluateRotationYieldFromPairs({
      rotation,
      regime: 'sec',
      pairMatrix: { pairs: { 'mais>soya': s, 'soya>mais': s } },
    }).confidence,
    'faible',
  );
});

test('les arrondis ne placent jamais la moyenne hors de son enveloppe', () => {
  const s = stat(0.04);
  s.stdErrorPct = 0;
  s.intervalPct = [0.04, 0.04];
  s.byRegime = {};
  const f = forecastFutureRotationYield({
    rotation: [{ crop: 'mais', years: 1 }],
    projectedSeasons: [season(2024)],
    localBaselineStats: baseline,
    localPairMatrix: { pairs: { 'mais>mais': s } },
  });
  assert.ok(f.futureYieldGainRangePct[0] <= f.meanFutureYieldGainPct);
  assert.ok(f.futureYieldGainRangePct[1] >= f.meanFutureYieldGainPct);
  assert.ok(f.yearlyForecast[0].intervalPct[1] >= f.yearlyForecast[0].expectedYieldGainPct);
});

test('années manquantes, répétées et désordonnées refusées avant la prévision', () => {
  for (const years of [
    [2027, 2029],
    [2027, 2027],
    [2028, 2027],
  ]) {
    assert.throws(
      () =>
        forecastFutureRotationYield({
          rotation,
          localPairMatrix: matrix,
          projectedSeasons: years.map((y) => season(y)),
          localBaselineStats: baseline,
        }),
      /consécutives/,
    );
  }
});

test('pluie ou températures absentes ne deviennent pas une saison sèche', () => {
  const parameters = daily().properties.parameter;
  const flat = Object.fromEntries(Object.entries(parameters).map(([k, v]) => [k, v.ssp245]));
  assert.equal(summarizeGrowingSeasons(flat)[0].coverage.completeDays, 153);
  assert.deepEqual(summarizeGrowingSeasons({ ...flat, PRECTOTCORR: {} }), []);
  const missingRain = { ...flat.PRECTOTCORR };
  delete missingRain['20270701'];
  assert.deepEqual(summarizeGrowingSeasons({ ...flat, PRECTOTCORR: missingRain }), []);
  assert.deepEqual(summarizeGrowingSeasons({ ...flat, T2M_MAX: {} }), []);
});

test('la requête NASA sélectionne explicitement le bon scénario', async (t) => {
  let request;
  isolateSources(t, async (url) => {
    request = new URL(url);
    return Response.json(daily());
  });
  const r = await fetchFutureClimateProjection({
    lat: 45.6,
    lon: -72.9,
    historicalSeasons: [season(2024)],
    startYear: 2027,
    endYear: 2027,
    scenario: 'ssp245',
  });
  assert.equal(request.searchParams.get('scenario'), 'ssp245');
  assert.equal(request.searchParams.has('scenarios'), false);
  assert.equal(request.searchParams.get('time-standard'), 'UTC');
  assert.equal(r.scenario, 'ssp245');
  assert.equal(r.projectedSeasons.length, 1);
});

test('aucune substitution silencieuse de scénario, y compris ssp585', async (t) => {
  let calls = 0;
  isolateSources(t, async () => {
    calls++;
    return Response.json(daily([2027], 'ssp126'));
  });
  await assert.rejects(
    () =>
      fetchFutureClimateProjection({
        lat: 45.6,
        lon: -72.9,
        historicalSeasons: [season(2024)],
        startYear: 2027,
        endYear: 2027,
        scenario: 'ssp585',
      }),
    /Scénario CMIP6 invalide/,
  );
  assert.equal(calls, 0);
  await assert.rejects(
    () =>
      fetchFutureClimateProjection({
        lat: 45.6,
        lon: -72.9,
        historicalSeasons: [season(2024)],
        startYear: 2027,
        endYear: 2027,
        scenario: 'ssp245',
      }),
    /Scénario ssp245 absent/,
  );
});

test('une réponse NASA partielle ne peut annoncer un horizon complet', async (t) => {
  isolateSources(t, async () => Response.json(daily([2027, 2029])));
  await assert.rejects(
    () =>
      fetchFutureClimateProjection({
        lat: 45.6,
        lon: -72.9,
        historicalSeasons: [season(2024)],
        startYear: 2027,
        endYear: 2029,
      }),
    /consécutives/,
  );
});

test('les caches géographiques refusent une autre emprise, même dans la même cellule', async (t) => {
  isolateSources(t);
  const a = computeRegionBbox(45.6, -72.9),
    b = computeRegionBbox(45.61, -72.9);
  const suffix = `${regionCellKey(45.6, -72.9, 0.05)}_2023_2024_4x4_8km`;
  writeCache('crop-history', `bbox_AAFC_CANADA_${suffix}`, {
    gridSize: 4,
    bbox: a,
    cropIdsByYear: { 2023: Array(16).fill('mais'), 2024: Array(16).fill('soya') },
  });
  await assert.rejects(
    () =>
      fetchRegionalCropHistory({
        lat: 45.6,
        lon: -72.9,
        bbox: b,
        gridSize: 4,
        startYear: 2023,
        endYear: 2024,
      }),
    /network-disabled/,
  );
  writeCache('modis-ndvi', `bbox_${suffix}`, {
    nrows: 4,
    ncols: 4,
    bbox: a,
    gridsByYear: { 2023: { pixels: Array(16).fill(0.6) }, 2024: { pixels: Array(16).fill(0.6) } },
  });
  await assert.rejects(
    () =>
      fetchRegionalNdviSeries({
        lat: 45.61,
        lon: -72.9,
        gridSize: 4,
        startYear: 2023,
        endYear: 2024,
      }),
    /network-disabled/,
  );
  assert.notEqual(bboxCacheKey(a), bboxCacheKey(b));
});

test('un cache aligné reste utilisable sans réseau', async (t) => {
  isolateSources(t);
  const bbox = computeRegionBbox(45.6, -72.9);
  const key = `bbox_AAFC_CANADA_${regionCellKey(45.6, -72.9, 0.05)}_2023_2024_4x4_8km_${bboxCacheKey(bbox)}`;
  writeCache('crop-history', key, {
    gridSize: 4,
    bbox,
    cropIdsByYear: { 2023: Array(16).fill('mais'), 2024: Array(16).fill('soya') },
  });
  const r = await fetchRegionalCropHistory({
    lat: 45.6,
    lon: -72.9,
    bbox,
    gridSize: 4,
    startYear: 2023,
    endYear: 2024,
  });
  assert.equal(r.fromCache, true);
});

test('le contrôle de grille précède le croisement pixel par pixel', () => {
  const bbox = computeRegionBbox(45.6, -72.9);
  const cropHistory = {
    bbox,
    gridSize: 4,
    cropIdsByYear: {
      2023: Array(16).fill('mais'),
      2024: Array(16).fill('soya'),
    },
  };
  const ndviSeries = {
    bbox: computeRegionBbox(45.61, -72.9),
    nrows: 4,
    ncols: 4,
    gridsByYear: { 2024: { pixels: Array(16).fill(0.6) } },
  };
  assert.throws(
    () => buildTransitionObservations({ cropHistory, ndviSeries, climateSeasons: [season(2024)] }),
    /désalignées/,
  );
  ndviSeries.bbox = bbox;
  assert.equal(
    buildTransitionObservations({ cropHistory, ndviSeries, climateSeasons: [season(2024)] }).length,
    1,
  );
  cropHistory.cropIdsByYear[2023] = [];
  assert.deepEqual(
    buildTransitionObservations({ cropHistory, ndviSeries, climateSeasons: [season(2024)] }),
    [],
  );
});

test('les validateurs personnalisés ne contournent pas le schéma du cache', (t) => {
  isolateSources(t);
  writeCache('modis-ndvi', 'corrupt', { nrows: 4, ncols: 4, gridsByYear: null });
  assert.equal(
    readCache('modis-ndvi', 'corrupt', () => true),
    null,
  );
});

test('les paramètres invalides du pipeline sont rejetés avant tout réseau', async (t) => {
  isolateSources(t);
  await assert.rejects(
    () => runRegionalYieldPipeline({ lat: 45.6, lon: -72.9, cycleYears: 1e12 }),
    /cycleYears/,
  );
});

test('la conversion NASS indique son hypothèse sans se présenter comme un ajustement empirique', () => {
  const m = { pairs: { 'soya>mais': { ...stat(10), to: 'mais' } } };
  const r = calibratePairMatrixWithNassYields(m, {
    available: true,
    stateAlpha: 'IA',
    yieldsByCropYear: { mais: { 2024: 200 } },
  });
  assert.equal(r.pairs['soya>mais'].calibratedYield.empiricallyCalibrated, false);
  assert.equal(r.pairs['soya>mais'].calibratedYield.relativeVigorToYieldSlope, 1);
});
