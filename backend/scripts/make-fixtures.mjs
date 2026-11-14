#!/usr/bin/env node
/**
 * Writes backend/contract/examples/: one input per reference case, plus the
 * demo engine's answer for each (to show the expected *shape* of a real answer).
 *   npm run fixtures
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { CASES } from '../contract/cases.js';
import { createMockEngine } from '../mockEngine.js';

const out = fileURLToPath(new URL('../contract/examples/', import.meta.url));
mkdirSync(out, { recursive: true });

const engine = createMockEngine();
const write = (name, data) =>
  writeFileSync(join(out, name), `${JSON.stringify(data, null, 2)}\n`, 'utf8');

for (const [name, input] of Object.entries(CASES)) {
  write(`${name}.input.json`, input);
  const plan = await engine.evaluateFarm(input);
  plan.meta.generatedAt = '2026-11-12T00:00:00.000Z';
  write(`${name}.plan.mock.json`, plan);
}

const demo = CASES['ferme-demo'];
write('propose.request.json', { farm: demo, sectionId: 'A', cycleYears: 4 });
write(
  'propose.response.mock.json',
  await engine.proposeRotation({ farm: demo, sectionId: 'A', cycleYears: 4 }),
);
write('field-data.request.json', { farm: demo, sectionId: 'A' });
write('field-data.response.mock.json', await engine.getFieldData({ farm: demo, sectionId: 'A' }));

console.log(`Exemples écrits dans ${out}`);
