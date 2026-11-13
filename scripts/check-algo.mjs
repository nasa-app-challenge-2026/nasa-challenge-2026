#!/usr/bin/env node
/**
 * Checks that a running algorithm respects the contract.
 *
 *   npm run check:algo -- http://localhost:8000
 *   (or set VITE_ALGO_URL)
 *
 * Sends every example input to the three endpoints and validates each answer
 * against contract/field-shift.schema.json. Exit code 1 if anything fails.
 */
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import Ajv from 'ajv';
import { CASES } from '../contract/cases.js';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const schema = JSON.parse(readFileSync(join(root, 'contract', 'field-shift.schema.json'), 'utf8'));
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

async function post(path, body) {
  const res = await fetch(`${baseUrl}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path} → HTTP ${res.status}`);
  return res.json();
}

let failures = 0;
const report = (label, errors) => {
  if (errors.length === 0) console.log(`  ✓ ${label}`);
  else {
    failures++;
    console.log(`  ✗ ${label}`);
    errors.slice(0, 8).forEach((e) => console.log(`      ${e}`));
  }
};

console.log(`Vérification de ${baseUrl}\n`);
for (const [name, input] of Object.entries(CASES)) {
  try {
    const plan = await post('/evaluate', input);
    const errors = check('FarmPlan', plan);
    if (plan.sections?.length !== input.sections.length) {
      errors.push('sections : il faut un résultat par section, dans le même ordre');
    }
    plan.sections?.forEach((s, i) => {
      if (s.id !== input.sections[i]?.id)
        errors.push(`sections[${i}].id devrait être ${input.sections[i]?.id}`);
    });
    report(`/evaluate · ${name}`, errors);
  } catch (e) {
    report(`/evaluate · ${name}`, [e.message]);
  }
}
const demo = CASES['ferme-demo'];
for (const years of [3, 4, 5]) {
  try {
    const r = await post('/propose', { farm: demo, sectionId: 'A', cycleYears: years });
    const errors = check('ProposeResponse', r);
    const total = (r.rotation || []).reduce((n, e) => n + (e.years || 1), 0);
    if (total !== years) errors.push(`la rotation proposée dure ${total} ans au lieu de ${years}`);
    report(`/propose · cycle de ${years} ans`, errors);
  } catch (e) {
    report(`/propose · cycle de ${years} ans`, [e.message]);
  }
}
try {
  const r = await post('/field-data', { farm: demo, sectionId: 'A' });
  report('/field-data · section A', check('FieldDataResponse', r));
} catch (e) {
  report('/field-data · section A', [e.message]);
}

console.log(failures ? `\n${failures} vérification(s) en échec.` : '\nTout respecte le contrat.');
process.exit(failures ? 1 : 0);
