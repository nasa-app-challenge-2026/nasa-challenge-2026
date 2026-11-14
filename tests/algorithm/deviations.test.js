/** Deliberate differences with field_shift.py v5.1 (docs/ALGORITHME.md, « Écarts avec la référence »). */
import { describe, expect, it } from 'vitest';
import { successions, yieldCriterion } from '../../backend/algorithm/chain/ChainScorer.js';
import { CycleClimate } from '../../backend/algorithm/climate/CycleClimate.js';
import { placeCrop } from '../../backend/algorithm/chain/CropPlacer.js';
import { solveCovariance } from '../../backend/algorithm/math/linearAlgebra.js';
import { roundHalfToEven } from '../../backend/algorithm/math/numbers.js';

describe('differences with the reference', () => {
  it('without a crop in place, the yield successions are read in order', () => {
    expect(successions(['mais', 'soya', 'ble-automne'], null, true)).toEqual([
      ['mais', 'soya'],
      ['soya', 'ble-automne'],
      ['ble-automne', 'mais'],
    ]);
    expect(successions(['soya'], 'mais', false)).toEqual([['mais', 'soya']]);
    expect(yieldCriterion([])).toBeNull();
  });

  it('a climate without frost does not block frost-sensitive crops', () => {
    const tropical = new CycleClimate({
      degreeDaysPerDay: new Array(12).fill(12),
      lastSpringFrost: null,
      firstFallFrost: null,
      januaryMinimumC: 15,
      harvestAdvanceMonths: 0,
    });
    const time = { frequencyMonths: 12, positionStartMonth: 0 };
    expect(placeCrop('mais', 27, 321.5, null, { time, climate: tropical })).not.toBeNull();
  });

  it('a singular covariance (an indicator that never changes) does not stop the search', () => {
    const x = solveCovariance(
      [
        [1, 0],
        [0, 0],
      ],
      [1, 1],
    );
    expect(x.every(Number.isFinite)).toBe(true);
    expect(x[1]).toBeGreaterThan(1000);
  });

  it('rounds the centre of a window like Python (halves to even)', () => {
    expect([roundHalfToEven(2036.5), roundHalfToEven(2037.5), roundHalfToEven(2036.4)]).toEqual([
      2036, 2038, 2036,
    ]);
  });
});
