/**
 * Step 1, block D of the algorithm: from the farmer's ranking of the criteria to
 * their weights, with the rank order centroid method. With 5 ranked criteria the
 * weights are 0.46 / 0.26 / 0.16 / 0.09 / 0.04. An unranked criterion keeps a
 * share (25 %) of the smallest weight. The algorithm then adjusts these weights
 * to the risks of each field (backend/algorithm/planning/CriteriaWeights.js).
 */
import { CRITERIA_IDS } from '../../data/reference/criteria.js';
import { UNRANKED_WEIGHT_SHARE } from '../../data/reference/planning.js';

/** Weight of the criterion ranked `rank` (0 = first) among `count` ranked criteria. */
export function rankOrderCentroid(rank, count) {
  let total = 0;
  for (let j = rank + 1; j <= count; j++) total += 1 / j;
  return total / count;
}

/**
 * Weight of every criterion. Without any ranking, all criteria weigh the same.
 * @param {string[]} ranking criterion ids, most important first
 * @returns {Record<string, number>}
 */
export function weightsFromRanking(ranking, unrankedShare = UNRANKED_WEIGHT_SHARE) {
  const ranked = ranking.filter((c, i) => CRITERIA_IDS.includes(c) && ranking.indexOf(c) === i);
  if (!ranked.length) return Object.fromEntries(CRITERIA_IDS.map((c) => [c, 1]));
  const weights = Object.fromEntries(
    ranked.map((c, i) => [c, rankOrderCentroid(i, ranked.length)]),
  );
  const smallest = Math.min(...Object.values(weights));
  return Object.fromEntries(CRITERIA_IDS.map((c) => [c, weights[c] ?? unrankedShare * smallest]));
}

/** Move the criterion at `index` by `delta` places. Returns a new ranking. */
export function moveCriterion(ranking, index, delta) {
  const j = index + delta;
  if (index < 0 || j < 0 || j >= ranking.length) return ranking;
  const next = [...ranking];
  [next[index], next[j]] = [next[j], next[index]];
  return next;
}

/** Criteria the farmer has not ranked, in the fixed order. */
export const unrankedCriteria = (ranking) => CRITERIA_IDS.filter((c) => !ranking.includes(c));
