/**
 * The front end and the algorithm server agree on the contract 2.0: the example files respect the
 * schema, the ids of the screens are the ids of the schema, and the HTTP client reads the server's
 * answers (and refusals) the right way. The server proves its own side in backend/server/tests.
 */
import { readFileSync, readdirSync } from 'node:fs';
import { describe, expect, it, vi } from 'vitest';
import Ajv from 'ajv';
import { createRemoteEngine, EngineError } from '../backend/remoteEngine.js';
import { createEngine } from '../backend/index.js';
import { CRITERIA_IDS } from '../data/reference/criteria.js';
import { CROPS, SHEETS } from '../data/reference/crops.js';
import { DEMO_FARM } from '../data/reference/demoFarm.js';
import { SOIL_DISEASES } from '../data/reference/diseases.js';
import { CYCLE_YEARS, FREQUENCIES, RESERVE_MODES } from '../data/reference/planning.js';

const CONTRACT = new URL('../backend/contract/', import.meta.url);
const read = (path) => JSON.parse(readFileSync(new URL(path, CONTRACT), 'utf8'));
const schema = read('field-shift.schema.json');
const ajv = new Ajv({ allErrors: true, strict: false });
ajv.addSchema(schema);
const check = (def, data) => {
  const validate = ajv.getSchema(`field-shift#/definitions/${def}`);
  return validate(data) ? [] : validate.errors.map((e) => `${e.instancePath} ${e.message}`);
};

const examples = readdirSync(new URL('examples/', CONTRACT));
const inputs = examples.filter((f) => f.endsWith('.input.json'));
const plans = examples.filter((f) => f.endsWith('.plan.json'));
const enumOf = (def) => schema.definitions[def].enum;

describe('examples of the contract', () => {
  it('there are inputs and plans', () => {
    expect(inputs.length).toBeGreaterThanOrEqual(3);
    expect(plans.length).toBe(inputs.length);
  });

  for (const file of inputs)
    it(`${file} is a valid FarmInput`, () =>
      expect(check('FarmInput', read(`examples/${file}`))).toEqual([]));

  for (const file of plans)
    it(`${file} is a valid FarmPlan`, () =>
      expect(check('FarmPlan', read(`examples/${file}`))).toEqual([]));

  it('the demo farm of the app is the "ferme-demo" example', () => {
    const example = read('examples/ferme-demo.input.json');
    delete example.today; // the example fixes the date of the plan; the app lets the server choose it
    expect(DEMO_FARM).toEqual(example);
  });

  it('the schema refuses an unknown crop and a cycle that is too long', () => {
    const bad = structuredClone(DEMO_FARM);
    bad.sections[0].currentRotation = ['riz'];
    expect(check('FarmInput', bad)).not.toEqual([]);
    const long = structuredClone(DEMO_FARM);
    long.farm.time.cycleYears = 7;
    expect(check('FarmInput', long)).not.toEqual([]);
  });
});

describe('the screens use the ids of the schema', () => {
  it('crops, sheets, criteria and soil diseases', () => {
    expect(Object.keys(CROPS).sort()).toEqual([...enumOf('CropId')].sort());
    expect(Object.keys(SHEETS).sort()).toEqual([...enumOf('SheetId')].sort());
    expect([...CRITERIA_IDS]).toEqual(enumOf('CriterionId'));
    expect(Object.keys(SOIL_DISEASES).sort()).toEqual([...enumOf('DiseaseId')].sort());
  });

  it('cycle, frequencies and reserve modes', () => {
    const farm = schema.definitions.FarmInput.properties.farm.properties;
    const { cycleYears, frequencyMonths } = farm.time.properties;
    expect([cycleYears.minimum, cycleYears.maximum]).toEqual([CYCLE_YEARS.min, CYCLE_YEARS.max]);
    expect(FREQUENCIES.map((f) => f.months)).toEqual(frequencyMonths.enum);
    expect(Object.keys(RESERVE_MODES).sort()).toEqual([...farm.seeds.properties.mode.enum].sort());
  });
});

describe('the client of the algorithm server', () => {
  const answer = (status, body) =>
    vi.fn(async () => ({
      ok: status < 400,
      status,
      json: async () => body,
      text: async () => (typeof body === 'string' ? body : JSON.stringify(body)),
    }));
  const engine = (fetchMock) => {
    vi.stubGlobal('fetch', fetchMock);
    return createRemoteEngine({ baseUrl: 'http://serveur:8000/' });
  };

  it('posts the farm to /plan and returns the plan', async () => {
    const plan = read('examples/ferme-demo.plan.json');
    const fetchMock = answer(200, plan);
    expect(await engine(fetchMock).planFarm(DEMO_FARM)).toEqual(plan);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('http://serveur:8000/plan');
    expect(init).toMatchObject({ method: 'POST', headers: { 'Content-Type': 'application/json' } });
    expect(JSON.parse(init.body)).toEqual(DEMO_FARM);
  });

  it('turns a refusal of the server into a readable sentence', async () => {
    const refusal = {
      detail: [
        { loc: ['body', 'farm', 'time'], msg: 'Value error, Le cycle doit durer de 2 à 6 ans.' },
        { loc: ['body', 'sections', 0, 'currentCrop'], msg: 'culture inconnue : riz' },
      ],
    };
    const error = await engine(answer(422, refusal))
      .planFarm(DEMO_FARM)
      .catch((e) => e);
    expect(error).toBeInstanceOf(EngineError);
    expect(error.status).toBe(422);
    expect(error.message).toContain('farm › time : Le cycle doit durer de 2 à 6 ans.');
    expect(error.message).toContain('sections › 0 › currentCrop : culture inconnue : riz');
  });

  it('says so when the server cannot be reached', async () => {
    const down = vi.fn(async () => Promise.reject(new TypeError('fetch failed')));
    const error = await engine(down)
      .planFarm(DEMO_FARM)
      .catch((e) => e);
    expect(error.message).toMatch(
      /Impossible de joindre l’algorithme \(http:\/\/serveur:8000\/plan\)/,
    );
  });

  it('says so when no server is configured, without breaking the app at start', async () => {
    const error = await createRemoteEngine({ baseUrl: '' })
      .planFarm(DEMO_FARM)
      .catch((e) => e);
    expect(error.message).toMatch(/VITE_ALGO_URL/);
  });

  it('uses VITE_ALGO_URL, the local server in development, nothing in production', async () => {
    const fetchMock = answer(200, {});
    vi.stubGlobal('fetch', fetchMock);
    await createEngine({ VITE_ALGO_URL: 'https://api.exemple.org' }).planFarm({});
    await createEngine({ DEV: true }).planFarm({});
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      'https://api.exemple.org/plan',
      'http://localhost:8000/plan',
    ]);
    const error = await createEngine({ DEV: false })
      .planFarm({})
      .catch((e) => e);
    expect(error.message).toMatch(/VITE_ALGO_URL/);
  });
});
