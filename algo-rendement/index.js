#!/usr/bin/env node
/**
 * Point d'entrée principal de `algo-rendement` :
 * Orchestre la récupération des vraies données satellites (NASA POWER, NASA MODIS/HLS NDVI,
 * USDA CropScape CDL / AAFC Inventaire annuel des cultures, et USDA NASS QuickStats),
 * calcule la matrice régionale des paires (A -> B) sans aucune valeur hardcodée,
 * et classe les meilleures rotations multi-cultures sur le rendement.
 *
 * Usage en ligne de commande :
 *   node algo-rendement/index.js --lat 45.63 --lon -72.95 --years 4 --current mais
 *   node algo-rendement/index.js --lat 42.03 --lon -93.62 --years 4 --current mais
 */
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { CONFIG } from './config.js';
import { fetchNasaPowerSeries } from './sources/nasaPower.js';
import { fetchRegionalNdviSeries, searchHls30mGranules } from './sources/nasaModisNdvi.js';
import { fetchRegionalCropHistory, isLocationInCanada } from './sources/cropHistory.js';
import {
  calibratePairMatrixWithNassYields,
  fetchNassStateYields,
} from './sources/nassQuickStats.js';
import {
  computeClimateBaselineStats,
  fetchFutureClimateProjection,
} from './sources/nasaCmip6Projection.js';
import {
  buildTransitionObservations,
  computeRegionalPairMatrix,
} from './engine/pairTransitions.js';
import {
  findClimateTwin,
  forecastFutureRotationYield,
  loadReferenceRegionsProfiles,
} from './engine/climateTwins.js';
import {
  evaluateRotationYieldFromPairs,
  findBestMultiCropRotationsForYield,
  validateCycleYears,
  validateRegime,
} from './engine/yieldOptimizer.js';
import { validateHistoricalSamplingParams } from './sources/cache.js';
import { validateCurrentCrop } from './engine/modelUtils.js';

/**
 * Exécute le pipeline complet d'extraction régionale des paires, de Jumeau Climatique
 * et d'optimisation du rendement (actuel et futur sous CMIP6) pour une coordonnée (lat, lon).
 */
