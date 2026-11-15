/**
 * Step 1, block D: the farmer's ranking of the four priorities. Only the editing of the list lives
 * here: the weights that come out of it (rank order centroid) are computed by the algorithm and
 * read in the plan (`plan.weights`, with the ranking they were computed from in
 * `plan.settings.priorities`).
 */
import { CRITERIA_IDS } from '../../data/reference/criteria.js';

/** Criteria of the previous version (nine criteria) that are one of the four priorities now. */
const RENAMED = { erosion: 'protection_sol' };

/** Move the priority at `index` by `delta` places. Returns a new ranking. */
export function moveCriterion(ranking, index, delta) {
  const j = index + delta;
  if (index < 0 || j < 0 || j >= ranking.length) return ranking;
  const next = [...ranking];
  [next[index], next[j]] = [next[j], next[index]];
  return next;
}

/**
 * The four priorities in the farmer's order, from any saved ranking. The criteria of the previous
 * version are renamed (érosion → protection du sol) or dropped (fourrage, azote, matière
 * organique, marché, réserve); the priorities missing are added at the end, in the fixed order.
 */
export function normalizePriorities(ranking = []) {
  const ranked = [
    ...new Set(ranking.map((c) => RENAMED[c] ?? c).filter((c) => CRITERIA_IDS.includes(c))),
  ];
  return [...ranked, ...CRITERIA_IDS.filter((c) => !ranked.includes(c))];
}

/**
 * Share (percent) each priority weighs in the plan, or null while the plan does not yet come from
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
