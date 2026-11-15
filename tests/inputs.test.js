/** Step 1 (the farmer's inputs) and the reading of the plan by the screens. */
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import {
  TimeSettings,
  allowedFrequencies,
  allowedHorizons,
  nearestHorizon,
} from '../application/rules/timeSettings.js';
import { moveCriterion, unrankedCriteria, weightShares } from '../application/rules/priorities.js';
import {
  addSeeds,
  deriveSeeds,
  getSeeds,
  setReserveMode,
  toggleSeed,
} from '../application/rules/seeds.js';
import {
  blankSection,
  historyYearsToAsk,
  moveInRotation,
  removeFromRotation,
  sectionInputProblems,
  setCurrentCrop,
  setHistoryCrop,
} from '../application/rules/sectionInputs.js';
import {
  cropOfYear,
  cycleOfYear,
  farmMix,
  planYears,
  positionYear,
} from '../application/rules/planView.js';
import { DEMO_FARM } from '../data/reference/demoFarm.js';

const example = (name) =>
  JSON.parse(
    readFileSync(new URL(`../backend/contract/examples/${name}`, import.meta.url), 'utf8'),
  );

describe('time settings (block C)', () => {
  it('lays out the positions of a cycle', () => {
    const t = new TimeSettings({ cycleYears: 4, frequencyMonths: 6, horizonYears: 12 });
    expect([t.positionsPerCycle, t.cycleCount, t.positionStartMonth]).toEqual([8, 3, 1]);
  });

  it('refuses invalid settings', () => {
    expect(
      () => new TimeSettings({ cycleYears: 7, frequencyMonths: 12, horizonYears: 14 }),
    ).toThrow(/2 à 6/);
    expect(
      () => new TimeSettings({ cycleYears: 4, frequencyMonths: 12, horizonYears: 10 }),
    ).toThrow(/multiple/);
  });

  it('offers only valid frequencies and horizons up to 2060', () => {
    expect(allowedFrequencies(3).map((f) => f.months)).toEqual([12, 6, 4]);
    expect(allowedHorizons(4, 2027)).toEqual([4, 8, 12, 16, 20, 24, 28, 32]);
    expect(nearestHorizon(5, 12, 2027)).toBe(10);
  });
});

describe('priorities (block D)', () => {
  it('moves and lists criteria', () => {
    expect(moveCriterion(['a', 'b'], 1, -1)).toEqual(['b', 'a']);
    expect(moveCriterion(['a', 'b'], 0, -1)).toEqual(['a', 'b']);
    expect(unrankedCriteria(['eau'])).not.toContain('eau');
  });

  it('shows the weights the algorithm computed, only for the ranking they come from', () => {
    const plan = example('ferme-demo.plan.json');
    const ranking = plan.settings.priorities;
    const shares = weightShares(plan, ranking);
    expect(Object.values(shares).reduce((a, b) => a + b, 0)).toBeGreaterThanOrEqual(99);
    expect(shares[ranking[0]]).toBeGreaterThan(shares[ranking[1]]);
    expect(weightShares(plan, [...ranking].reverse())).toBeNull();
    expect(weightShares(null, ranking)).toBeNull();
  });
});

describe('seed reserve (block B)', () => {
  it('derives, toggles and keeps the catalogue order', () => {
    const farm = structuredClone(DEMO_FARM);
    expect(deriveSeeds(farm).crops).toEqual(['mais', 'soya', 'ble-automne', 'luzerne']);
    toggleSeed(farm, 'orge');
    toggleSeed(farm, 'mais');
    expect(getSeeds(farm).crops).toEqual(['soya', 'ble-automne', 'orge', 'seigle']);
    addSeeds(farm, ['canola', 'mais']);
    setReserveMode(farm, 'uniquement');
    expect(getSeeds(farm)).toEqual({
      crops: ['mais', 'soya', 'ble-automne', 'orge', 'canola', 'seigle'],
      mode: 'uniquement',
    });
  });
});

describe('section inputs (block A)', () => {
  it('asks the years before the crop in place', () => {
    const s = { ...blankSection('X'), currentCrop: 'luzerne-3', currentHarvest: '2027-09' };
    expect(historyYearsToAsk(s, 2026, 3)).toEqual([2024, 2023, 2022]);
    expect(historyYearsToAsk(blankSection('Y'), 2026, 2)).toEqual([2026, 2025]);
  });

  it('edits the crop in place, the history and the rotation', () => {
    const s = blankSection('X');
    setCurrentCrop(s, 'mais', '2026-10');
    expect(s).toMatchObject({
      currentHarvest: '2026-10',
      currentRotation: ['mais'],
      rotationPosition: 0,
    });
    setHistoryCrop(s, 2025, 'soya');
    setHistoryCrop(s, 2024, 'mais');
    setHistoryCrop(s, 2025, null);
    expect(s.history).toEqual([{ year: 2024, crop: 'mais' }]);
    s.currentRotation = ['mais', 'soya', 'ble-automne'];
    moveInRotation(s, 0, 1);
    expect([s.currentRotation, s.rotationPosition]).toEqual([['soya', 'mais', 'ble-automne'], 1]);
    removeFromRotation(s, 2);
    expect(sectionInputProblems(s)).toEqual([]);
    s.rotationPosition = 0;
    expect(sectionInputProblems(s)[0]).toMatch(/position/);
  });
});

describe('reading the plan of the server', () => {
  const plan = example('ferme-demo.plan.json');
  const farm = example('ferme-demo.input.json');
  const [a, b] = plan.sections;

  it('finds the years, cycles and crops of each year', () => {
    expect(planYears(plan)).toEqual({ first: 2027, last: 2039 });
    expect(cycleOfYear(a, 2032).index).toBe(2);
    expect(positionYear(a.cycles[0], 4, 12)).toBe(2030);
    expect(cropOfYear(farm.sections[0], a, 2028, 12)).toEqual({
      id: 'luzerne-2',
      source: 'plan',
    });
    expect(cropOfYear(farm.sections[0], a, 2027, 12)).toEqual({ id: 'jachere', source: 'plan' });
    expect(cropOfYear(farm.sections[1], b, 2027, 12)).toEqual({
      id: 'luzerne-3',
      source: 'en-place',
    });
    expect(cropOfYear(farm.sections[1], b, 2031, 12).id).toBe('luzerne-2');
  });

  it('sums the area of each crop on the farm', () => {
    const mix = farmMix(farm, plan, 2028);
    expect(Object.values(mix).reduce((x, y) => x + y, 0)).toBe(36);
  });
});
