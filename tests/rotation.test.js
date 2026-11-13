import { describe, expect, it } from 'vitest';
import {
  autoStagger,
  bestOffsets,
  buildCalendar,
  cycleLength,
  farmMix,
  fromSlots,
  imbalancedYears,
  lockReason,
  placeCrop,
  rotationErrors,
  setCover,
  setCycleYears,
  toSlots,
} from '../src/lib/rotation.js';
import { CASES } from '../contract/cases.js';

const R4 = CASES['cas1-meme-rotation-decalee'].sections[0].rotation;
const farmOf = (c) => CASES[c].farm;
const sectionsOf = (c) => CASES[c].sections;

describe('cycle and slots', () => {
  it('counts multi-year crops in the cycle length', () => {
    const r = [
      { crop: 'mais', years: 1 },
      { crop: 'soya', years: 1 },
      { crop: 'luzerne', years: 3 },
    ];
    expect(cycleLength(r)).toBe(5);
    expect(toSlots(r).map((s) => s.crop)).toEqual([
      'mais',
      'soya',
      'luzerne',
      'luzerne',
      'luzerne',
    ]);
    expect(fromSlots(toSlots(r))).toEqual([
      { crop: 'mais', years: 1, cover: null },
      { crop: 'soya', years: 1, cover: null },
      { crop: 'luzerne', years: 3, cover: null },
    ]);
  });

  it('pads and truncates when the cycle length changes', () => {
    expect(cycleLength(setCycleYears(R4, 6))).toBe(6);
    expect(setCycleYears(R4, 3).map((e) => e.crop)).toEqual(['soya', 'ble', 'mais']);
  });

  it('clears a multi-year block cut by a shorter cycle', () => {
    const r = [
      { crop: 'mais', years: 1 },
      { crop: 'luzerne', years: 3 },
    ];
    expect(setCycleYears(r, 3).map((e) => e.crop)).toEqual(['mais', null, null]);
  });
});

describe('editing', () => {
  it('places alfalfa on 3 years and removes it as a block', () => {
    let r = setCycleYears(R4, 5);
    r = placeCrop(r, 2, 'luzerne');
    expect(toSlots(r).map((s) => s.crop)).toEqual(['soya', 'ble', 'luzerne', 'luzerne', 'luzerne']);
    r = placeCrop(r, 3, 'mais');
    expect(toSlots(r).map((s) => s.crop)).toEqual(['soya', 'ble', null, 'mais', null]);
  });

  it('sets and removes a winter cover', () => {
    const r = setCover(R4, 1, 'trefle');
    expect(r[1].cover).toBe('trefle');
    expect(setCover(r, 1, null)[1].cover).toBeNull();
  });
});

describe('return delays', () => {
  it('locks potato when it would come back too early', () => {
    const r = [
      { crop: 'patate', years: 1 },
      { crop: 'soya', years: 1 },
      { crop: 'ble', years: 1 },
      { crop: 'mais', years: 1 },
      { crop: 'soya', years: 1 },
    ];
    expect(lockReason(r, 2, 'patate')).toMatch(/Délai de retour/);
    expect(lockReason(R4, 3, 'patate')).toBeNull();
  });

  it('locks a crop whose delay is longer than the cycle', () => {
    expect(lockReason(setCycleYears(R4, 3), 0, 'patate')).toMatch(/plus court/);
  });

  it('reports empty years and early returns', () => {
    expect(rotationErrors(setCycleYears(R4, 5))).toContain('L’année 5 n’a pas de culture.');
    expect(rotationErrors(R4)).toEqual([]);
  });
});

describe('calendar and farm mix (the three team cases)', () => {
  it('cas 1: same rotation staggered → every year is balanced', () => {
    expect(
      imbalancedYears(
        farmOf('cas1-meme-rotation-decalee'),
        sectionsOf('cas1-meme-rotation-decalee'),
      ),
    ).toBe(0);
  });

  it('cas 2: different cycle lengths → some years are unbalanced', () => {
    const mix = farmMix(farmOf('cas2-durees-differentes'), sectionsOf('cas2-durees-differentes'));
    expect(mix.some((y) => !y.balanced)).toBe(true);
    expect(mix[0].duplicates).toEqual(['mais']);
  });

  it('cas 3: a 5-year cycle on 12 years ends with a cut cycle', () => {
    const d = sectionsOf('cas3-luzerne-cycle-coupe')[3];
    const cal = buildCalendar(d.rotation, { offset: 0, startYear: 2027, horizonYears: 12 });
    expect(cal.map((y) => y.cut)).toEqual([...Array(10).fill(false), true, true]);
    expect(cal[2].crop).toBe('luzerne');
  });

  it('bestOffsets never makes things worse and fixes cas 3’s first year', () => {
    const farm = farmOf('cas3-luzerne-cycle-coupe');
    const sections = sectionsOf('cas3-luzerne-cycle-coupe');
    const before = imbalancedYears(farm, sections);
    const { offsets, imbalanced } = bestOffsets(farm, sections);
    expect(imbalanced).toBeLessThanOrEqual(before);
    expect(offsets.A).toBe(0);
  });
});

describe('autoStagger', () => {
  const farm = { startYear: 2027, horizonYears: 12 };
  const same = () => [
    { crop: 'mais', years: 1, cover: null },
    { crop: 'soya', years: 1, cover: null },
    { crop: 'ble', years: 1, cover: null },
  ];

  it('shifts identical rotations so the farm grows different crops each year', () => {
    const sections = ['A', 'B', 'C'].map((id) => ({ id, areaHa: 5, offset: 0, rotation: same() }));
    expect(imbalancedYears(farm, sections)).toBe(12);
    autoStagger(farm, sections);
    expect(imbalancedYears(farm, sections)).toBe(0);
    expect(new Set(sections.map((s) => s.offset)).size).toBe(3);
  });

  it('leaves offsets alone when nothing improves', () => {
    const sections = [{ id: 'A', areaHa: 5, offset: 0, rotation: same() }];
    autoStagger(farm, sections);
    expect(sections[0].offset).toBe(0);
  });
});
