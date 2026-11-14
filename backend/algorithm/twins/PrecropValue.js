/**
 * Step 7: greenness → yield → value of the previous crop (Peltonen-Sainio et al. 2019).
 *
 * The peak NDVI (NASA HLS, 30 m) of a field is compared with the fields of the same
 * crop, zone and year (comparing the same year cancels the weather of the year).
 * Its rank becomes an estimated yield gap: 0 at the 90th percentile, 0.30 at the
 * median, 0.55 at the 25th percentile. The value of crop A before crop B is the
 * mean gap of B after B (monoculture) minus the mean gap of B after A: positive =
 * A helps B. At least 20 fields per group, else the value stays unknown.
 */
import {
  MAX_YIELD_GAP,
  MIN_FIELDS_PER_GROUP,
  PERCENT,
  YIELD_GAP_AT_MEDIAN,
  YIELD_GAP_MEDIAN_TO_Q25,
} from '../config/twins.js';
import { mean } from '../math/numbers.js';

/** Smallest spread between the median and the 25th percentile (avoids dividing by 0). */
const MIN_SPREAD = 1e-6;

/**
 * Estimated yield gap (0 to 1) of a field from its peak NDVI.
 * @param {number} ndvi peak NDVI of the field
 * @param {{ p90: number, p50: number, p25: number }} percentiles same crop, zone and year
 */
export function yieldGapFromNdvi(ndvi, { p90, p50, p25 }) {
  if (ndvi >= p90) return 0;
  if (ndvi > p50) return (YIELD_GAP_AT_MEDIAN * (p90 - ndvi)) / (p90 - p50);
  return Math.min(
    MAX_YIELD_GAP,
    YIELD_GAP_AT_MEDIAN +
      (YIELD_GAP_MEDIAN_TO_Q25 * (p50 - ndvi)) / Math.max(p50 - p25, MIN_SPREAD),
  );
}

/**
 * Yield gain (%) of crop `next` when it follows `previous` rather than itself.
 * @param {{ crop: string, previous: string, yieldGap: number }[]} fieldYears one per field and year
 * @returns {number|null} null = gap in the data (fewer than 20 fields in a group)
 */
export function precropValue(fieldYears, previous, next, minFields = MIN_FIELDS_PER_GROUP) {
  const gaps = (before) =>
    fieldYears.filter((r) => r.crop === next && r.previous === before).map((r) => r.yieldGap);
  const monoculture = gaps(next);
  const after = gaps(previous);
  if (monoculture.length < minFields || after.length < minFields) return null;
  return PERCENT * (mean(monoculture) - mean(after));
}
