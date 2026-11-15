/**
 * Source 1 : NASA POWER Agroclimatology Daily API (sans clé d'API).
 * Récupère les variables agro-météorologiques quotidiennes et d'humidité du sol assimilée :
 * - T2M, T2M_MAX, T2M_MIN : Températures à 2 m (°C)
 * - PRECTOTCORR : Précipitations corrigées MERRA-2 / GPM (mm/jour)
 * - GWETTOP : Humidité du sol de surface (0-5 cm, fraction 0-1, assimilée SMAP/GLDAS)
 * - GWETROOT : Humidité du sol dans la zone racinaire (0-100 cm, fraction 0-1)
 * - ALLSKY_SFC_SW_DWN : Rayonnement solaire incident (MJ/m²/jour)
 */
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { CONFIG } from '../config.js';
import { validateClimateSeasons } from './climateValidation.js';
import {
  readBoundedJson,
  readCache,
  regionCellKey,
  validateHistoricalSamplingParams,
  writeCache,
} from './cache.js';

const FILL_VALUE = -990;

/**
 * Résume les indicateurs de la saison de croissance (mai à septembre, mois 5 à 9)
 * pour chaque année disponible dans la réponse NASA POWER.
 */
export function summarizeGrowingSeasons(parametersByDate) {
  const {
    T2M = {},
    T2M_MAX = {},
    T2M_MIN = {},
    PRECTOTCORR = {},
    GWETTOP = {},
    GWETROOT = {},
  } = parametersByDate;
  const byYear = new Map();
  const valid = (v) => Number.isFinite(v) && v > FILL_VALUE;
  for (const [date, temp] of Object.entries(T2M)) {
    if (!/^\d{8}$/.test(date)) continue;
    const year = Number(date.slice(0, 4));
    const month = Number(date.slice(4, 6));
    const parsed = new Date(
      `${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6, 8)}T00:00:00Z`,
    );
    if (
      !Number.isFinite(parsed.getTime()) ||
      parsed.toISOString().slice(0, 10).replaceAll('-', '') !== date ||
      month < 5 ||
      month > 9
    )
      continue;
    const max = T2M_MAX[date],
      min = T2M_MIN[date],
      rain = PRECTOTCORR[date];
    // Aucun remplacement par zéro/pluie ou par T2M/extrema : les quatre séries sont requises.
    if (![temp, max, min, rain].every(valid) || rain < 0 || max < min) continue;
    if (!byYear.has(year))
      byYear.set(year, {
        year,
        days: 0,
        temp: 0,
        gdd: 0,
        heat: 0,
        rain: 0,
        dry: 0,
        top: [],
        root: [],
      });
    const a = byYear.get(year);
    a.days++;
    a.temp += temp;
    a.gdd += Math.max(0, (max + min) / 2 - 10);
    a.heat += Number(max >= 30);
    a.rain += rain;
    a.dry += Number(rain < 1);
    if (valid(GWETTOP[date]) && GWETTOP[date] >= 0 && GWETTOP[date] <= 1) a.top.push(GWETTOP[date]);
    if (valid(GWETROOT[date]) && GWETROOT[date] >= 0 && GWETROOT[date] <= 1)
      a.root.push(GWETROOT[date]);
  }
  const soilMean = (arr) =>
    arr.length ? Number((arr.reduce((a, b) => a + b, 0) / arr.length).toFixed(3)) : null;
  const seasons = [...byYear.values()]
    .filter((a) => a.days === 153)
    .map((a) => ({
      year: a.year,
      meanTempC: Number((a.temp / a.days).toFixed(2)),
      gddBase10: Number(a.gdd.toFixed(1)),
      heatStressDays: a.heat,
      precipMm: Number(a.rain.toFixed(1)),
      dryDaysCount: a.dry,
      soilMoistureTop: soilMean(a.top),
      soilMoistureRoot: soilMean(a.root),
      coverage: { requiredDays: 153, completeDays: a.days },
    }))
    .sort((a, b) => a.year - b.year);
  return classifyClimateRegimes(seasons);
}

/**
 * Classifie chaque année en régime climatique ('normal', 'sec', 'chaud')
 * à partir des centiles observés sur la série de la région (aucun seuil arbitraire).
 */
function classifyClimateRegimes(summaries) {
  if (summaries.length === 0) return [];
  const rains = [...summaries.map((s) => s.precipMm)].sort((a, b) => a - b);
  const temps = [...summaries.map((s) => s.meanTempC)].sort((a, b) => a - b);
  const p25Rain = rains[Math.floor(rains.length * 0.25)];
  const p75Temp = temps[Math.floor(temps.length * 0.75)];

  const meanRain = rains.reduce((a, b) => a + b, 0) / rains.length;
  const stdRain = Math.sqrt(rains.reduce((a, b) => a + (b - meanRain) ** 2, 0) / rains.length) || 1;
  const meanTemp = temps.reduce((a, b) => a + b, 0) / temps.length;
  const stdTemp = Math.sqrt(temps.reduce((a, b) => a + (b - meanTemp) ** 2, 0) / temps.length) || 1;

  return summaries.map((s) => {
    const rainZ = (s.precipMm - meanRain) / stdRain;
    const tempZ = (s.meanTempC - meanTemp) / stdTemp;
    let regime = 'normal';
    if (s.precipMm <= p25Rain) regime = 'sec';
    else if (s.meanTempC >= p75Temp) regime = 'chaud';
    return {
      ...s,
      rainZScore: Number(rainZ.toFixed(2)),
      tempZScore: Number(tempZ.toFixed(2)),
      regime,
    };
  });
}

