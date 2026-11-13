#!/usr/bin/env node
/**
 * Runs after `npm install` at the root (postinstall), so one command sets up the whole monorepo:
 *   1. the React app's dependencies (apps/web)
 *   2. uv, installed automatically if missing
 *   3. the Python API (apps/api): uv downloads Python 3.12 itself if needed
 * Never fails the install: if a step breaks, it prints what to do and moves on.
 * Skipped in CI (each job installs its own tools) or with FIELDSHIFT_SKIP_SETUP=1.
 *   npm run setup   re-runs it by hand
 */
import { spawnSync } from 'node:child_process';
import { join } from 'node:path';
import { findUv, installUv, npmCommand, root } from './lib/tools.mjs';

if (process.env.CI || process.env.FIELDSHIFT_SKIP_SETUP) process.exit(0);

const log = (msg) => console.log(`\n\x1b[32m[field-shift]\x1b[0m ${msg}`);
const warn = (msg) => console.warn(`\n\x1b[33m[field-shift] ${msg}\x1b[0m`);
const run = (cmd, args, cwd) => spawnSync(cmd, args, { cwd, stdio: 'inherit' }).status === 0;

log('Dépendances de apps/web…');
const [npm, npmArgs] = npmCommand(['install', '--no-save', '--no-audit', '--no-fund']);
if (!run(npm, npmArgs, join(root, 'apps', 'web'))) {
  warn('apps/web : npm install a échoué. Relance `npm run setup`.');
}

let uv = findUv();
if (!uv) {
  log('uv introuvable, installation automatique…');
  uv = installUv();
}
if (!uv) {
  warn("Impossible d'installer uv. L'API ne tournera pas (le front marche quand même).");
  warn('Installe-le à la main : https://docs.astral.sh/uv/ puis relance `npm run setup`.');
  process.exit(0);
}

log('API Python (apps/api)…');
if (!run(uv, ['sync', '--frozen'], join(root, 'apps', 'api'))) {
  warn('apps/api : uv sync a échoué. Relance `npm run setup`.');
}

log('Prêt. Lance `npm run dev`.');
