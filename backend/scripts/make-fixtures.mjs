#!/usr/bin/env node
/**
 * Writes backend/contract/examples/: one FarmInput per reference case, and the plan
 * the algorithm returns for it (fictitious weather, so the files never depend on
 * the network).
 *   npm run fixtures
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { CASES } from '../contract/cases.js';
import { createAlgorithmEngine } from '../algorithmEngine.js';

const FIXED_GENERATION_TIME = '2026-11-13T00:00:00.000Z';
const out = fileURLToPath(new URL('../contract/examples/', import.meta.url));
mkdirSync(out, { recursive: true });

const engine = createAlgorithmEngine({ useRealWeather: false });
const write = (name, data) =>
  writeFileSync(join(out, name), `${JSON.stringify(data, null, 2)}\n`, 'utf8');

for (const [name, input] of Object.entries(CASES)) {
  write(`${name}.input.json`, input);
  const plan = await engine.planFarm(input);
  plan.meta.generatedAt = FIXED_GENERATION_TIME;
  write(`${name}.plan.json`, plan);
}
console.log(`Exemples écrits dans ${out}`);
