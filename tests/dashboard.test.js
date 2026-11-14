import { describe, expect, it } from 'vitest';
import {
  dashboardOrder,
  defaultOrder,
  isDefaultOrder,
  moveBlock,
} from '../frontend/lib/dashboard.js';

describe('dashboard order', () => {
  it('has a default layout: weather + A B, 3D + C D, mix, fires, then more sections', () => {
    expect(defaultOrder(['A', 'B', 'C', 'D', 'E'])).toEqual([
      'weather',
      'sec:A',
      'sec:B',
      'farm3d',
      'sec:C',
      'sec:D',
      'mix',
      'fire',
      'sec:E',
    ]);
  });

  it('keeps the saved order, drops removed sections and slots new ones after the last section', () => {
    const saved = ['mix', 'sec:B', 'weather', 'sec:A', 'sec:Z', 'farm3d'];
    expect(dashboardOrder(saved, ['A', 'B', 'C'])).toEqual([
      'mix',
      'sec:B',
      'weather',
      'sec:A',
      'sec:C',
      'farm3d',
      'fire',
    ]);
  });

  it('restores a missing fixed block and ignores duplicates', () => {
    expect(dashboardOrder(['sec:A', 'sec:A', 'mix'], ['A'])).toEqual([
      'sec:A',
      'mix',
      'weather',
      'farm3d',
      'fire',
    ]);
    expect(dashboardOrder(null, ['A'])).toEqual(defaultOrder(['A']));
  });

  it('moves a block with the keyboard and knows the default', () => {
    const o = defaultOrder(['A', 'B']);
    expect(moveBlock(o, 'weather', 1).slice(0, 2)).toEqual(['sec:A', 'weather']);
    expect(moveBlock(o, 'weather', -1)).toBe(o);
    expect(isDefaultOrder(o, ['A', 'B'])).toBe(true);
    expect(isDefaultOrder(moveBlock(o, 'mix', -1), ['A', 'B'])).toBe(false);
  });
});
