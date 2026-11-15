import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  buildTransitionObservations,
  computeRegionalPairMatrix,
} from '../engine/pairTransitions.js';
import {
  physicalEffectInterval,
  relativeGainPct,
  resolvePairEvidence,
} from '../engine/modelUtils.js';
import { blendPairEffectForSeason, forecastFutureRotationYield } from '../engine/climateTwins.js';
import { calibratePairMatrixWithNassYields } from '../sources/nassQuickStats.js';
import { evaluateRotationYieldFromPairs } from '../engine/yieldOptimizer.js';

const season = (year, regime = 'normal', precipMm = 500) => ({
  year,
  regime,
  precipMm,
  meanTempC: 20,
  gddBase10: 1000,
  heatStressDays: 5,
});
const baseline = {
  means: { precipMm: 500, soilMoistureRoot: 0.55, gddBase10: 1000 },
  stds: { precipMm: 50 },
  period: { endYear: 2024 },
};
const evidence = (meanEffectPct, overrides = {}) => ({
  meanEffectPct,
  intervalPct: [meanEffectPct - 1, meanEffectPct + 1],
  stdErrorPct: 1,
  sampleCount: 30,
  effectiveYearsCount: 6,
  confidence: 'elevee',
  ...overrides,
});
const blend = (pairStat, options = {}) =>
  blendPairEffectForSeason({
    pairKey: 'soya>mais',
    projectedSeason: season(2027),
    alpha: 0,
    localPairMatrix: { pairs: { 'soya>mais': pairStat } },
    localBaselineStats: baseline,
    ...options,
  });

test('la correction météo conserve des effets physiques avec un historique spatial cohérent', () => {
  const gridSize = 16;
  const bbox = { minLon: -73, minLat: 45, maxLon: -72.9, maxLat: 45.1 };
  const slots = [];
  for (let row = 0; row < gridSize; row++)
    for (let col = 0; col < gridSize; col++)
      if ((row + col) % 2 === 0) slots.push(row * gridSize + col);
  const cropIdsByYear = {};
  const gridsByYear = {};
  const climateSeasons = [];
  for (let year = 2018; year <= 2024; year++) {
    const wet = year % 2 === 1;
    const crops = Array(gridSize ** 2).fill(null);
    const pixels = Array(gridSize ** 2).fill(null);
    for (let field = 0; field < 100; field++) {
      const rotates = field >= 90;
      crops[slots[field]] = rotates && !wet ? 'soya' : 'mais';
      pixels[slots[field]] = rotates ? (wet ? 0.09 : 0.6) : wet ? 0.9 : 0.1;
    }
    cropIdsByYear[year] = crops;
    gridsByYear[year] = { pixels };
    climateSeasons.push({
      ...season(year, wet ? 'normal' : 'sec'),
      rainZScore: wet ? 1.15 : -0.87,
      tempZScore: 0,
    });
  }
  const observations = buildTransitionObservations({
    cropHistory: { bbox, gridSize, cropIdsByYear },
    ndviSeries: { bbox, nrows: gridSize, ncols: gridSize, gridsByYear },
    climateSeasons,
  });
  assert.equal(observations.length, 600);
  const matrix = computeRegionalPairMatrix(observations);
  const affected = matrix.pairs['soya>mais'];
  assert.equal(affected.sampleCount, 30);
  assert.ok(affected.meanEffectPct > -100 && affected.meanEffectPct < 0);
  assert.equal(matrix.weatherAdjustmentMethod, 'centered_log_ridge');
  for (const pairStat of Object.values(matrix.pairs)) {
    for (const stat of [pairStat, ...Object.values(pairStat.byRegime).filter(Boolean)]) {
      assert.ok(Number.isFinite(stat.meanEffectPct) && stat.meanEffectPct >= -100);
      assert.ok(stat.intervalPct[0] >= -100);
      assert.ok(stat.intervalPct.every(Number.isFinite));
      assert.ok(stat.intervalPct[0] <= stat.meanEffectPct);
      assert.ok(stat.intervalPct[1] >= stat.meanEffectPct);
    }
  }
});

