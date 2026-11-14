/**
 * Reference inputs of the contract, used to write backend/contract/examples/ and by
 * the tests. `today` is fixed so that the examples do not change from day to day.
 */
import { DEMO_FARM } from '../../data/reference/demoFarm.js';

export const EXAMPLE_TODAY = '2026-11-13';

const withTime = (time) => ({
  ...structuredClone(DEMO_FARM),
  today: EXAMPLE_TODAY,
  farm: { ...structuredClone(DEMO_FARM.farm), time },
});

export const CASES = {
  /** The demo farm: cycle of 4 years, one crop a year, 12 years. */
  'ferme-demo': withTime({ cycleYears: 4, frequencyMonths: 12, horizonYears: 12 }),
  /** Two crops a year: rye takes its own positions. */
  'deux-cultures-par-an': withTime({ cycleYears: 4, frequencyMonths: 6, horizonYears: 8 }),
  /** A 5-year cycle: alfalfa ×3 fits again. */
  'cycle-5-ans': withTime({ cycleYears: 5, frequencyMonths: 12, horizonYears: 10 }),
};
