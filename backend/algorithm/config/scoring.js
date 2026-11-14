/** Constants of the diagnostic (step 8), the chain score (9b) and the plan (10). */

/**
 * Step 8: each measure is divided by the value where it reaches its maximum
 * (`saturation`), bounded to 0..1, and weighted by its `share` of the risk.
 */
export const EROSION_RISK = {
  slopePct: { share: 0.5, saturation: 8 },
  heavyRainDays: { share: 0.3, saturation: 8 },
  bareSoilDays: { share: 0.2, saturation: 150 },
};
export const WATER_RISK = {
  /** ECOSTRESS ESI: no stress at 0.8 and above, full stress at 0.4 and below. */
  summerStressIndex: { share: 0.4, noStress: 0.8, range: 0.4 },
  rootZoneDrought: { share: 0.3 },
  summerRainDropPct: { share: 0.2, saturation: 20 },
  groundwaterDropCmPerYear: { share: 0.1, saturation: 2 },
};
/** An irrigated field keeps 40 % of its water risk. */
export const IRRIGATED_WATER_RISK_FACTOR = 0.4;

/** Weights: erosion × (1 + erosion risk), water × (1 + water risk), forage × 0.3 without livestock. */
export const NO_LIVESTOCK_FORAGE_FACTOR = 0.3;

/** Yield criterion: precrop values from −16 % to +16 % become 0 to 1. */
export const PRECROP_VALUE_RANGE_PCT = 16;
/** Scores are on 100. */
export const SCORE_SCALE = 100;

/** Beam search: partial chains kept at each position, complete chains returned. */
export const BEAM_WIDTH = 400;
export const BEST_CHAINS = 3;
/** The chain in place is kept while it is at most this many points below the best. */
export const KEEP_THRESHOLD_POINTS = 5;

/** Duration guard: never divide by an empty time span. */
export const MIN_DURATION_MONTHS = 1e-6;
