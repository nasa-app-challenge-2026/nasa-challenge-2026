/**
 * The climate calendar of one cycle (output of step 3, used by step 9b): heat of
 * each month, mean dates of the last spring frost and the first fall frost, mean
 * January minimum, and how much earlier the fixed-date harvests come.
 */
import {
  DEGREE_DAY_DAYS_PER_MONTH,
  MATURITY_STEP_MONTHS,
  MAX_MATURITY_MONTHS,
  MONTHS_PER_YEAR,
} from '../config/calendar.js';

export const CLIMATE_METHOD = { TREND: 'tendance', MODELS: 'modeles' };

export class CycleClimate {
  /**
   * @param {object} p
   * @param {number[]} p.degreeDaysPerDay  12 values: mean degree-days per day of each month
   * @param {number|null} p.lastSpringFrost mean last spring frost (0-based decimal month), null = no frost
   * @param {number|null} p.firstFallFrost  mean first fall frost, null = no frost
   * @param {number} p.januaryMinimumC
   * @param {number} p.harvestAdvanceMonths fixed-date harvests come this much earlier
   * @param {number} p.warmingC            temperature shift compared with 2005–2024
   * @param {number} p.summerRainChangePct June–August rain compared with 2005–2024
   * @param {string} p.method              CLIMATE_METHOD.TREND or CLIMATE_METHOD.MODELS
   * @param {string} p.source              readable source ("tendance NASA POWER"…)
   * @param {string[]} [p.models]          climate models averaged (case 2)
   */
  constructor(p) {
    this.degreeDaysPerDay = p.degreeDaysPerDay;
    this.lastSpringFrost = p.lastSpringFrost;
    this.firstFallFrost = p.firstFallFrost;
    this.januaryMinimumC = p.januaryMinimumC;
    this.harvestAdvanceMonths = p.harvestAdvanceMonths;
    this.warmingC = p.warmingC ?? 0;
    this.summerRainChangePct = p.summerRainChangePct ?? 0;
    this.method = p.method;
    this.source = p.source;
    this.models = p.models ?? [];
    this.maturityOffsets = new Map();
  }

  /**
   * When a crop sown at `sowing` (absolute month) has received `degreeDays`, or
   * null if it never does within a year. Computed from the month of the year it is
   * sown, so the result does not depend on the year.
   */
  maturity(sowing, degreeDays) {
    const start = sowing % MONTHS_PER_YEAR;
    const key = `${start}|${degreeDays}`;
    if (!this.maturityOffsets.has(key))
      this.maturityOffsets.set(key, this.#maturityOffset(start, degreeDays));
    const offset = this.maturityOffsets.get(key);
    return offset === null ? null : sowing + offset;
  }

  #maturityOffset(start, degreeDays) {
    let total = 0;
    let t = start;
    while (total < degreeDays) {
      const month = Math.floor(t) % MONTHS_PER_YEAR;
      total += this.degreeDaysPerDay[month] * DEGREE_DAY_DAYS_PER_MONTH * MATURITY_STEP_MONTHS;
      t += MATURITY_STEP_MONTHS;
      if (t - start > MAX_MATURITY_MONTHS) return null;
    }
    return t - start;
  }

  /** Plain data, for the plan sent to the screens. */
  toJSON() {
    const { maturityOffsets: _cache, ...data } = this;
    return data;
  }
}
