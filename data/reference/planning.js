/**
 * What the farmer chooses before the algorithm runs (step 1 of field_shift.py
 * v5.1): the cycle, how often a crop is harvested, the horizon, the criteria he
 * ranks, the reserve mode. Shared by the screens and the algorithm.
 */

export const MONTHS_PER_YEAR = 12;
export const EPOCH_YEAR = 2000;

/** A rotation cycle lasts from 2 to 6 years. */
export const CYCLE_YEARS = { min: 2, max: 6 };

/**
 * Harvest frequency. `positionStartMonth` = month (0-based) where the positions
 * of the cycle start: January with one crop a year, February otherwise.
 */
export const FREQUENCIES = [
  { months: 12, label: '1 culture par an', positionStartMonth: 0 },
  { months: 6, label: '2 cultures par an (été et hiver)', positionStartMonth: 1 },
  {
    months: 4,
    label: '3 cultures par an (cultures courtes, rare au Québec)',
    positionStartMonth: 1,
  },
];

/** Last year covered by the climate projections: horizons stop there. */
export const LAST_PROJECTION_YEAR = 2060;

/** Seed reserve modes. */
export const RESERVE_MODES = {
  preferer: {
    label: 'Préférer ma réserve',
    text: 'Toutes les cultures restent possibles ; celles de la réserve comptent dans la note.',
  },
  uniquement: {
    label: 'Ma réserve uniquement',
    text: 'Seules les semences de la réserve sont proposées (plus la jachère).',
  },
};

/** Fewest years of history asked to the farmer (step 1). */
export const MIN_HISTORY_YEARS = 3;

/** An unranked criterion keeps this share of the smallest weight (step 1). */
export const UNRANKED_WEIGHT_SHARE = 0.25;
