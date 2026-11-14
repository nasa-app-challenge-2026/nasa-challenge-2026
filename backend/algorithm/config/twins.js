/** Constants of the twin fields: soil filter (step 5), rotations (6), precrop values (7). */

/** Soil: each difference is divided by its tolerance; distance ≤ 1 = same soil. */
export const SOIL_TOLERANCES = {
  clayPct: 8,
  sandPct: 12,
  /** Organic carbon is compared in logarithm: a ratio of 1.5 counts as 1. */
  organicCarbonRatio: 1.5,
  ph: 0.6,
};
export const SAME_SOIL_MAX_DISTANCE = 1;
/** Fewer fields than this after the filter: widen the tolerances by 25 % (shown in the app). */
export const MIN_FIELDS_AFTER_SOIL_FILTER = 200;
export const SOIL_TOLERANCE_WIDENING = 1.25;

/** Rotations: cycles of 2 to 4 years, at most one atypical year. */
export const LONGEST_ROTATION_YEARS = 4;
export const ATYPICAL_YEARS_ALLOWED = 1;
export const TOP_ROTATIONS = 3;

/**
 * Greenness → yield gap (Peltonen-Sainio et al. 2019): 0 at the 90th percentile of
 * the fields of the same crop, zone and year, 0.30 at the median, 0.55 at the 25th.
 */
export const YIELD_GAP_AT_MEDIAN = 0.3;
export const YIELD_GAP_MEDIAN_TO_Q25 = 0.25;
export const MAX_YIELD_GAP = 1;
export const PERCENT = 100;
/** A precrop value needs at least 20 fields in each group, else it stays unknown. */
export const MIN_FIELDS_PER_GROUP = 20;
