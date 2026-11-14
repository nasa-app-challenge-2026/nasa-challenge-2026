/**
 * Times of the chain building: absolute months since January of EPOCH_YEAR, as
 * decimals. 321.6 = (2026 − 2000) × 12 + 9.6 = about 19 October 2026.
 * Months inside a year are 0-based (0 = January).
 */
import { DAYS_PER_MONTH, EPOCH_YEAR, MONTHS_PER_YEAR, TIME_EPSILON } from '../config/calendar.js';
import { floorMod } from '../math/numbers.js';
import { MONTH_NAMES } from '../../../data/reference/calendar.js';

export { MONTH_NAMES };

export const MonthTime = {
  /** Absolute time of month `month` (0-based decimal) of `year`. */
  of: (year, month) => (year - EPOCH_YEAR) * MONTHS_PER_YEAR + month,

  /** Year of an absolute time. */
  yearOf: (time) => EPOCH_YEAR + Math.floor(time / MONTHS_PER_YEAR),

  /** Month of the year (0-based decimal) of an absolute time. */
  monthOfYear: (time) => floorMod(time, MONTHS_PER_YEAR),

  /** Start of `year`. */
  startOfYear: (year) => (year - EPOCH_YEAR) * MONTHS_PER_YEAR,

  /** Calendar date of an absolute time: { year, month (1–12), day }. */
  toDate(time) {
    const whole = Math.floor(time + TIME_EPSILON);
    const year = EPOCH_YEAR + Math.floor(whole / MONTHS_PER_YEAR);
    const month = floorMod(whole, MONTHS_PER_YEAR);
    return { year, month: month + 1, day: dayInMonth(time - whole, year, month) };
  },

  /** "2027-05-08" */
  toIsoDate(time) {
    const { year, month, day } = MonthTime.toDate(time);
    return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
  },

  /** "mai 2027" */
  label(time) {
    const { year, month } = MonthTime.toDate(time);
    return `${MONTH_NAMES[month - 1]} ${year}`;
  },

  /** A month of the year (decimal) as "~23 avr." style parts: { month (1–12), day }. */
  dayOfYearParts(monthOfYear) {
    const month = Math.floor(monthOfYear);
    return { month: month + 1, day: dayInMonth(monthOfYear - month, 2001, month) };
  },
};

function dayInMonth(fraction, year, month) {
  const days = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
  return Math.min(days, Math.floor(fraction * DAYS_PER_MONTH) + 1);
}