export async function runRegionalYieldPipeline({
  lat,
  lon,
  startYear = CONFIG.sampling.startYear,
  endYear = CONFIG.sampling.endYear,
  halfWindowKm = CONFIG.sampling.halfWindowKm,
  cycleYears = 4,
  currentCrop = null,
  availableCrops,
  minDistinctCrops = 2,
  regime = 'all',
  futureStartYear = 2027,
  futureEndYear = 2040,
  scenario = 'ssp245',
}) {
  validateHistoricalSamplingParams({ lat, lon, startYear, endYear, halfWindowKm });
  validateCycleYears(cycleYears);
  validateRegime(regime);
  validateCurrentCrop(currentCrop);
  // 1. Météo, degrés-jours et humidité du sol NASA POWER
  const nasaPower = await fetchNasaPowerSeries({ lat, lon, startYear, endYear });

  // 2. Grilles satellites de NDVI maximal d'été (NASA MODIS 250m)
  const ndviSeries = await fetchRegionalNdviSeries({
    lat,
    lon,
    startYear,
    endYear,
    halfWindowKm,
  });

  // 3. Historique des cultures par tuile matricielle complète (64x64 = 4 096 pixels)
  const cropHistory = await fetchRegionalCropHistory({
    lat,
    lon,
    bbox: ndviSeries.bbox,
    gridSize: ndviSeries.nrows || 64,
    halfWindowKm,
    startYear,
    endYear,
  });

  // 4. Métadonnées HLS 30m (Landsat 8/9 + Sentinel-2 via NASA CMR-STAC)
  const hlsGranulesSample = await searchHls30mGranules({ lat, lon, year: endYear }).catch(() => []);

  // 5. Rendements officiels USDA NASS QuickStats (uniquement pour les États-Unis et si USDA_NASS_API_KEY est présente)
  const nassYields = await fetchNassStateYields({
    lat,
    lon,
    startYear,
    endYear,
  }).catch(() => ({
    available: false,
  }));

  // 6. Croisement empirique par champ distinct : (culture_{t-1} -> culture_t) x NDVI_t corrigé du climat_t
  const observations = buildTransitionObservations({
    ndviSeries,
    cropHistory,
    climateSeasons: nasaPower.seasons,
  });

  const pairMatrix = calibratePairMatrixWithNassYields(
    computeRegionalPairMatrix(observations),
    nassYields,
  );

  // 7. Projection climatique future CMIP6 (ssp126 / ssp245 / ssp370) + recherche du Jumeau Climatique
  const climateProjection = await fetchFutureClimateProjection({
    lat,
    lon,
    historicalSeasons: nasaPower.seasons,
    startYear: futureStartYear,
    endYear: futureEndYear,
    scenario,
  });

  const referenceRegions = await loadReferenceRegionsProfiles({ startYear, endYear });
  const climateTwin = findClimateTwin({
    projectedSeasons: climateProjection.projectedSeasons,
    localBaselineStats: climateProjection.baselineStats,
    candidateRegions: referenceRegions,
    farmCoordinates: { lat, lon },
  });

  // 8. Recherche de la meilleure rotation multi-cultures pour le rendement (actuel + trajectoire future)
  const bestRotations = findBestMultiCropRotationsForYield({
    pairMatrix,
    cycleYears,
    availableCrops,
    currentCrop,
    minDistinctCrops,
    regime,
    topK: 5,
    projectedSeasons: climateProjection.projectedSeasons,
    twinMatch: climateTwin,
    localBaselineStats: climateProjection.baselineStats,
  });

  return {
    interpretation: {
      metric: 'equal_weight_annual_relative_vigor',
      yieldMapping: 'conditional_1_to_1_relative_anomalies',
      empiricalYieldValidation: false,
      rotationEffect: 'observational_association',
      twinTheory: 'progressive_transfer_from_warmer_climate_analogue',
      uncertainty: 'model_envelope_not_validated_coverage',
    },
    region: { lat, lon, halfWindowKm, period: { startYear, endYear } },
    sourcesUsed: {
      climate: nasaPower.source,
      ndvi: ndviSeries.source,
      cropMap: cropHistory.source,
      cmip6Projection: climateProjection.source,
      hls30mGranulesFound: hlsGranulesSample.length,
      nassCalibration: nassYields.available,
    },
    climateSeasons: nasaPower.seasons,
    climateProjection: {
      scenario: climateProjection.scenario,
      period: climateProjection.period,
      baselineStats: climateProjection.baselineStats,
      projectedSeasons: climateProjection.projectedSeasons,
    },
    climateTwin: climateTwin
      ? {
          status: climateTwin.status,
          reason: climateTwin.reason || null,
          targetFutureClimate: climateTwin.targetFutureClimate,
          warmingDeltaGdd: climateTwin.warmingDeltaGdd,
          warmingDeltaTempC: climateTwin.warmingDeltaTempC,
          bestTwin: climateTwin.bestTwin
            ? {
                id: climateTwin.bestTwin.id,
                name: climateTwin.bestTwin.name,
                coordinates: climateTwin.bestTwin.coordinates,
                distance: climateTwin.bestTwin.distance,
                similarityPct: climateTwin.bestTwin.similarityPct,
                baselineMeans: climateTwin.bestTwin.baselineMeans,
              }
            : null,
          candidatesRanked: (climateTwin.candidatesRanked || []).map((c) => ({
            id: c.id,
            name: c.name,
            distance: c.distance,
            similarityPct: c.similarityPct,
            baselineMeans: c.baselineMeans,
          })),
        }
      : null,
    pairMatrix,
    bestRotations,
  };
}

export {
  buildTransitionObservations,
  calibratePairMatrixWithNassYields,
  computeClimateBaselineStats,
  computeRegionalPairMatrix,
  evaluateRotationYieldFromPairs,
  fetchFutureClimateProjection,
  findBestMultiCropRotationsForYield,
  findClimateTwin,
  forecastFutureRotationYield,
  isLocationInCanada,
  loadReferenceRegionsProfiles,
};

// --- Exécution CLI directe ---
if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  const args = Object.fromEntries(
    process.argv
      .slice(2)
      .map((a, i, arr) => (a.startsWith('--') ? [a.slice(2), arr[i + 1]] : null))
      .filter(Boolean),
  );

  const lat = Number(args.lat ?? 45.63);
  const lon = Number(args.lon ?? -72.95);
  const cycleYears = Number(args.years ?? 4);
  const currentCrop = args.current ?? null;

  console.log(
    `Extraction régionale des successions satellites autour de (${lat}, ${lon}) sur ${CONFIG.sampling.startYear}–${CONFIG.sampling.endYear}…`,
  );
  runRegionalYieldPipeline({ lat, lon, cycleYears, currentCrop })
    .then((res) => {
      console.log(JSON.stringify(res, null, 2));
    })
    .catch((err) => {
      console.error('Erreur pipeline :', err.message);
      process.exit(1);
    });
}
