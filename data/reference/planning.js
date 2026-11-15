/**
 * What the farmer chooses before the algorithm runs (step 1 of field_shift v5.1): the cycle, how
 * often a crop is harvested, the horizon, the reserve mode. The screens offer only valid choices;
 * the server refuses the others with the same limits (backend/server/field_shift/reference/
 * planning.py), and tests/contract.test.js checks that both agree through the schema.
 */

export const MONTHS_PER_YEAR = 12;

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
    label: 'Toutes les cultures',
    text: 'Toutes les cultures restent possibles ; celles qui manquent à la réserve sont listées « à se procurer ».',
  },
  uniquement: {
    label: 'Ma réserve uniquement',
    text: 'Seules les semences de la réserve sont proposées (plus la jachère).',
  },
};

/** Fewest years of history asked to the farmer (step 1). */
export const MIN_HISTORY_YEARS = 3;
