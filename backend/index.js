/**
 * The single place where the app picks its engine (called by frontend/main.js).
 * Switching to the real algorithm = set VITE_ALGO_MODE=remote and VITE_ALGO_URL
 * (see .env.example). No screen or application code changes.
 */
import { createMockEngine } from './mockEngine.js';
import { createRemoteEngine } from './remoteEngine.js';

export function createEngine(env = import.meta.env) {
  if (env.VITE_ALGO_MODE === 'remote') {
    return createRemoteEngine({ baseUrl: env.VITE_ALGO_URL });
  }
  return createMockEngine({ latencyMs: 150 });
}
