/**
 * Return delays of a chain (hard constraint n° 4 and the "pests" criterion).
 *
 * Checked between the crops of the chain; between what grew before (history or
 * previous cycle) and the start of the chain; between the end of the chain and its
 * repetition in the next cycle. Two crops of different families that share a soil
 * disease (white mould, common scab) and come back too fast give a warning, without
 * changing the score.
 */
import { delayRules, reasonKey } from './ReturnDelayRules.js';
import { OCCUPATION_SOURCE, yearsBetween } from './Occupation.js';
import { defaultDelayCatalog } from './ReturnDelayCatalog.js';
import { MIN_HISTORY_YEARS } from '../../../data/reference/planning.js';

const { CHAIN, HISTORY, NEXT_CYCLE, PREVIOUS_CYCLE } = OCCUPATION_SOURCE;
const byFirstYear = (a, b) => a.firstYear - b.firstYear;

/**
 * @typedef {object} DelayViolation
 * @property {object} reason       see ReturnDelayRules
 * @property {number} yearsWithout years without the crop
 * @property {number} minimum      years required
 * @property {{ year: number, source: string }} from  harvest of the earlier crop
 * @property {{ year: number, source: string }} to    first year of the later crop
 *
 * @typedef {{ disease: string, previous: string, next: string, yearsWithout: number, advised: number }} SharedDiseaseWarning
 */

export class ReturnDelayChecker {
  /**
   * @param {object} p
   * @param {number} p.cycleYears           C
   * @param {import('./Occupation.js').Occupation[]|null} [p.history] what grew before the
   *        cycle; null = the previous cycle was the same chain
   * @param {string[]} [p.diseases]         soil diseases declared by the farmer
   */
  constructor({ cycleYears, history = null, diseases = [], catalog = defaultDelayCatalog }) {
    this.cycleYears = cycleYears;
    this.history = history;
    this.diseases = diseases;
    this.catalog = catalog;
  }

  /**
   * The chain with what precedes it and, for a complete chain, its repetition in the
   * next cycle (the cycle starts again).
   */
  timeline(occupations, closed) {
    const chain = [...occupations].sort(byFirstYear);
    const before =
      this.history === null
        ? closed
          ? chain.map((o) => o.shiftedBy(-this.cycleYears, PREVIOUS_CYCLE))
          : []
        : this.history.map((o) => o.withSource(HISTORY));
    const after = closed ? chain.map((o) => o.shiftedBy(this.cycleYears, NEXT_CYCLE)) : [];
    return [...before, ...chain, ...after].sort(byFirstYear);
  }

  /** Hard constraints only (fast, for the beam search). */
  violations(occupations, { closed = true } = {}) {
    const timeline = this.timeline(occupations, closed);
    const found = [];
    const seen = new Set();
    timeline.forEach((b, j) => {
      if (b.source !== CHAIN && b.source !== NEXT_CYCLE) return;
      for (const a of timeline.slice(0, j)) {
        if (a.source === NEXT_CYCLE && b.source === NEXT_CYCLE) continue;
        const gap = yearsBetween(a, b);
        for (const rule of delayRules(this.catalog, a.cropId, b.cropId, this.diseases)) {
          if (gap >= rule.minimum) continue;
          const key = `${reasonKey(rule.reason)}|${a.lastYear}|${b.firstYear}`;
          if (seen.has(key)) continue;
          seen.add(key);
          found.push({
            reason: rule.reason,
            yearsWithout: gap,
            minimum: rule.minimum,
            from: { year: a.lastYear, source: a.source },
            to: { year: b.firstYear, source: b.source },
          });
        }
      }
    });
    return found;
  }

  isAllowed(occupations, { closed = true } = {}) {
    return this.violations(occupations, { closed }).length === 0;
  }

  /** Full verdict of a complete chain. */
  check(occupations) {
    const violations = this.violations(occupations);
    return {
      ok: violations.length === 0,
      violations,
      warnings: this.sharedDiseaseWarnings(occupations),
      pestScore: this.pestScore(occupations),
    };
  }

