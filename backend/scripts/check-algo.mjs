#!/usr/bin/env node
/**
 * Checks that a running algorithm server respects the contract (v2.0).
 *
 *   npm run check:algo -- http://localhost:8000
 *   (or set VITE_ALGO_URL)
 *
 * Sends every reference input (backend/contract/examples/*.input.json) to POST /plan and validates
 * each answer against backend/contract/field-shift.schema.json. Exit code 1 if anything fails.
 */
import { readFileSync, readdirSync } from 'node:fs';
import Ajv from 'ajv';

const CONTRACT = new URL('../contract/', import.meta.url);
const INPUT_SUFFIX = '.input.json';

const schema = JSON.parse(readFileSync(new URL('field-shift.schema.json', CONTRACT), 'utf8'));
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

const examples = readdirSync(new URL('examples/', CONTRACT)).filter((f) =>
  f.endsWith(INPUT_SUFFIX),
);
let failures = 0;
console.log(`Vérification de ${baseUrl}\n`);
for (const file of examples) {
  const name = file.slice(0, -INPUT_SUFFIX.length);
  const input = JSON.parse(readFileSync(new URL(`examples/${file}`, CONTRACT), 'utf8'));
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
    const { cycleYears, horizonYears } = input.farm.time;
    for (const s of plan.sections ?? []) {
      const infeasible = s.cycles.at(-1)?.decision === 'aucune';
      if (s.cycles.length !== horizonYears / cycleYears && !infeasible)
        errors.push(
          `section ${s.id} : ${s.cycles.length} cycles au lieu de ${horizonYears / cycleYears}`,
        );
    }
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
process.exitCode = failures ? 1 : 0; // not process.exit(): it crashes Node on Windows while the fetch sockets close
