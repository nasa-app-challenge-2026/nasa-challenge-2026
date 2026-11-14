/**
 * Step 9b, the score of a chain: 9 criteria from 0 to 1, then their weighted mean on 100.
 *
 *   rendement     precrop values (step 7) of each succession, from the crop in place to
 *                 the return to the start of the cycle; same crop twice = 0 %; unknown
 *                 value = 0 % and a gap is reported. −16 %…+16 % become 0…1.
 *   erosion       share of the time the soil is covered by a living crop (covers included)
 *   eau, fourrage, azote, matiere_org   sheet values weighted by the time each crop holds the field
 *   marche        mean of the sold crops (a perennial counts once per year)
 *   ravageurs     return delays (see ReturnDelayChecker.pestScore)
 *   reserve       share of the sowings of the 1st cycle made with seeds the farmer owns;
 *                 the other seeds are listed "to buy"
 * An unknown criterion is left out of the mean.
 */
import { ROLE } from '../../../data/reference/crops.js';
import { CRITERIA_IDS } from '../../../data/reference/criteria.js';
import { MIN_DURATION_MONTHS, PRECROP_VALUE_RANGE_PCT, SCORE_SCALE } from '../config/scoring.js';
import { clamp01, mean } from '../math/numbers.js';
import { isCover, isSold, sheetOf, toOccupations } from './ChainStep.js';
import { coverCrops } from './CoverCropPlanner.js';

const TIME_WEIGHTED_CRITERIA = ['eau', 'fourrage', 'azote', 'matiere_org'];

/** Precrop values (%) → 0..1 (null when there is no succession at all). */
export function yieldCriterion(values, range = PRECROP_VALUE_RANGE_PCT) {
  return values.length ? clamp01((mean(values) + range) / (2 * range)) : null;
}

/** Chain and covers in harvest order (a cover first on a tie). */
const byHarvest = (steps) =>
  steps
    .map((step, i) => ({ step, i }))
    .sort(
      (a, b) => a.step.harvest - b.step.harvest || isCover(b.step) - isCover(a.step) || a.i - b.i,
    )
    .map(({ step }) => step);

function livingCover(steps, end) {
  return steps
    .filter((s) => s.sowing !== null && sheetOf(s).role !== ROLE.FALLOW)
    .reduce((total, s) => total + (Math.min(s.harvest, end) - s.sowing), 0);
}

function timeWeightedValues(steps, start) {
  let previous = start;
  const spans = steps.map((s) => {
    const span = Math.max(s.harvest - previous, 0);
    previous = s.harvest;
    return { sheet: sheetOf(s), span };
  });
  const total = spans.reduce((t, x) => t + x.span, 0) || MIN_DURATION_MONTHS;
  return Object.fromEntries(
    TIME_WEIGHTED_CRITERIA.map((c) => [
      c,
      spans.reduce((t, x) => t + x.sheet.values[c] * x.span, 0) / total,
    ]),
  );
}

function marketValue(soldSheets) {
  const weights = soldSheets.map((s) => Math.max(s.productionYears, 1));
  const total = weights.reduce((t, w) => t + w, 0);
  return total ? soldSheets.reduce((t, s, i) => t + s.values.marche * weights[i], 0) / total : 0;
}

/** Successions of sold crops, from the crop in place, and back to the start if complete. */
export function successions(crops, entryCropId, complete) {
  const previous = entryCropId ? [entryCropId, ...crops] : crops;
  const pairs = crops
    .map((crop, i) => [previous[entryCropId ? i : i - 1], crop])
    .filter(([a]) => a);
  if (complete && crops.length > 1) pairs.push([crops[crops.length - 1], crops[0]]);
  return pairs;
}

function yieldValues(pairs, evidence) {
  const values = [];
  const gaps = [];
  for (const [previous, next] of pairs) {
    if (previous === next) {
      values.push(0);
      continue;
    }
    const value = evidence.precropValue(previous, next);
    values.push(value ?? 0); // unknown: neutral, and reported
    if (value === null || value === undefined) {
      if (!gaps.some(([a, b]) => a === previous && b === next)) gaps.push([previous, next]);
    }
  }
  return { values, gaps };
}

function reserveShare(steps, reserve) {
  const sown = steps
    .filter((s) => s.sowing !== null && sheetOf(s).role !== ROLE.FALLOW)
    .sort((a, b) => a.sowing - b.sowing);
  const toBuy = [];
  const owned = sown.map((s) => {
    const seed = sheetOf(s).seedId;
    if (!reserve.has(seed) && !toBuy.includes(seed)) toBuy.push(seed);
    return reserve.has(seed) ? 1 : 0;
  });
  return { share: owned.length ? mean(owned) : null, toBuy };
}

/**
 * @typedef {object} ChainScore
 * @property {number} score    0 to 100
 * @property {Record<string, number|null>} criteria
 * @property {[string, string][]} gaps        successions whose precrop value is unknown
 * @property {string[]} seedsToBuy
 * @property {object[]} covers                cover steps placed automatically
 * @property {object[]} warnings              shared soil diseases (complete chains only)
 */

/**
 * @param {ReturnType<import('./ChainStep.js').chainStep>[]} chain
 * @param {import('./CycleContext.js').CycleContext} ctx
 * @param {{ partial?: boolean }} [options] a partial chain is scored up to its last harvest
 * @returns {ChainScore}
 */
export function scoreChain(chain, ctx, { partial = false } = {}) {
  const covers = coverCrops(chain, ctx);
  const steps = byHarvest([...chain, ...covers]);
  const start = ctx.entryHarvest;
  const end = partial ? chain[chain.length - 1].harvest : start + ctx.cycleMonths;
  const duration = Math.max(end - start, MIN_DURATION_MONTHS);

  const sold = chain.filter(isSold);
  const crops = sold.map((s) => sheetOf(s).cropId);
  const { values, gaps } = yieldValues(successions(crops, ctx.entryCropId, !partial), ctx.evidence);
  const occupations = toOccupations(chain, ctx.catalog);
  const reserve = ctx.reserve ? reserveShare(steps, ctx.reserve) : { share: null, toBuy: [] };

  const criteria = {
    rendement: yieldCriterion(values),
    erosion: Math.min(1, livingCover(steps, end) / duration),
    ...timeWeightedValues(steps, start),
    marche: marketValue(sold.map(sheetOf)),
    ravageurs: ctx.delays.pestScore(occupations, { closed: !partial }),
    reserve: reserve.share,
  };
  const known = CRITERIA_IDS.filter((c) => criteria[c] !== null && criteria[c] !== undefined);
  const weightSum = known.reduce((t, c) => t + ctx.weights[c], 0);
  const score =
    (SCORE_SCALE * known.reduce((t, c) => t + ctx.weights[c] * criteria[c], 0)) / weightSum;
  return {
    score,
    criteria,
    gaps,
    seedsToBuy: reserve.toBuy,
    covers,
    warnings: partial ? [] : ctx.delays.sharedDiseaseWarnings(occupations),
  };
}
