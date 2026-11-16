import { build } from 'vite';

// A deployed frontend must never silently fall back to a visitor's localhost.
const value = process.env.VITE_ALGO_URL?.trim();
if (!value) throw new Error('Set VITE_ALGO_URL to the public HTTPS API URL before deploying.');
const url = new URL(value);
if (
  url.protocol !== 'https:' ||
  ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname) ||
  url.username ||
  url.password ||
  url.search ||
  url.hash
) {
  throw new Error(
    'VITE_ALGO_URL must be a public HTTPS URL without credentials, query or fragment.',
  );
}
process.env.VITE_ALGO_URL = value.replace(/\/+$/, '');
await build();
