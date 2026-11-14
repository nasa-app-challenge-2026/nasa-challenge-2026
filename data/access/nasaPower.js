/**
 * NASA POWER daily weather at a point: maximum and minimum temperature at 2 m
 * (°C) and corrected rain (mm/day). Public API, no account, CORS open
 * (https://power.larc.nasa.gov/docs/services/api/). About 0.7 MB for 40 years.
 * Results are kept in memory for the session, per point.
 */
const API = 'https://power.larc.nasa.gov/api/temporal/daily/point';
const PARAMETERS = ['T2M_MAX', 'T2M_MIN', 'PRECTOTCORR'];
const FILL_VALUE = -999;
const TIMEOUT_MS = 30000;
/** Points closer than this (degrees) share the same POWER cell and the same cache entry. */
const CACHE_PRECISION = 100;

const cache = new Map();

const pointKey = (lat, lon, first, last) =>
  `${Math.round(lat * CACHE_PRECISION)}:${Math.round(lon * CACHE_PRECISION)}:${first}:${last}`;

/** Missing days (fill value) take the value of the day before. */
function fillGaps(values) {
  let previous = 0;
  return values.map((v) => {
    if (typeof v !== 'number' || v <= FILL_VALUE) return previous;
    previous = v;
    return v;
  });
}

/**
 * @returns {Promise<{ firstYear: number, lastYear: number,
 *                     tmax: number[], tmin: number[], rain: number[] }>}
 *          one value per day from 1 January of firstYear to 31 December of lastYear
 */
export function fetchNasaPowerDaily(
  lat,
  lon,
  { firstYear, lastYear, fetchImpl = globalThis.fetch } = {},
) {
  const key = pointKey(lat, lon, firstYear, lastYear);
  if (!cache.has(key)) {
    const request = download(lat, lon, firstYear, lastYear, fetchImpl);
    cache.set(key, request);
    request.catch(() => cache.delete(key)); // a failure can be retried later
  }
  return cache.get(key);
}

async function download(lat, lon, firstYear, lastYear, fetchImpl) {
  const params = new URLSearchParams({
    parameters: PARAMETERS.join(','),
    community: 'AG',
    latitude: lat.toFixed(4),
    longitude: lon.toFixed(4),
    start: `${firstYear}0101`,
    end: `${lastYear}1231`,
    format: 'JSON',
  });
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    const res = await fetchImpl(`${API}?${params}`, { signal: ctrl.signal });
    if (!res.ok) throw new Error(`NASA POWER a répondu ${res.status}`);
    const body = await res.json();
    const p = body?.properties?.parameter;
    if (!p?.T2M_MAX) throw new Error('Réponse NASA POWER inattendue');
    const column = (name) => fillGaps(Object.values(p[name] ?? {}));
    return {
      firstYear,
      lastYear,
      tmax: column('T2M_MAX'),
      tmin: column('T2M_MIN'),
      rain: column('PRECTOTCORR'),
    };
  } finally {
    clearTimeout(timer);
  }
}
