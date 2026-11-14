/**
 * The four layers (docs/ARCHITECTURE.md), from top to bottom:
 *
 *   frontend → backend → application → data
 *
 * A file may import its own layer and the layers below it, never a layer above.
 * Two more rules keep the screens simple:
 *   - in frontend/, only main.js imports backend/ (it hands the engine to the app);
 *   - frontend/ never imports data/access/: network and storage go through `app`.
 */
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { dirname, join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const LAYERS = ['frontend', 'backend', 'application', 'data'];

const toPosix = (path) => path.split(sep).join('/');

/** Repository-relative paths of the JS files of one layer. */
function filesOf(layer) {
  return readdirSync(join(ROOT, layer), { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile() && /\.m?js$/.test(entry.name))
    .map((entry) => toPosix(relative(ROOT, join(entry.parentPath ?? entry.path, entry.name))));
}

const IMPORT = /^\s*import\s+(?:[^'";]*?\s+from\s+)?['"]([^'"]+)['"]/gm;
const REEXPORT = /^\s*export\s+(?:\*|\{[^}]*\})\s+from\s+['"]([^'"]+)['"]/gm;

/** Repository-relative targets of the relative imports of a file (packages are skipped). */
function importsOf(file) {
  const code = readFileSync(join(ROOT, file), 'utf8');
  return [...code.matchAll(IMPORT), ...code.matchAll(REEXPORT)]
    .map((m) => m[1])
    .filter((spec) => spec.startsWith('.'))
    .map((spec) => toPosix(relative(ROOT, join(ROOT, dirname(file), spec))));
}

const layerOf = (path) => LAYERS.indexOf(path.split('/')[0]);

/** Why `from` must not import `to`, or null when the import is allowed. */
function violation(from, to) {
  const a = layerOf(from);
  const b = layerOf(to);
  if (a === -1 || b === -1) return null;
  if (b < a) return `${LAYERS[a]} must not depend on ${LAYERS[b]}, a layer above it`;
  if (LAYERS[a] === 'frontend' && LAYERS[b] === 'backend' && from !== 'frontend/main.js') {
    return 'only frontend/main.js plugs the engine in; screens go through app';
  }
  if (LAYERS[a] === 'frontend' && to.startsWith('data/access/')) {
    return 'network and storage go through the application (app)';
  }
  return null;
}

describe('layered architecture', () => {
  const files = LAYERS.flatMap(filesOf);
  const edges = files.flatMap((from) => importsOf(from).map((to) => ({ from, to })));

  it('finds the four layers and their imports', () => {
    for (const layer of LAYERS) expect(files.some((f) => f.startsWith(`${layer}/`))).toBe(true);
    expect(edges.length).toBeGreaterThan(50);
  });

  it('every relative import points to an existing file', () => {
    expect(edges.filter(({ to }) => !existsSync(join(ROOT, to)))).toEqual([]);
  });

  it('imports only go down: frontend → backend → application → data', () => {
    const bad = edges
      .map(({ from, to }) => ({ from, to, why: violation(from, to) }))
      .filter((e) => e.why)
      .map((e) => `${e.from} → ${e.to}: ${e.why}`);
    expect(bad).toEqual([]);
  });

  it('the rules catch what they should', () => {
    expect(violation('data/reference/crops.js', 'application/rules/seeds.js')).not.toBeNull();
    expect(violation('application/app.js', 'backend/index.js')).not.toBeNull();
    expect(violation('application/app.js', 'frontend/lib/html.js')).not.toBeNull();
    expect(violation('frontend/screens/tableau.js', 'backend/index.js')).not.toBeNull();
    expect(violation('frontend/screens/localisation.js', 'data/access/geocode.js')).not.toBeNull();
    expect(violation('frontend/main.js', 'backend/index.js')).toBeNull();
    expect(
      violation('backend/algorithm/input/FarmInputReader.js', 'application/rules/timeSettings.js'),
    ).toBeNull();
    expect(violation('frontend/screens/plan.js', 'data/reference/crops.js')).toBeNull();
  });
});