  /**
   * "Pests" criterion (0 to 1): for each sold crop of the chain, the smallest ratio
   * (years without + 1) ÷ (recommended delay + 1) with the crops before AND after it
   * (same crop, same family, declared disease), capped at 1. Mean over the crops.
   */
  pestScore(occupations, { closed = true } = {}) {
    const timeline = this.timeline(occupations, closed);
    const scores = [];
    timeline.forEach((b, j) => {
      if (b.source !== CHAIN) return;
      let score = 1;
      timeline.forEach((a, i) => {
        if (i === j) return;
        const [before, after] = i < j ? [a, b] : [b, a];
        const gap = yearsBetween(before, after);
        for (const rule of delayRules(this.catalog, before.cropId, after.cropId, this.diseases)) {
          if (rule.recommended > 0)
            score = Math.min(score, Math.max(0, (gap + 1) / (rule.recommended + 1)));
        }
      });
      scores.push(score);
    });
    return scores.length ? scores.reduce((s, v) => s + v, 0) / scores.length : null;
  }

  /** Crops of different families hosting the same undeclared cross-family disease, too close. */
  sharedDiseaseWarnings(occupations) {
    const timeline = this.timeline(occupations, true);
    const worst = new Map();
    for (const [disease, info] of Object.entries(this.catalog.diseases)) {
      if (!info.crossFamily || this.diseases.includes(disease)) continue;
      const hosts = timeline.filter((o) => info.hosts.includes(this.catalog.get(o.cropId)?.id));
      hosts.forEach((b, j) => {
        if (b.source !== CHAIN && b.source !== NEXT_CYCLE) return;
        for (const a of hosts.slice(0, j)) {
          const fa = this.catalog.get(a.cropId);
          const fb = this.catalog.get(b.cropId);
          if (fa.family === fb.family) continue;
          const gap = yearsBetween(a, b);
          const key = `${disease}|${[fa.id, fb.id].sort().join('|')}`;
          if (gap < info.low && (!worst.has(key) || gap < worst.get(key).yearsWithout)) {
            worst.set(key, {
              disease,
              previous: fa.id,
              next: fb.id,
              yearsWithout: gap,
              advised: info.low,
            });
          }
        }
      });
    }
    return [...worst.values()];
  }
}

/**
 * Crops that cannot come back every cycle: a crop present once per cycle has at
 * most C − (years it occupies) years without it. Below its minimum, it is removed.
 * @param {{ id: string, cropId: string, productionYears: number }[]} sheets
 * @returns {Map<string, { required: number, possible: number, occupiedYears: number }>}
 */
export function impossibleCrops(
  cycleYears,
  sheets,
  declaredDiseases = [],
  catalog = defaultDelayCatalog,
) {
  const out = new Map();
  for (const sheet of sheets) {
    const delay = catalog.get(sheet.cropId);
    if (!delay) continue;
    const occupiedYears = Math.max(sheet.productionYears, 1);
    const required = Math.max(
      delay.minimum,
      catalog.declaredDiseaseDelay(sheet.cropId, declaredDiseases),
    );
    const possible = cycleYears - occupiedYears;
    if (possible < required) out.set(sheet.id, { required, possible, occupiedYears });
  }
  return out;
}

/** Years of history to ask the farmer: the longest recommended delay (at least MIN_HISTORY_YEARS). */
export function historyDepth(
  cropIds,
  declaredDiseases = [],
  { minimum = MIN_HISTORY_YEARS, catalog = defaultDelayCatalog } = {},
) {
  const delays = cropIds.map((c) => catalog.get(c)?.recommended).filter((d) => d !== undefined);
  const diseases = declaredDiseases.map((d) => catalog.diseases[d]?.high ?? 0);
  return Math.max(minimum, ...delays, ...diseases);
}
