/**
 * The single place where the app picks its engine (called by frontend/main.js):
 *   - default: the Field Shift algorithm in the browser (backend/algorithm/), with
 *     the real NASA POWER weather of the farm;
 *   - VITE_FARM_WEATHER=demo: same algorithm, fictitious weather (offline);
 *   - VITE_ALGO_MODE=remote: a server that answers POST /plan (see .env.example).
 */
import { createAlgorithmEngine } from './algorithmEngine.js';
import { createRemoteEngine } from './remoteEngine.js';

export function createEngine(env = import.meta.env) {
  if (env.VITE_ALGO_MODE === 'remote') return createRemoteEngine({ baseUrl: env.VITE_ALGO_URL });
  return createAlgorithmEngine({ useRealWeather: env.VITE_FARM_WEATHER !== 'demo' });
}
