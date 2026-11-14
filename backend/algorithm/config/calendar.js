/**
 * Time constants of the chain building (step 9b). Times are absolute months
 * since January of EPOCH_YEAR, as decimals (see time/MonthTime.js).
 */
export { EPOCH_YEAR, MONTHS_PER_YEAR } from '../../../data/reference/planning.js';

/** About one week between a harvest and the next sowing. */
export const SOWING_DELAY_MONTHS = 0.25;
/** Step used to try later sowing dates inside a sowing window. */
export const SOWING_STEP_MONTHS = 0.25;
/** Step of the degree-day accumulation from sowing to maturity. */
export const MATURITY_STEP_MONTHS = 0.05;
/** A summer crop that is not mature after this many months never is. */
export const MAX_MATURITY_MONTHS = 12;
/** Days per month in the degree-day accumulation (field_shift.py). */
export const DEGREE_DAY_DAYS_PER_MONTH = 30.4;
/** Days per month when a day of the year becomes a decimal month. */
export const DAYS_PER_MONTH = 30.44;
/** A double crop is sown at most this long after the harvest it follows. */
export const DOUBLE_CROP_MAX_DELAY_MONTHS = 1;
/** Sowing years tried after a harvest, starting the year before it. */
export const SOWING_YEARS_TRIED = 5;
/** Rounding guard when comparing decimal months. */
export const TIME_EPSILON = 1e-9;
/** Rounding guard when a cover crop is attached to the crop harvested before it. */
export const COVER_ATTACH_EPSILON = 1e-6;