/**
 * Interroge l'API officielle NASA POWER pour (lat, lon) entre startYear et endYear.
 */
export async function fetchNasaPowerSeries({
  lat,
  lon,
  startYear = CONFIG.sampling.startYear,
  endYear = CONFIG.sampling.endYear,
}) {
  const valid = validateHistoricalSamplingParams({ lat, lon, startYear, endYear });
  const cacheKey = `${regionCellKey(valid.lat, valid.lon, 0.5)}_${valid.startYear}_${valid.endYear}`;
  const cached = readCache('nasa-power', cacheKey, (d) => {
    validateClimateSeasons(d.seasons, valid);
    return true;
  });
  if (cached) return { ...cached, fromCache: true };

  // Vérifie si un snapshot NASA POWER local du dépôt correspond exactement aux coordonnées demandées
  const localSnap = loadLocalNasaPowerSnapshot({
    lat: valid.lat,
    lon: valid.lon,
    startYear: valid.startYear,
    endYear: valid.endYear,
  });
  if (localSnap) {
    return {
      ...localSnap,
      period: { startYear: valid.startYear, endYear: valid.endYear },
      fromCache: true,
    };
  }

  const params = new URLSearchParams({
    parameters: 'T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,GWETTOP,GWETROOT,ALLSKY_SFC_SW_DWN',
    community: 'AG',
    longitude: String(valid.lon),
    latitude: String(valid.lat),
    start: `${valid.startYear}0101`,
    end: `${valid.endYear}1231`,
    format: 'JSON',
  });

  const url = `${CONFIG.endpoints.nasaPowerDaily}?${params.toString()}`;
  const res = await fetch(url, {
    headers: { Accept: 'application/json' },
    signal: AbortSignal.timeout(CONFIG.httpTimeoutMs),
  });

  if (!res.ok) {
    throw new Error(`NASA POWER API a répondu HTTP ${res.status} sur ${url}`);
  }

  const raw = await readBoundedJson(res);
  const parameterData = raw?.properties?.parameter;
  if (!parameterData) {
    throw new Error('Réponse NASA POWER invalide : properties.parameter manquant.');
  }

  const seasons = validateClimateSeasons(summarizeGrowingSeasons(parameterData), valid);
  const payload = {
    source: 'NASA POWER Daily Agroclimatology API (MERRA-2 / GLDAS)',
    url,
    coordinates: { lat: valid.lat, lon: valid.lon },
    period: { startYear: valid.startYear, endYear: valid.endYear },
    seasons,
  };

  return writeCache('nasa-power', cacheKey, payload);
}

/**
 * Lit un snapshot NASA POWER dans `data/snapshots/nasa-power/` en vérifiant que les coordonnées
 * internes du fichier GeoJSON (`geometry.coordinates = [lon, lat]`) correspondent à `(lat, lon)` (à ±0.25°).
 */
export function loadLocalNasaPowerSnapshot({ lat, lon, startYear, endYear } = {}) {
  if (!existsSync(CONFIG.repoSnapshotsDir)) return null;
  const files = readdirSync(CONFIG.repoSnapshotsDir).filter(
    (f) => f.endsWith('.json') && !f.endsWith('.meta.json'),
  );

  for (const file of files) {
    try {
      const fullPath = join(CONFIG.repoSnapshotsDir, file);
      const raw = JSON.parse(readFileSync(fullPath, 'utf8'));
      const coords = raw?.geometry?.coordinates;
      const snapLon = Number(coords?.[0]);
      const snapLat = Number(coords?.[1]);

      if (!Number.isFinite(snapLat) || !Number.isFinite(snapLon)) continue;
      if (
        lat !== undefined &&
        lon !== undefined &&
        (Math.abs(snapLat - Number(lat)) > 0.25 || Math.abs(snapLon - Number(lon)) > 0.25)
      ) {
        continue;
      }

      const parameterData = raw?.properties?.parameter;
      if (!parameterData) continue;

      let allSeasons = summarizeGrowingSeasons(parameterData);
      if (startYear !== undefined && endYear !== undefined) {
        allSeasons = classifyClimateRegimes(
          allSeasons.filter((s) => s.year >= startYear && s.year <= endYear),
        );
      }
      if (allSeasons.length === 0) continue;
      validateClimateSeasons(allSeasons, { startYear, endYear });

      return {
        source: `Snapshot local NASA POWER (${file})`,
        coordinates: { lat: snapLat, lon: snapLon },
        seasons: allSeasons,
      };
    } catch {
      // Ignore fichier illisible
    }
  }
  return null;
}
