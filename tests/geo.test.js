import { describe, expect, it } from 'vitest';
import {
  areaHa,
  bounds,
  distanceToBoundsM,
  fitToBox,
  followCorner,
  isClosed,
  roundHa,
} from '../application/rules/geo.js';
import { DEMO_FARM } from '../data/reference/demoFarm.js';

// A grid of 100 m cells near Saint-Hyacinthe: P(x, y) is x cells east, y cells north.
const LAT0 = 45.6;
const LON0 = -72;
const D_LAT = 100 / 111_320;
const D_LON = 100 / (111_320 * Math.cos((LAT0 * Math.PI) / 180));
const P = (x, y) => [LAT0 + y * D_LAT, LON0 + x * D_LON];
const SQUARE = [P(0, 0), P(2, 0), P(2, 2), P(0, 2)]; // 4 ha

describe('followCorner', () => {
  it('moves the corner and slides snapped corners along the edges touching it', () => {
    const left = [P(0, 0), P(1, 0), P(1, 2), P(0, 2)]; // west half, corners snapped to the outline
    const moved = followCorner(left, SQUARE, 0, P(0, -1));
    expect(moved[0]).toEqual(P(0, -1));
    // P(1, 0) was halfway along the edge P(0,0) → P(2,0): it stays halfway along the new edge
    expect(moved[1][0]).toBeCloseTo(P(1, -0.5)[0], 10);
    expect(moved[1][1]).toBeCloseTo(P(1, -0.5)[1], 10);
    expect(moved[2]).toEqual(P(1, 2)); // on an edge that did not move
    expect(moved[3]).toEqual(P(0, 2));
  });
});

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

  it('measures how far a point is from a bounds box', () => {
    const b = bounds([DEMO_FARM.farm.boundary]);
    const { lat, lon } = DEMO_FARM.farm.location;
    expect(distanceToBoundsM(b, [lat, lon])).toBe(0);
    // 1 km north of the box
    expect(distanceToBoundsM(b, [b[1][0] + 1000 / 111_320, lon])).toBeCloseTo(1000, 0);
    // Québec city is ~200 km from the Saint-Hyacinthe demo farm
    expect(distanceToBoundsM(b, [46.8139, -71.208])).toBeGreaterThan(150_000);
  });
});
