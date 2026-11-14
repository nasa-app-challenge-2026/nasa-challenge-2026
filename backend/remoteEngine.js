/**
 * The algorithm server (backend/server, FastAPI) over HTTP. It answers one POST endpoint that
 * respects backend/contract/field-shift.schema.json:
 *
 *   POST {baseUrl}/plan    FarmInput → FarmPlan
 *
 * The server must allow the origin of the site (CORS) and the Content-Type header: see
 * FIELD_SHIFT_CORS_ORIGINS in backend/server/README.md.
 */
export class EngineError extends Error {
  constructor(message, { status, cause } = {}) {
    super(message);
    this.name = 'EngineError';
    this.status = status;
    this.cause = cause;
  }
}

const DEFAULT_TIMEOUT_MS = 30000;
const HTTP_UNPROCESSABLE = 422;

/** FastAPI's refusal of a body ({ detail: [{ loc, msg }] }) as a readable sentence. */
function describeRefusal(text) {
  try {
    const { detail } = JSON.parse(text);
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail
        .map(
          (d) => `${d.loc.slice(1).join(' › ')} : ${String(d.msg).replace(/^Value error, /, '')}`,
        )
        .join(' ; ');
    }
  } catch {
    /* not JSON: the raw text is the best we have */
  }
  return text;
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
      const why = res.status === HTTP_UNPROCESSABLE ? describeRefusal(text) : text;
      throw new EngineError(`L’algorithme a répondu ${res.status} sur ${path}. ${why}`.trim(), {
        status: res.status,
      });
    }
    return await res.json();
  } catch (err) {
    if (err instanceof EngineError) throw err;
    const msg =
      err.name === 'AbortError'
        ? `L’algorithme n’a pas répondu à temps (${baseUrl}${path}).`
        : `Impossible de joindre l’algorithme (${baseUrl}${path}). Le serveur est-il lancé ?`;
    throw new EngineError(msg, { cause: err });
  } finally {
    clearTimeout(timer);
  }
}

/**
 * @param {{ baseUrl: string, timeoutMs?: number }} options
 * @returns {import('./contract/types.js').Engine}
 */
export function createRemoteEngine({ baseUrl, timeoutMs = DEFAULT_TIMEOUT_MS }) {
  const url = (baseUrl ?? '').replace(/\/+$/, '');
  return {
    name: 'remote',
    planFarm(input) {
      if (!url)
        return Promise.reject(
          new EngineError(
            'Aucun serveur d’algorithme n’est configuré : donnez son adresse dans VITE_ALGO_URL.',
          ),
        );
      return post(url, '/plan', input, timeoutMs);
    },
  };
}