test('la correction météo ne dépend pas du centrage initial des covariables', () => {
  const observations = [];
  for (const year of [2023, 2024]) {
    for (let field = 0; field < 90; field++) {
      const prevCrop = field < 45 ? 'mais' : 'soya';
      observations.push({
        fieldId: field + 1,
        currYear: year,
        prevCrop,
        currCrop: 'mais',
        pairKey: `${prevCrop}>mais`,
        isMonoculture: prevCrop === 'mais',
        ndvi: (prevCrop === 'mais' ? 0.25 : 0.3) * (year === 2023 ? 1 : 1.5),
        climate: { rainZScore: year === 2023 ? 1 : 2, tempZScore: 0, regime: 'normal' },
      });
    }
  }
  const original = computeRegionalPairMatrix(observations);
  const shifted = computeRegionalPairMatrix(
    observations.map((o) => ({
      ...o,
      climate: { ...o.climate, rainZScore: o.climate.rainZScore + 5 },
    })),
  );
  for (const key of Object.keys(original.pairs)) {
    assert.equal(original.pairs[key].meanEffectPct, shifted.pairs[key].meanEffectPct);
    assert.equal(original.pairs[key].gainVsMonoculturePct, shifted.pairs[key].gainVsMonoculturePct);
  }
});

test('les observations et covariables invalides sont refusées avant estimation', () => {
  for (const ndvi of [NaN, Infinity, -0.1, 0, 1.1]) {
    assert.throws(() => computeRegionalPairMatrix([{ ndvi }]), /vigueur invalide/);
  }
  assert.throws(
    () => computeRegionalPairMatrix([{ ndvi: 0.5, climate: { rainZScore: Infinity } }]),
    /Covariable météo invalide/,
  );
});

test('les moyennes impossibles sont rejetées, seules les enveloppes sont tronquées', () => {
  for (const mean of [-100.01, NaN, Infinity]) {
    assert.throws(() => resolvePairEvidence(evidence(mean)), RangeError);
    assert.throws(() => blend(evidence(mean)), RangeError);
  }
  const atBoundary = resolvePairEvidence(evidence(-100, { intervalPct: [-110, -90] }));
  assert.equal(atBoundary.meanEffectPct, -100);
  assert.deepEqual(atBoundary.intervalPct, [-100, -90]);
  assert.deepEqual(physicalEffectInterval(20, [-150, 250]), [-100, 250]);
  assert.throws(() => physicalEffectInterval(20, [0, Infinity]), /Intervalle/);
  assert.equal(blend(evidence(150)).meanEffectPct, 150);
  assert.equal(relativeGainPct(150, 0), 150);
  assert.equal(relativeGainPct(-100, 0), -100);
  assert.equal(relativeGainPct(0, -100), null);
  assert.throws(() => relativeGainPct(-101, 0), RangeError);
});

test('le stress ne peut extrapoler une perte de -160 % et les cas valides sont conservés', () => {
  const normal = evidence(0);
  const dry = evidence(-80);
  const pairStat = evidence(-40, { byRegime: { normal, sec: dry } });
  assert.throws(
    () => blend(pairStat, { projectedSeason: season(2027, 'sec', 500 - 50 / 0.15) }),
    /Extrapolation du stress climatique/,
  );
  assert.equal(blend(pairStat, { projectedSeason: season(2027, 'sec') }).meanEffectPct, -80);
  const unchanged = blend(evidence(10));
  assert.equal(unchanged.meanEffectPct, 10);
  assert.deepEqual(unchanged.intervalPct, [9, 11]);
});

test('la modulation prend aussi en compte la confiance du régime normal utilisé', () => {
  const pairStat = evidence(-20, {
    byRegime: {
      normal: evidence(0, { sampleCount: 5, effectiveYearsCount: 1 }),
      sec: evidence(-20),
    },
  });
  const result = blend(pairStat, { projectedSeason: season(2027, 'sec', 450) });
  assert.equal(result.confidence, 'faible');
  assert.equal(result.sampleCount, 5);
  assert.equal(result.effectiveYearsCount, 1);
});

