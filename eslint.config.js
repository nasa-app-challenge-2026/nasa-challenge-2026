import js from '@eslint/js';
import globals from 'globals';

export default [
  { ignores: ['dist/**', 'node_modules/**', 'coverage/**', 'backend/server/**', 'api/**'] },
  js.configs.recommended,
  {
    // The four layers run in the browser (see docs/ARCHITECTURE.md).
    files: ['frontend/**/*.js', 'backend/**/*.js', 'application/**/*.js', 'data/**/*.js'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: { ...globals.browser },
    },
    rules: {
      'no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
      eqeqeq: ['error', 'always'],
      'prefer-const': 'error',
    },
  },
  {
    files: [
      'tests/**/*.js',
      'backend/scripts/**/*.mjs',
      'scripts/**/*.mjs',
      'contract/**/*.js',
      '*.config.js',
      'algo-rendement/**/*.{js,mjs}',
    ],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: { ...globals.node },
    },
  },
];
