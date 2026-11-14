/** Constants of the climate steps (2 to 4). */

/** A cycle that ends within this many years of today uses the NASA POWER trend only. */
export const SHORT_TERM_HORIZON_YEARS = 10;
/** The 20 most recent complete years of NASA POWER, shifted by the trend (case 1). */
export const RECENT_WINDOW = { first: 2005, last: 2024 };
/** Baseline of the deltas: NEX-GDDP-CMIP6 historical runs stop in 2014 (case 2). */
export const MODEL_BASELINE = { first: 1985, last: 2014 };
/** A climate needs 20 years: window = centre − 10 … centre + 9 (case 2). */
export const CLIMATE_WINDOW_BEFORE_YEARS = 10;
export const CLIMATE_WINDOW_AFTER_YEARS = 9;
/** Years when the twins' crops are known (AAFC inventory in Québec from 2011). */
export const TWIN_PERIOD = { first: 2011, last: 2024 };

/** Growing degree-days: base 10 °C, temperatures capped at 30 °C, April to October. */
export const DEGREE_DAY_BASE_C = 10;
export const DEGREE_DAY_CAP_C = 30;
export const GROWING_SEASON = { firstMonth: 4, lastMonth: 10 };
/** Summer rain: June to August. */
export const SUMMER = { firstMonth: 6, lastMonth: 8 };
/** A hot day goes above 30 °C; a frost is a minimum at or below 0 °C. */
export const HOT_DAY_C = 30;
export const FROST_C = 0;
/** Days of the year before this one are spring frosts, the others fall frosts. */
export const FIRST_FALL_DAY_OF_YEAR = 182;
/** Frost-free season when a year has no spring / no fall frost. */
export const NO_SPRING_FROST_DAY = 0;
export const NO_FALL_FROST_DAY = 366;
export const JANUARY = 1;

/** The rain ratio of a model is bounded (case 2). */
export const RAIN_RATIO_BOUNDS = { min: 0.5, max: 2 };
/** Fixed-date harvests come ~3 days earlier per °C of warming (hypothesis, to check). */
export const HARVEST_ADVANCE_MONTHS_PER_C = 0.1;

/** Twins kept for each target climate, and the sigma beyond which no real twin exists. */
export const TWINS_PER_TARGET = 10;
export const GOOD_TWIN_MAX_SIGMA = 2;
