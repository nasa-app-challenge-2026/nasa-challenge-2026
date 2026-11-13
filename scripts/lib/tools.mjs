/**
 * Shared helpers for `npm install` (setup.mjs) and `npm run dev` (dev.mjs):
 * find or install uv (the Python tool used by apps/api), and run npm in a subfolder.
 */
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

export const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
export const isWin = process.platform === 'win32';

/** Path to the uv binary, or null. Also looks where the official installer puts it. */
export function findUv() {
  if (spawnSync('uv', ['--version'], { stdio: 'ignore' }).status === 0) return 'uv';
  const exe = isWin ? 'uv.exe' : 'uv';
  const dirs = [
    process.env.UV_INSTALL_DIR,
    process.env.XDG_BIN_HOME,
    join(homedir(), '.local', 'bin'),
    join(homedir(), '.cargo', 'bin'),
  ].filter(Boolean);
  return dirs.map((d) => join(d, exe)).find((p) => existsSync(p)) ?? null;
}

/** Runs the official uv installer (https://docs.astral.sh/uv/). Returns the uv path or null. */
export function installUv() {
  const [cmd, args] = isWin
    ? [
        'powershell',
        [
          '-NoProfile',
          '-ExecutionPolicy',
          'ByPass',
          '-Command',
          'irm https://astral.sh/uv/install.ps1 | iex',
        ],
      ]
    : ['sh', ['-c', 'curl -LsSf https://astral.sh/uv/install.sh | sh']];
  spawnSync(cmd, args, { stdio: 'inherit' });
  return findUv();
}

/** [command, args] to run npm without a shell (works with spaces in paths, on every OS). */
export function npmCommand(args) {
  const cli = process.env.npm_execpath;
  if (cli && cli.endsWith('.js')) return [process.execPath, [cli, ...args]];
  return [isWin ? 'npm.cmd' : 'npm', args];
}
