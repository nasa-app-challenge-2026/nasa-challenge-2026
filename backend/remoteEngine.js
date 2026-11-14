/**
 * Real algorithm over HTTP. The algo team only has to expose three POST
 * endpoints that respect backend/contract/field-shift.schema.json:
 *
 *   POST {baseUrl}/evaluate    FarmInput         → FarmPlan
 *   POST {baseUrl}/propose     ProposeRequest    → ProposeResponse
 *   POST {baseUrl}/field-data  FieldDataRequest  → FieldDataResponse
 *
 * CORS must allow the site's origin (GitHub Pages) and the Content-Type header.
 */
export class EngineError extends Error {
  constructor(message, { status, cause } = {}) {
    super(message);
    this.name = 'EngineError';
    this.status = status;
    this.cause = cause;
  }
}

async function post(baseUrl, path, body, timeoutMs) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${baseUrl}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: ctrl.signal,
    });
    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new EngineError(`L’algorithme a répondu ${res.status} sur ${path}. ${text}`.trim(), {
        status: res.status,
      });
    }
    return await res.json();
  } catch (err) {
    if (err instanceof EngineError) throw err;
    const msg =
      err.name === 'AbortError'
        ? `L’algorithme n’a pas répondu à temps (${path}).`
        : `Impossible de joindre l’algorithme (${path}).`;
    throw new EngineError(msg, { cause: err });
  } finally {
    clearTimeout(timer);
  }
}

/**
 * @param {{ baseUrl: string, timeoutMs?: number }} options
 * @returns {import('./contract/types.js').Engine}
 */
export function createRemoteEngine({ baseUrl, timeoutMs = 15000 }) {
  if (!baseUrl)
    throw new Error('VITE_ALGO_URL est vide : impossible d’utiliser le moteur distant.');
  const url = baseUrl.replace(/\/+$/, '');
  return {
    name: 'remote',
    evaluateFarm: (input) => post(url, '/evaluate', input, timeoutMs),
    proposeRotation: (req) => post(url, '/propose', req, timeoutMs),
    getFieldData: (req) => post(url, '/field-data', req, timeoutMs),
  };
}
