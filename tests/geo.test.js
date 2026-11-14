import { describe, expect, it } from 'vitest';
import { areaHa, bounds, fitToBox, isClosed, roundHa } from '../application/rules/geo.js';
import { DEMO_FARM } from '../data/reference/demoFarm.js';

describe('geo', () => {
  it('a polygon needs 3 corners', () => {
    expect(isClosed([])).toBe(false);
    expect(isClosed([[45, -72]])).toBe(false);
    expect(
      areaHa([
        [45, -72],
        [45.001, -72],
      ]),
    ).toBe(0);
    expect(isClosed(DEMO_FARM.sections[0].polygon)).toBe(true);
  });

  it('computes the area of a 100 m × 100 m square as 1 ha', () => {
    const lat = 45.6;
    const dLat = 100 / 111_320;
    const dLon = 100 / (111_320 * Math.cos((lat * Math.PI) / 180));
    const square = [
      [lat, -72],
      [lat, -72 + dLon],
      [lat + dLat, -72 + dLon],
      [lat + dLat, -72],
    ];
    expect(areaHa(square)).toBeCloseTo(1, 2);
  });

  it('demo farm polygons match the declared areas', () => {
    for (const s of DEMO_FARM.sections) {
      expect(roundHa(areaHa(s.polygon)), `section ${s.id}`).toBeCloseTo(s.areaHa, 0);
    }
    const total = DEMO_FARM.sections.reduce((a, s) => a + s.areaHa, 0);
    expect(roundHa(areaHa(DEMO_FARM.farm.boundary))).toBeCloseTo(total, 0);
  });

  it('fits polygons in a box, north up', () => {
    const b = bounds([DEMO_FARM.farm.boundary]);
    expect(b[0][0]).toBeLessThan(b[1][0]);
    const { shapes, scale } = fitToBox([DEMO_FARM.farm.boundary], {
      width: 200,
      height: 100,
      padding: 10,
    });
    expect(scale).toBeGreaterThan(0);
    const xs = shapes[0].map((p) => p.x);
    const ys = shapes[0].map((p) => p.y);
    expect(Math.min(...xs)).toBeGreaterThanOrEqual(9.99);
    expect(Math.max(...xs)).toBeLessThanOrEqual(190.01);
    expect(Math.min(...ys)).toBeGreaterThanOrEqual(9.99);
    expect(Math.max(...ys)).toBeLessThanOrEqual(90.01);
    // the northernmost corner (highest latitude) is at the top (smallest y)
    const northIdx = DEMO_FARM.farm.boundary.findIndex((p) => p[0] === b[1][0]);
    expect(shapes[0][northIdx].y).toBeCloseTo(Math.min(...ys), 5);
  });
});
