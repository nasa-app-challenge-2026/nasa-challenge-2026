import { defineConfig } from 'vite';

// `base: './'` makes the build work on GitHub Pages under any repo name.
export default defineConfig({
  base: './',
  server: { port: 5173, open: false },
  build: { outDir: 'dist', sourcemap: true },
  test: {
    environment: 'node',
    include: ['tests/**/*.test.js'],
  },
});
