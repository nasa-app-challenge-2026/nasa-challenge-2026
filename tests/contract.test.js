/**
 * The demo engine must respect the contract exactly: it is the reference the
 * real algorithm is compared to.
 */
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import Ajv from 'ajv';
import { CASES } from '../contract/cases.js';
import { createMockEngine } from '../src/algo/mockEngine.js';

const schema = JSON.parse(
  readFileSync(new URL('../contract/field-shift.schema.json', import.meta.url), 'utf8'),
);
const ajv = new Ajv({ allErrors: true, strict: false });
ajv.addSchema(schema);
const validator = (def) => ajv.getSchema(`field-shift#/definitions/${def}`);
const expectValid = (def, data) => {
  const v = validator(def);
  const ok = v(data);
  expect(ok, JSON.stringify(v.errors, null, 2)).toBe(true);
};

const engine = createMockEngine();

describe('contract', () => {
  for (const [name, input] of Object.entries(CASES)) {
    it(`example input "${name}" is a valid FarmInput`, () => expectValid('FarmInput', input));

    it(`demo engine answers "${name}" with a valid FarmPlan`, async () => {
      const plan = await engine.evaluateFarm(input);
      expectValid('FarmPlan', plan);
      expect(plan.sections.map((s) => s.id)).toEqual(input.sections.map((s) => s.id));
      expect(plan.meta.demo).toBe(true);
    });
  }

  it('proposeRotation returns a rotation of the requested length', async () => {
    for (const cycleYears of [2, 3, 4, 5, 6]) {
      const r = await engine.proposeRotation({
        farm: CASES['ferme-demo'],
        sectionId: 'A',
        cycleYears,
      });
      expectValid('ProposeResponse', r);
      expect(r.rotation.reduce((n, e) => n + e.years, 0)).toBe(cycleYears);
    }
  });

  it('getFieldData returns valid metrics, from sensors when enabled', async () => {
    const farm = structuredClone(CASES['ferme-demo']);
    const r1 = await engine.getFieldData({ farm, sectionId: 'A' });
    expectValid('FieldDataResponse', r1);
    farm.farm.sensors = true;
    const r2 = await engine.getFieldData({ farm, sectionId: 'A' });
    expect(r2.metrics.find((m) => m.id === 'soilMoisture').fromSensors).toBe(true);
  });

  it('rejects an invalid input (unknown crop)', () => {
    const bad = structuredClone(CASES['ferme-demo']);
    bad.sections[0].rotation[0].crop = 'riz';
    expect(validator('FarmInput')(bad)).toBe(false);
  });
});
