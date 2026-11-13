#!/usr/bin/env node
/**
 * `npm run dev`: starts everything at once, with prefixed logs. Ctrl+C stops it all.
 *   front   Field Shift front (repo root)   http://localhost:5173
 *   web     React app (apps/web)            http://localhost:5174
 *   api     Python API (apps/api)           http://127.0.0.1:8000/api/docs
 * `npm run dev:front` starts only the root front.
 */
import { spawn, spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { findUv, isWin, npmCommand, root } from './lib/tools.mjs';

const env = { ...process.env, FORCE_COLOR: '1' };
const children = [];

function start(name, color, cmd, args, cwd) {
  const child = spawn(cmd, args, { cwd, env });
  const tag = `\x1b[${color}m[${name}]\x1b[0m `;
  for (const stream of [child.stdout, child.stderr]) {
    let rest = '';
    stream.on('data', (chunk) => {
      const lines = (rest + chunk).split(/\r?\n/);
      rest = lines.pop();
      for (const line of lines) process.stdout.write(tag + line + '\n');
    });
  }
  child.on('error', (err) => console.error(`${tag}impossible de démarrer : ${err.message}`));
  child.on('exit', (code) => console.log(`${tag}arrêté (code ${code ?? 'signal'})`));
  children.push(child);
}

function stopAll() {
  for (const child of children) {
    if (child.exitCode !== null || !child.pid) continue;
    if (isWin) spawnSync('taskkill', ['/pid', String(child.pid), '/T', '/F'], { stdio: 'ignore' });
    else child.kill('SIGTERM');
  }
  process.exit(0);
}
process.on('SIGINT', stopAll);
process.on('SIGTERM', stopAll);

const vite = join(root, 'node_modules', 'vite', 'bin', 'vite.js');
start('front', 32, process.execPath, [vite, '--port', '5173', '--strictPort'], root);

const web = join(root, 'apps', 'web');
if (existsSync(join(web, 'node_modules'))) {
  const [npm, args] = npmCommand(['run', 'dev', '--', '--port', '5174', '--strictPort']);
  start('web', 36, npm, args, web);
} else {
  console.warn('[web] dépendances absentes, lance `npm run setup`.');
}

const uv = findUv();
if (uv) {
  const api = join(root, 'apps', 'api');
  const args = [
    'run',
    '--frozen',
    'uvicorn',
    '--factory',
    'fieldshift.api.app:create_app',
    '--reload',
  ];
  start('api', 35, uv, [...args, '--port', '8000'], api);
} else {
  console.warn('[api] uv introuvable, lance `npm run setup`. Le front marche sans.');
}

console.log(
  '\n  Front Field Shift  http://localhost:5173' +
    '\n  App React          http://localhost:5174' +
    '\n  API (docs)         http://127.0.0.1:8000/api/docs\n',
);
