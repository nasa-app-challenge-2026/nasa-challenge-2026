/**
 * Reading the plan for the screens: which cycle covers a year, what a section grows
 * that year, what the whole farm grows. No agronomy here: the plan comes from the
 * algorithm (backend/algorithm/); this only finds things in it.
 */
import { FREQUENCIES, MONTHS_PER_YEAR } from '../../data/reference/planning.js';
import { ROLE, SHEETS } from '../../data/reference/crops.js';

const yearOf = (isoDate) => (isoDate ? Number(isoDate.slice(0, 4)) : null);

/** Year of a position (1-based) of a cycle. */
export function positionYear(cycle, position, frequencyMonths) {
  const start = FREQUENCIES.find((f) => f.months === frequencyMonths)?.positionStartMonth ?? 0;
  return cycle.years[0] + Math.floor((start + (position - 1) * frequencyMonths) / MONTHS_PER_YEAR);
}

/** The cycle of a section plan that covers `year`, or null. */
export const cycleOfYear = (sectionPlan, year) =>
  sectionPlan?.cycles.find((c) => year >= c.years[0] && year <= c.years[1]) ?? null;

/** First and last year of the plans of every section. */
export function planYears(plan) {
  const sections = (plan?.sections ?? []).filter((s) => s.firstYear !== null);
  if (!sections.length) return null;
  return {
    first: Math.min(...sections.map((s) => s.firstYear)),
    last: Math.max(...sections.map((s) => s.lastYear)),
  };
}

/** The option of the farmer's current rotation among the rotations of a cycle. */
export const REFERENCE_OPTION = 'ref';

/**
 * The rotations a cycle proposes, best first: the one the algorithm chose, then its alternatives
 * (three in all when the constraints leave that many).
 */
export const proposedRotations = (cycle) =>
  cycle.chosen ? [cycle.chosen, ...cycle.alternatives] : [];

/**
 * The rotation shown in detail: { id, chain } where id is the rank of a proposal (0 = the chosen
 * one) or REFERENCE_OPTION. An option the cycle does not have falls back on the chosen rotation,
 * then on the current one; null when the cycle has neither.
 */
export function shownRotation(cycle, option) {
  const proposals = proposedRotations(cycle);
  if (option === REFERENCE_OPTION && cycle.reference)
    return { id: REFERENCE_OPTION, chain: cycle.reference };
  if (proposals[option]) return { id: option, chain: proposals[option] };
  if (proposals.length) return { id: 0, chain: proposals[0] };
  return cycle.reference ? { id: REFERENCE_OPTION, chain: cycle.reference } : null;
}

/** Steps of a chain that hold a position, with the years they cover. */
export function positionedSteps(chain, cycle, frequencyMonths) {
  return (chain?.steps ?? [])
    .filter((s) => s.positions)
    .map((s) => ({
      ...s,
      fromYear:
        s.kind === 'jachere'
          ? positionYear(cycle, s.positions[0], frequencyMonths)
          : yearOf(s.sowing),
      toYear:
        s.kind === 'jachere'
          ? positionYear(cycle, s.positions[1], frequencyMonths)
          : yearOf(s.harvest),
    }));
}

/**
 * What a section grows in `year`: { id (sheet or crop), source } with source
 * 'plan', 'en-place' (before the first cycle) or null when nothing is known.
 * A sold crop harvested that year wins; then a crop growing that year; then fallow.
 */
export function cropOfYear(section, sectionPlan, year, frequencyMonths) {
  const cycle = cycleOfYear(sectionPlan, year);
  if (!cycle) {
    const freeYear = yearOf(sectionPlan?.freeAt);
    if (section.currentCrop && freeYear !== null && year <= freeYear)
      return { id: section.currentCrop, source: 'en-place' };
    return { id: null, source: null };
  }
  const steps = positionedSteps(cycle.chosen, cycle, frequencyMonths);
  const sold = (s) => SHEETS[s.sheet]?.role === ROLE.SOLD;
  const pick =
    steps.find((s) => sold(s) && s.toYear === year) ??
    steps.find((s) => sold(s) && s.fromYear <= year && s.toYear >= year) ??
    steps.find((s) => s.fromYear <= year && s.toYear >= year);
  return { id: pick?.sheet ?? null, source: 'plan' };
}

/** Area (ha) of each crop on the whole farm in `year`. */
export function farmMix(farm, plan, year) {
  const areaByCrop = {};
  for (const section of farm.sections) {
    const sectionPlan = plan?.sections.find((s) => s.id === section.id);
    const { id } = cropOfYear(section, sectionPlan, year, farm.farm.time.frequencyMonths);
    const crop = SHEETS[id]?.cropId ?? id;
    if (!crop) continue;
    areaByCrop[crop] = (areaByCrop[crop] ?? 0) + section.areaHa;
  }
  return areaByCrop;
}
