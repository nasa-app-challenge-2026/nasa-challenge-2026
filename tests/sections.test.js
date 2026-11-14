import { describe, expect, it } from 'vitest';
import { areaHa, roundHa } from '../application/rules/geo.js';
import { followOutline } from '../application/rules/sections.js';
import { DEMO_FARM } from '../data/reference/demoFarm.js';

// The demo farm: four sections drawn inside the outline, their corners on it.
const [[N, W]] = DEMO_FARM.farm.boundary;
const sumHa = (farm) => roundHa(farm.sections.reduce((a, s) => a + areaHa(s.polygon), 0));

describe('sections follow the outline', () => {
  it('a dragged outline corner drags the sections that touch it', () => {
    const farm = structuredClone(DEMO_FARM);
    const before = structuredClone(farm.farm.boundary);
    farm.farm.boundary[0] = [N + 0.001, W - 0.001]; // north-west corner, ~150 m out
    expect(followOutline(farm, before)).toBe(true);

    const a = farm.sections.find((s) => s.id === 'A'); // the north-west section
    expect(a.polygon[0]).toEqual(farm.farm.boundary[0]);
    expect(a.areaHa).toBeGreaterThan(DEMO_FARM.sections.find((s) => s.id === 'A').areaHa);
    // the sections still cover the whole outline
    expect(sumHa(farm)).toBeCloseTo(roundHa(areaHa(farm.farm.boundary)), 0);
    // a section away from that corner did not move
    const b = farm.sections.find((s) => s.id === 'B');
    expect(b.polygon).toEqual(DEMO_FARM.sections.find((s) => s.id === 'B').polygon);
  });

  it('adding or removing outline corners leaves the sections alone', () => {
    const farm = structuredClone(DEMO_FARM);
    const before = structuredClone(farm.farm.boundary);
    farm.farm.boundary = before.slice(0, 3);
    expect(followOutline(farm, before)).toBe(false);
    expect(farm.sections).toEqual(DEMO_FARM.sections);
  });
});
