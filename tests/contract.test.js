/**
 * The engine of the app (the algorithm in the browser) must respect the contract
 * 2.0 exactly: it is what any other engine (a server) is compared to.
 */
import { readFileSync } from 'node:fs';
import { describe, expect, it, vi } from 'vitest';
import Ajv from 'ajv';
import { CASES } from '../backend/contract/cases.js';
import { createAlgorithmEngine, WEATHER_YEARS } from '../backend/algorithmEngine.js';
import { demoFarmWeather } from '../backend/algorithm/sources/DemoFarmWeather.js';

const schema = JSON.parse(
  readFileSync(new URL('../backend/contract/field-shift.schema.json', import.meta.url), 'utf8'),
);
const ajv = new Ajv({ allErrors: true, strict: false });
ajv.addSchema(schema);
const validator = (def) => ajv.getSchema(`field-shift#/definitions/${def}`);
const expectValid = (def, data) => {
  const v = validator(def);
  expect(v(data), JSON.stringify(v.errors?.slice(0, 5), null, 2)).toBe(true);
};

const offline = createAlgorithmEngine({ useRealWeather: false });

describe('contract 2.0', () => {
  for (const [name, input] of Object.entries(CASES)) {
    it(`"${name}": valid input, valid plan, one plan per section`, async () => {
      expectValid('FarmInput', input);
      const plan = await offline.planFarm(input);
      expectValid('FarmPlan', plan);
      expect(plan.sections.map((s) => s.id)).toEqual(input.sections.map((s) => s.id));
      const cycles = input.farm.time.horizonYears / input.farm.time.cycleYears;
      for (const s of plan.sections) expect(s.cycles).toHaveLength(cycles);
      expect(plan.meta.demo).toBe(true);
    });
  }

  it('demo farm: sections A and B follow the worked example of the algorithm', async () => {
    const plan = await offline.planFarm(CASES['ferme-demo']);
    const [a, b] = plan.sections;
    expect(a.cycles[0]).toMatchObject({ years: [2027, 2030], decision: 'changer' });
    expect(a.cycles[0].chosen.sheets).toEqual(['jachere', 'soya', 'jachere', 'ble-automne']);
    expect(a.cycles[0].referenceAlerts[0].message).toMatch(/Soya après Soya/);
    expect(a.cycles[2].decision).toBe('garder');
    expect(b.cycles[0].years).toEqual([2028, 2031]);
    expect(b.cycles[0].chosen.label).toBe('Maïs (+ seigle) → Jachère → Luzerne ×2 [2 pos.]');
    expect(b.cycles[0].removed.map((r) => r.sheet)).toEqual(['luzerne-3']);
  });

  it('uses NASA POWER when it answers, and says so', async () => {
    const demo = demoFarmWeather();
    const fetchWeather = vi.fn(async () => ({
      firstYear: WEATHER_YEARS.first,
      lastYear: WEATHER_YEARS.last,
      tmax: demo.tmax,
      tmin: demo.tmin,
      rain: demo.rain,
    }));
    const engine = createAlgorithmEngine({ fetchWeather });
    const plan = await engine.planFarm(CASES['ferme-demo']);
    expect(fetchWeather).toHaveBeenCalledWith(45.6287, -72.94815, {
      firstYear: 1985,
      lastYear: 2024,
    });
    expect(plan.meta.sources.farmWeather.real).toBe(true);
  });

  it('falls back to the fictitious weather when NASA POWER fails', async () => {
    const engine = createAlgorithmEngine({
      fetchWeather: vi.fn(async () => Promise.reject(new Error('offline'))),
    });
    const plan = await engine.planFarm(CASES['ferme-demo']);
    expect(plan.meta.sources.farmWeather.real).toBe(false);
    expect(plan.sections).toHaveLength(4);
  });

  it('rejects an invalid input (unknown crop)', () => {
    const bad = structuredClone(CASES['ferme-demo']);
    bad.sections[0].currentRotation = ['riz'];
    expect(validator('FarmInput')(bad)).toBe(false);
  });
});
