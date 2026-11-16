/**
 * The single place where the app gets its engine (called by frontend/main.js): the Field Shift
 * algorithm server (backend/server, FastAPI), reached over HTTP.
 *
 * Its address is VITE_ALGO_URL (see .env.example). With `npm run dev` it defaults to
 * http://localhost:8000, where `python -m uvicorn field_shift.api.main:app` serves it; a
 * production build needs the variable.
 */
import { createRemoteEngine } from './remoteEngine.js';

const DEV_SERVER_URL = 'http://localhost:8000';

export function createEngine(env = import.meta.env) {
  return createRemoteEngine({ baseUrl: env.VITE_ALGO_URL || (env.DEV ? DEV_SERVER_URL : '') });
}

/**
 * Wakes a hosted server that sleeps when idle (free hosting): one GET /health when the page
 * opens, so it is awake by the time the farmer asks for a plan. Errors are ignored.
 */
export function wakeEngine(env = import.meta.env) {
  if (!env.VITE_ALGO_URL) return;
  fetch(`${env.VITE_ALGO_URL}/health`).catch(() => {});
}