test('une source de poids nul ne déclenche ni extrapolation ni validation inutilisée', () => {
  const impossible = evidence(-40, {
    byRegime: { normal: evidence(0), sec: evidence(-80) },
  });
  const valid = evidence(10);
  const projectedSeason = season(2027, 'sec', 500 - 50 / 0.15);
  const twinPairMatrix = { pairs: { 'soya>mais': impossible } };
  assert.equal(blend(valid, { projectedSeason, alpha: 0, twinPairMatrix }).meanEffectPct, 10);
  assert.equal(
    blend(impossible, {
      projectedSeason,
      alpha: 1,
      twinPairMatrix: { pairs: { 'soya>mais': valid } },
    }).meanEffectPct,
    10,
  );
  assert.throws(
    () => blend(impossible, { projectedSeason, alpha: 0.5, twinPairMatrix }),
    RangeError,
  );
});

test('les paires inconnues et les enveloppes futures restent dans le domaine physique', () => {
  assert.throws(() => blend(null, { unobservedPenaltyPct: -101 }), /Pénalité/);
  const unknown = blend(null, { unobservedPenaltyPct: -100 });
  assert.equal(unknown.meanEffectPct, -100);
  assert.equal(unknown.intervalPct[0], -100);
  const forecast = forecastFutureRotationYield({
    rotation: [{ crop: 'mais', years: 1 }],
    localPairMatrix: {
      pairs: { 'mais>mais': evidence(-99, { stdErrorPct: 20, intervalPct: [-119, -79] }) },
    },
    projectedSeasons: [season(2027), season(2028)],
    localBaselineStats: baseline,
  });
  assert.equal(forecast.meanFutureYieldGainPct, -99);
  assert.equal(forecast.futureYieldGainRangePct[0], -100);
  assert.ok(forecast.yearlyForecast.every((s) => s.intervalPct[0] === -100));
});

test('une paire historique inconnue conserve aussi une enveloppe physiquement possible', () => {
  const result = evaluateRotationYieldFromPairs({
    rotation: [{ crop: 'mais', years: 1 }],
    pairMatrix: { pairs: { 'soya>mais': evidence(-99, { intervalPct: [-100, -90] }) } },
  });
  assert.equal(result.meanYieldGainPct, -99);
  assert.equal(result.observedShare, 0);
  assert.equal(result.transitions[0].intervalPct[0], -100);
  assert.equal(result.yieldGainRangePct[0], -100);
});

test('NASS refuse les entrées impossibles et préserve zéro rendement et les hausses >100 %', () => {
  const nass = { available: true, stateAlpha: 'IA', yieldsByCropYear: { mais: { 2024: 200 } } };
  for (const meanEffectPct of [-101, NaN, Infinity]) {
    assert.throws(
      () =>
        calibratePairMatrixWithNassYields({ pairs: { test: { to: 'mais', meanEffectPct } } }, nass),
      RangeError,
    );
  }
  const matrix = {
    pairs: {
      zero: { to: 'mais', meanEffectPct: -100 },
      increase: { to: 'mais', meanEffectPct: 150 },
    },
  };
  calibratePairMatrixWithNassYields(matrix, nass);
  assert.equal(matrix.pairs.zero.calibratedYield.expectedTonnesPerHa, 0);
  assert.equal(matrix.pairs.increase.calibratedYield.expectedTonnesPerHa, 31.38);
  assert.equal(matrix.pairs.increase.calibratedYield.empiricallyCalibrated, false);
  for (const invalid of [-1, Infinity, NaN]) {
    assert.throws(
      () =>
        calibratePairMatrixWithNassYields(matrix, {
          ...nass,
          yieldsByCropYear: { mais: { 2024: invalid } },
        }),
      /Rendement NASS invalide/,
    );
  }
});
