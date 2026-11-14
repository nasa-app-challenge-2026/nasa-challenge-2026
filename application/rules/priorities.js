/**
 * Step 1, block D: the farmer's ranking of the criteria. Only the editing of the list lives here:
 * the weights that come out of it (rank order centroid) are computed by the algorithm and read in
 * the plan (`plan.weights`, with the ranking they were computed from in `plan.settings.priorities`).
 */
import { CRITERIA_IDS } from '../../data/reference/criteria.js';

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

/**
 * Share (percent) each criterion weighs in the plan, or null while the plan does not yet come from
 * this ranking (it is being computed, or inputs are missing).
 */
export function weightShares(plan, ranking) {
  const computedFor = plan?.settings?.priorities;
  if (!plan?.weights || computedFor?.join() !== ranking.join()) return null;
  const total = Object.values(plan.weights).reduce((a, b) => a + b, 0);
  return Object.fromEntries(
    Object.entries(plan.weights).map(([c, w]) => [c, Math.round((100 * w) / total)]),
  );
}
