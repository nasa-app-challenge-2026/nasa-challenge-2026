import { describe, expect, it } from 'vitest';
import { DEMO_FARM } from '../src/data/demoFarm.js';
import { createMockEngine } from '../src/algo/mockEngine.js';
import {
  bestOffsets,
  currentCropConflict,
  firstYear,
  rotationErrors,
  suggestCycleYears,
  toSlots,
} from '../src/lib/rotation.js';
import { addSeeds, deriveSeeds, getSeeds, missingSeeds } from '../src/lib/seeds.js';
import { migrateFarm } from '../src/state/initialState.js';

const R3 = [
  { crop: 'mais', years: 1, cover: null },
  { crop: 'soya', years: 1, cover: null },
  { crop: 'ble', years: 1, cover: null },
];
const farmWith = (seeds, sections) => ({
  ...structuredClone(DEMO_FARM),
  farm: { ...structuredClone(DEMO_FARM.farm), seeds },
  sections,
});
const crops = (rotation) => toSlots(rotation).map((s) => s.crop);

describe('current crop', () => {
  it('flags a one-year crop that would follow itself', () => {
    const s = { id: 'A', currentCrop: 'mais', offset: 0, rotation: R3 };
    expect(currentCropConflict(s)).toMatch(/Maïs deux ans de suite/);
    expect(currentCropConflict(s, 1)).toBeNull();
    expect(currentCropConflict({ ...s, currentCrop: null })).toBeNull();
  });

  it('flags alfalfa starting in the middle of its block', () => {
    const rot = [
      { crop: 'mais', years: 1, cover: null },
      { crop: 'luzerne', years: 3, cover: null },
    ];
    expect(firstYear({ rotation: rot, offset: 2 })).toEqual({ crop: 'luzerne', blockStart: false });
    expect(currentCropConflict({ currentCrop: 'soya', offset: 2, rotation: rot })).toMatch(/bloc/);
    expect(currentCropConflict({ currentCrop: 'luzerne', offset: 2, rotation: rot })).toBeNull();
  });

  it('bestOffsets removes clashes before balancing the farm', () => {
    const farm = { startYear: 2027, horizonYears: 12 };
    const sections = ['A', 'B', 'C'].map((id) => ({
      id,
      areaHa: 5,
      offset: 0,
      currentCrop: 'mais',
      rotation: R3,
    }));
    const { offsets, conflicts, imbalanced } = bestOffsets(farm, sections);
    expect(conflicts).toBe(0);
    expect(imbalanced).toBeGreaterThan(0); // 3 sections, 2 allowed first crops: one year repeats
    for (const s of sections) expect(currentCropConflict(s, offsets[s.id])).toBeNull();
  });
});

describe('seed reserve', () => {
  it('derives the reserve from current crops and rotations', () => {
    const f = farmWith(undefined, [
      {
        id: 'A',
        currentCrop: 'orge',
        offset: 0,
        rotation: [{ crop: 'mais', years: 1, cover: 'seigle' }],
      },
    ]);
    delete f.farm.seeds;
    expect(deriveSeeds(f)).toEqual({ crops: ['mais', 'orge'], covers: ['seigle'] });
    expect(getSeeds(f).crops).toEqual(['mais', 'orge']);
  });

  it('lists missing seeds and adds them in catalogue order', () => {
    const f = farmWith({ crops: ['soya'], covers: [] }, []);
    expect(missingSeeds(f, R3)).toEqual(['mais', 'ble']);
    addSeeds(f, ['ble', 'mais', 'riz']);
    expect(f.farm.seeds.crops).toEqual(['mais', 'soya', 'ble']);
  });

  it('migrates a farm saved before seeds and current crops existed', () => {
    const old = structuredClone(DEMO_FARM);
    delete old.farm.seeds;
    old.sections.forEach((s) => delete s.currentCrop);
    const m = migrateFarm(old);
    expect(m.sections.every((s) => s.currentCrop === null)).toBe(true);
    expect(m.farm.seeds.crops).toEqual(['mais', 'soya', 'ble', 'patate']);
  });

  it('suggests a cycle that uses every seed once', () => {
    expect(suggestCycleYears(['mais', 'soya', 'ble'])).toBe(3);
    expect(suggestCycleYears(['mais', 'soya', 'luzerne'])).toBe(5);
    expect(suggestCycleYears(['mais'])).toBe(2);
    expect(suggestCycleYears(['mais', 'soya', 'ble', 'orge', 'patate', 'luzerne'])).toBe(6);
  });
});

describe('demo engine proposals', () => {
  const engine = createMockEngine();
  const section = (over = {}) => ({
    id: 'A',
    areaHa: 5,
    offset: 0,
    currentCrop: null,
    rotation: R3,
    ...over,
  });

  it('only uses the seeds of the reserve', async () => {
    const farm = farmWith({ crops: ['soya', 'ble', 'orge'], covers: [] }, [section()]);
    const r = await engine.proposeRotation({ farm, sectionId: 'A', cycleYears: 3 });
    expect(new Set(crops(r.rotation))).toEqual(new Set(['soya', 'ble', 'orge']));
    expect(r.rotation.every((e) => e.cover === null)).toBe(true);
    expect(r.missingSeeds).toBeUndefined();
    expect(rotationErrors(r.rotation)).toEqual([]);
  });

  it('never starts with the crop growing now', async () => {
    for (const now of ['mais', 'soya', 'ble']) {
      const farm = farmWith({ crops: ['mais', 'soya', 'ble'], covers: ['trefle'] }, [
        section({ currentCrop: now }),
      ]);
      const r = await engine.proposeRotation({ farm, sectionId: 'A', cycleYears: 3 });
      expect(crops(r.rotation)[0]).not.toBe(now);
      expect(r.reasons.join(' ')).toMatch(/maintenant/);
    }
  });

  it('declares the seeds it had to add when the reserve is not enough', async () => {
    const farm = farmWith({ crops: ['mais'], covers: [] }, [section()]);
    const r = await engine.proposeRotation({ farm, sectionId: 'A', cycleYears: 3 });
    expect(rotationErrors(r.rotation)).toEqual([]);
    expect(r.missingSeeds.length).toBeGreaterThan(0);
    expect(r.missingSeeds).not.toContain('mais');
  });

  it('follows the farmer’s first priority', async () => {
    const seeds = { crops: ['mais', 'soya', 'ble', 'orge', 'patate', 'luzerne'], covers: [] };
    const money = farmWith(seeds, [section()]);
    money.farm.priorities = ['revenu', 'travail', 'resilience', 'sol', 'eau'];
    const soil = farmWith(seeds, [section()]);
    soil.farm.priorities = ['sol', 'eau', 'resilience', 'travail', 'revenu'];
    const a = await engine.proposeRotation({ farm: money, sectionId: 'A', cycleYears: 4 });
    const b = await engine.proposeRotation({ farm: soil, sectionId: 'A', cycleYears: 4 });
    expect(crops(a.rotation)).toContain('patate');
    expect(crops(b.rotation).join()).not.toBe(crops(a.rotation).join());
  });
});
