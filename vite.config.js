import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';

const fromRepo = (path) => fileURLToPath(new URL(path, import.meta.url));

/**
 * The page (index.html, public/) lives in frontend/; Vite follows its imports
 * into backend/, application/ and data/ (see docs/ARCHITECTURE.md).
 * `.env.local` stays at the repository root and the build goes to dist/.
 * `base: './'` makes the build work on GitHub Pages under any repo name.
 */
export default defineConfig({
  root: fromRepo('frontend'),
  envDir: fromRepo('.'),
  base: './',
  server: { port: 5173, open: false },
  build: { outDir: fromRepo('dist'), emptyOutDir: true, sourcemap: true },
  test: {
    root: fromRepo('.'),
    environment: 'node',
    include: ['tests/**/*.test.js'],
  },
});
