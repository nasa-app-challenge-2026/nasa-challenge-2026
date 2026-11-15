/** Capture the corrected JavaScript engine as a language-migration oracle (tests only). */
import { mkdirSync, writeFileSync } from 'node:fs';
import { computeRegionalPairMatrix, buildTransitionObservations } from '../algo-rendement/engine/pairTransitions.js';
import { evaluateRotationYieldFromPairs, findBestMultiCropRotationsForYield } from '../algo-rendement/engine/yieldOptimizer.js';
import { blendPairEffectForSeason, forecastFutureRotationYield, findClimateTwin } from '../algo-rendement/engine/climateTwins.js';
import { computeClimateBaselineStats, recalibrateSeasonsWithBaseline } from '../algo-rendement/sources/nasaCmip6Projection.js';

const cases = [];
const capture = (operation, input, fn) => cases.push({ operation, input, expected: fn(input) });
const season = (year, shift = 0) => ({ year, meanTempC: 18 + shift, gddBase10: 1000 + 100 * shift, heatStressDays: 5 + shift, precipMm: 500 - 30 * shift, soilMoistureRoot: 0.55, regime: 'normal', rainZScore: -shift / 2, tempZScore: shift / 2 });
const historical = Array.from({ length: 7 }, (_, i) => season(2018 + i, (i % 3) - 1));
const baseline = computeClimateBaselineStats(historical);
const twinBaseline = { ...baseline, means: { ...baseline.means, gddBase10: 1500, meanTempC: 22 } };
const projected = recalibrateSeasonsWithBaseline(Array.from({ length: 14 }, (_, i) => season(2027 + i, 0.5 + i / 10)), baseline);
const stat = (meanEffectPct, years = 6) => {
  const evidence = { meanEffectPct, intervalPct: [meanEffectPct - 2, meanEffectPct + 2], stdErrorPct: 2, sampleCount: 30, effectiveYearsCount: years };
  return { ...evidence, confidence: 'elevee', byRegime: { normal: { ...evidence }, sec: { ...evidence, meanEffectPct: meanEffectPct - 1, intervalPct: [meanEffectPct - 3, meanEffectPct + 1] }, chaud: null } };
};
const crops = ['mais', 'soya', 'ble', 'patate', 'luzerne'];
const matrix = { pairs: Object.fromEntries(crops.flatMap((a, i) => crops.map((b, j) => [`${a}>${b}`, stat(i === j ? -5 : (i + j) % 7)]))) };
const twin = { ...matrix, pairs: { ...matrix.pairs, 'mais>soya': stat(10, 1) } };
const twinMatch = { bestTwin: { pairMatrix: twin, baselineStats: twinBaseline, distance: 0.7 } };
capture('baseline', historical, computeClimateBaselineStats);
capture('recalibrate', { seasons: projected, baseline }, ({ seasons, baseline: b }) => recalibrateSeasonsWithBaseline(seasons, b));
for (const currentCrop of [null, 'mais', 'patate']) {
  for (const offset of [0, -1, 7]) {
    capture('evaluate', { rotation: [{ crop: 'mais', years: 1 }, { crop: 'soya', years: 1 }], pairMatrix: matrix, currentCrop, offset }, evaluateRotationYieldFromPairs);
  }
}
capture('evaluate', { rotation: [{ crop: 'luzerne', years: 3 }, { crop: 'mais', years: 1 }], pairMatrix: matrix, currentCrop: 'mais' }, evaluateRotationYieldFromPairs);
capture('evaluate', { rotation: [{ crop: 'mais', years: 1 }], pairMatrix: { pairs: { 'soya>mais': stat(-99) } } }, evaluateRotationYieldFromPairs);
for (const alpha of [0, 0.25, 1]) {
  capture('blend', { pairKey: 'mais>soya', projectedSeason: projected[0], alpha, localPairMatrix: matrix, twinPairMatrix: twin, localBaselineStats: baseline, twinBaselineStats: twinBaseline }, blendPairEffectForSeason);
}
for (const currentCrop of [null, 'mais']) {
  capture('forecast', { rotation: [{ crop: 'luzerne', years: 3 }, { crop: 'mais', years: 1 }], currentCrop, projectedSeasons: projected, localPairMatrix: matrix, localBaselineStats: baseline, twinMatch, historicalConfidence: 'moyenne' }, forecastFutureRotationYield);
}
capture('optimize', { pairMatrix: matrix, cycleYears: 4, currentCrop: 'patate', availableCrops: ['mais', 'soya', 'ble', 'patate'], topK: 10 }, findBestMultiCropRotationsForYield);
capture('optimize', { pairMatrix: matrix, cycleYears: 4, currentCrop: 'mais', availableCrops: ['mais', 'soya', 'luzerne'], projectedSeasons: projected, localBaselineStats: baseline, twinMatch }, findBestMultiCropRotationsForYield);
const bbox = { minLon: -73, minLat: 45, maxLon: -72.9, maxLat: 45.1 };
const cropIdsByYear = {}, gridsByYear = {};
for (let year = 2018; year <= 2024; year++) {
  cropIdsByYear[year] = Array.from({ length: 16 }, (_, i) => i % 3 === 0 ? 'mais' : year % 2 ? 'soya' : 'mais');
  gridsByYear[year] = { pixels: Array.from({ length: 16 }, (_, i) => 0.5 + (i % 4) / 20 + (year % 2) / 10) };
}
const input = { ndviSeries: { bbox, nrows: 4, ncols: 4, gridsByYear }, cropHistory: { bbox, gridSize: 4, cropIdsByYear }, climateSeasons: historical };
capture('observations', input, buildTransitionObservations);
capture('matrix', buildTransitionObservations(input), computeRegionalPairMatrix);
const candidates = [{ id: 'warm', name: 'Warm reference', coordinates: { lat: 42, lon: -94 }, baselineStats: twinBaseline, pairMatrix: twin }];
capture('twin', { projectedSeasons: projected, localBaselineStats: baseline, candidateRegions: candidates, farmCoordinates: { lat: 45, lon: -73 } }, findClimateTwin);
mkdirSync('api/tests/fixtures', { recursive: true });
writeFileSync('api/tests/fixtures/yield_js_parity.json', JSON.stringify({ generatedBy: 'scripts/yield-parity-fixtures.mjs', purpose: 'Synthetic regression inputs; never production data', cases }, null, 2) + '\n');
console.log(`${cases.length} JavaScript reference cases captured.`);
