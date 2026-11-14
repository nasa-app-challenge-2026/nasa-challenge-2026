/**
 * Step 1, block C of the algorithm: the cycle (C years), the harvest frequency
 * (f months) and the horizon (a multiple of C). The screens use it to offer only
 * valid choices; the algorithm (backend/algorithm/) uses it to lay out the
 * positions of a cycle.
 */
import {
  CYCLE_YEARS,
  FREQUENCIES,
  LAST_PROJECTION_YEAR,
  MONTHS_PER_YEAR,
} from '../../data/reference/planning.js';

const frequency = (months) => FREQUENCIES.find((f) => f.months === months);

export class TimeSettings {
  /** @param {{ cycleYears: number, frequencyMonths: number, horizonYears: number }} settings */
  constructor({ cycleYears, frequencyMonths, horizonYears }) {
    const errors = TimeSettings.errors({ cycleYears, frequencyMonths, horizonYears });
    if (errors.length) throw new Error(errors.join(' '));
    this.cycleYears = cycleYears;
    this.frequencyMonths = frequencyMonths;
    this.horizonYears = horizonYears;
    Object.freeze(this);
  }

  /** Why these settings are not valid (empty list = valid). */
  static errors({ cycleYears, frequencyMonths, horizonYears }) {
    const errors = [];
    if (
      !Number.isInteger(cycleYears) ||
      cycleYears < CYCLE_YEARS.min ||
      cycleYears > CYCLE_YEARS.max
    )
      errors.push(`Le cycle doit durer de ${CYCLE_YEARS.min} à ${CYCLE_YEARS.max} ans.`);
    if (!frequency(frequencyMonths)) errors.push('Fréquence : 12, 6 ou 4 mois.');
    else if ((MONTHS_PER_YEAR * cycleYears) % frequencyMonths)
      errors.push(`${frequencyMonths} mois ne divise pas un cycle de ${cycleYears} ans.`);
    if (!Number.isInteger(horizonYears) || horizonYears <= 0 || horizonYears % cycleYears)
      errors.push(
        `L’horizon (${horizonYears} ans) doit être un multiple du cycle (${cycleYears} ans).`,
      );
    return errors;
  }

  /** N: number of positions (crops) in one cycle. */
  get positionsPerCycle() {
    return (MONTHS_PER_YEAR * this.cycleYears) / this.frequencyMonths;
  }

  get cycleCount() {
    return this.horizonYears / this.cycleYears;
  }

  /** Month (0-based) where the positions start: January (12 months) or February. */
  get positionStartMonth() {
    return frequency(this.frequencyMonths).positionStartMonth;
  }
}

/** Frequencies that divide a cycle of `cycleYears` years. */
export function allowedFrequencies(cycleYears) {
  return FREQUENCIES.filter((f) => (MONTHS_PER_YEAR * cycleYears) % f.months === 0);
}

/** Horizons C, 2C, 3C… that end before the last projection year. */
export function allowedHorizons(cycleYears, firstYear, lastYear = LAST_PROJECTION_YEAR) {
  const out = [];
  for (let k = 1; firstYear + k * cycleYears - 1 <= lastYear; k++) out.push(k * cycleYears);
  return out;
}

/** The nearest valid horizon (used when the farmer changes the cycle). */
export function nearestHorizon(cycleYears, wantedYears, firstYear) {
  const options = allowedHorizons(cycleYears, firstYear);
  if (!options.length) return cycleYears;
  return options.reduce((best, h) =>
    Math.abs(h - wantedYears) < Math.abs(best - wantedYears) ? h : best,
  );
}
