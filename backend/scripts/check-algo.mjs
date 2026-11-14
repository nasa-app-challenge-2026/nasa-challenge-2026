#!/usr/bin/env node
/**
 * Checks that a running algorithm server respects the contract (v2.0).
 *
 *   npm run check:algo -- http://localhost:8000
 *   (or set VITE_ALGO_URL)
 *
 * Sends every reference input to POST /plan and validates each answer against
 * backend/contract/field-shift.schema.json. Exit code 1 if anything fails.
 */
import { readFileSync } from 'node:fs';
import Ajv from 'ajv';
import { CASES } from '../contract/cases.js';

const schema = JSON.parse(
  readFileSync(new URL('../contract/field-shift.schema.json', import.meta.url), 'utf8'),
);
const ajv = new Ajv({ allErrors: true, strict: false });
ajv.addSchema(schema);
const check = (def, data) => {
  const validate = ajv.getSchema(`field-shift#/definitions/${def}`);
  return validate(data) ? [] : validate.errors.map((e) => `${e.instancePath || '/'} ${e.message}`);
};

const baseUrl = (process.argv[2] || process.env.VITE_ALGO_URL || '').replace(/\/+$/, '');
if (!baseUrl) {
  console.error('Donnez l’adresse de l’algo : npm run check:algo -- http://localhost:8000');
  process.exit(1);
}

let failures = 0;
console.log(`Vérification de ${baseUrl}\n`);
for (const [name, input] of Object.entries(CASES)) {
  const errors = [];
  try {
    const res = await fetch(`${baseUrl}/plan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    });
    if (!res.ok) throw new Error(`/plan → HTTP ${res.status}`);
    const plan = await res.json();
    errors.push(...check('FarmPlan', plan));
    if (plan.sections?.map((s) => s.id).join() !== input.sections.map((s) => s.id).join())
      errors.push('sections : il faut un plan par section, dans le même ordre');
    const cycles = input.farm.time.horizonYears / input.farm.time.cycleYears;
    plan.sections?.forEach((s) => {
      if (s.cycles.length !== cycles && s.cycles.at(-1)?.decision !== 'aucune')
        errors.push(`section ${s.id} : ${s.cycles.length} cycles au lieu de ${cycles}`);
    });
  } catch (e) {
    errors.push(e.message);
  }
  if (errors.length) {
    failures++;
    console.log(`  ✗ /plan · ${name}`);
    errors.slice(0, 8).forEach((e) => console.log(`      ${e}`));
  } else console.log(`  ✓ /plan · ${name}`);
}
console.log(failures ? `\n${failures} vérification(s) en échec.` : '\nTout respecte le contrat.');
process.exit(failures ? 1 : 0);
