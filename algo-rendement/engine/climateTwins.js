/**
 * Moteur de Jumeaux Climatiques (Analogues Spatiaux) et de prévision du rendement futur
 * sous réchauffement climatique (NASA NEX-GDDP-CMIP6 : ssp126, ssp245, ssp370).
 *
 * Rigueur méthodologique :
 * 1) Alignement des seuils de régime : une saison future est classée contre les seuils locaux
 *    pour la matrice locale, et contre les seuils propres du Jumeau Climatique pour la matrice du jumeau.
 * 2) Paires observées uniquement chez le jumeau (`!localResolved && twinResolved`) :
 *    pondérées honnêtement par `(1 - alpha) * unobservedPenaltyPct + alpha * twinEffect`, sans
 *    forcer `alpha = 1` ni gonfler artificiellement `observedShare`.
 * 3) Modulation hydrique activée uniquement lorsque le sous-régime dispose d'au moins
 *    `minRegimeSamplesForStressModulation` (5) observations.
 * 4) Héritage strict de la confiance : la confiance future tient compte de l'effectif minimal
 *    des sources de poids non nul, ne peut jamais dépasser la confiance historique,
 *    et est dégradée d'un cran dès que l'horizon atteint `longHorizonConfidenceDowngradeYears` (12 ans).
 */
import { CROPS } from '../../src/data/crops.js';
import { firstYear } from '../../src/lib/rotation.js';
import { CONFIG } from '../config.js';
import {
  downgradeConfidence,
  minConfidence,
  physicalEffectInterval,
  resolvePairEvidence,
  validatePhysicalEffectPct,
  validateCurrentCrop,
  validatedRotationSlots,
} from './modelUtils.js';
import { validateClimateSeasons } from '../sources/climateValidation.js';
import { fetchNasaPowerSeries } from '../sources/nasaPower.js';
import { fetchRegionalNdviSeries } from '../sources/nasaModisNdvi.js';
import { fetchRegionalCropHistory } from '../sources/cropHistory.js';
import {
  classifySeasonAgainstBaseline,
  computeClimateBaselineStats,
} from '../sources/nasaCmip6Projection.js';
import { buildTransitionObservations, computeRegionalPairMatrix } from './pairTransitions.js';

export const REFERENCE_REGIONS_CATALOG = [
  {
    id: 'qc_nord_cote_nord',
    name: 'Sacré-Cœur / Côte-Nord, Québec (Climat boréal frais)',
    lat: 48.0,
    lon: -70.0,
    hasSatelliteCropMatrix: false,
  },
  {
    id: 'qc_sud_monteregie',
    name: 'Saint-Hyacinthe / Montérégie, Québec (Vallée du Saint-Laurent)',
    lat: 45.6,
    lon: -72.9,
    hasSatelliteCropMatrix: true,
  },
  {
    id: 'us_midwest_iowa',
    name: 'Story County / Ames, Iowa (Corn Belt américain)',
    lat: 42.015,
    lon: -93.75,
    hasSatelliteCropMatrix: true,
  },
];

/**
 * Valide que `offset` est un entier fini et renvoie sa valeur normalisée dans `[0, L - 1]`.
 */
export function normalizeCycleOffset(offset, cycleLength) {
  const num = Number(offset);
  if (!Number.isInteger(num)) {
    throw new RangeError(`Paramètre offset invalide (${offset}) : un entier est requis.`);
  }
  if (cycleLength <= 0) return 0;
  return ((num % cycleLength) + cycleLength) % cycleLength;
}

export async function loadReferenceRegionsProfiles({ startYear = 2018, endYear = 2024 } = {}) {
  const profiles = [];
  const skippedRegions = [];

  for (const reg of REFERENCE_REGIONS_CATALOG) {
    try {
      const nasaPower = await fetchNasaPowerSeries({
        lat: reg.lat,
        lon: reg.lon,
        startYear,
        endYear,
      });
      const baselineStats = computeClimateBaselineStats(nasaPower.seasons);

      let pairMatrix = null;
      if (reg.hasSatelliteCropMatrix) {
        const ndviSeries = await fetchRegionalNdviSeries({
          lat: reg.lat,
          lon: reg.lon,
          startYear,
          endYear,
        });
        const cropHistory = await fetchRegionalCropHistory({
          lat: reg.lat,
          lon: reg.lon,
          bbox: ndviSeries.bbox,
          gridSize: ndviSeries.nrows || 64,
          startYear,
          endYear,
        });
        const observations = buildTransitionObservations({
          ndviSeries,
          cropHistory,
          climateSeasons: nasaPower.seasons,
        });
        pairMatrix = computeRegionalPairMatrix(observations);
      }

      profiles.push({
        id: reg.id,
        name: reg.name,
        coordinates: { lat: reg.lat, lon: reg.lon },
        baselineStats,
        pairMatrix,
      });
    } catch (err) {
      skippedRegions.push({ id: reg.id, reason: err.message });
    }
  }

  if (profiles.filter((p) => p.pairMatrix !== null).length === 0) {
    throw new Error(
      `Aucune région de référence avec matrice satellite n'a pu être chargée : ${JSON.stringify(skippedRegions)}`,
    );
  }

  return profiles;
}

export function computeNormalizedClimateDistance(targetClimate, regionBaselineStats) {
  const { means, stds } = regionBaselineStats;
  const weights = CONFIG.hyperparameters.climateDistanceWeights;
  const gddZ = (targetClimate.gddBase10 - means.gddBase10) / Math.max(40, stds.gddBase10);
  const tempZ = (targetClimate.meanTempC - means.meanTempC) / Math.max(0.4, stds.meanTempC);
  const heatZ =
    (targetClimate.heatStressDays - means.heatStressDays) / Math.max(2, stds.heatStressDays);
  const rainZ = (targetClimate.precipMm - means.precipMm) / Math.max(30, stds.precipMm);

  const weightedSq =
    weights.gddBase10 * gddZ ** 2 +
    weights.meanTempC * tempZ ** 2 +
    weights.heatStressDays * heatZ ** 2 +
    weights.precipMm * rainZ ** 2;

  return Number(Math.sqrt(weightedSq).toFixed(3));
}

export function findClimateTwin({
  projectedSeasons,
  localBaselineStats,
  candidateRegions,
  farmCoordinates = null,
}) {
  validateClimateSeasons(projectedSeasons);

  const tailWindow = projectedSeasons.slice(-Math.min(5, projectedSeasons.length));
  const meanOf = (arr) => arr.reduce((a, b) => a + b, 0) / arr.length;

  const targetFutureClimate = {
    gddBase10: Number(meanOf(tailWindow.map((s) => s.gddBase10)).toFixed(1)),
    meanTempC: Number(meanOf(tailWindow.map((s) => s.meanTempC)).toFixed(2)),
    heatStressDays: Number(meanOf(tailWindow.map((s) => s.heatStressDays)).toFixed(1)),
    precipMm: Number(meanOf(tailWindow.map((s) => s.precipMm)).toFixed(1)),
  };

  const withMatrices = (candidateRegions || []).filter(
    (r) => r.pairMatrix && Object.keys(r.pairMatrix.pairs || {}).length > 0,
  );
  if (withMatrices.length === 0) {
    return null;
  }

  const isSameLocation = (r) =>
    farmCoordinates &&
    Math.abs(r.coordinates.lat - farmCoordinates.lat) < 0.25 &&
    Math.abs(r.coordinates.lon - farmCoordinates.lon) < 0.25;

  const externalRegions = withMatrices.filter((r) => !isSameLocation(r));
  const warmingGdd = targetFutureClimate.gddBase10 - localBaselineStats.means.gddBase10;
  const warmerExternalRegions = externalRegions.filter(
    (r) => r.baselineStats.means.gddBase10 > localBaselineStats.means.gddBase10,
  );

  // Si aucune région du catalogue n'est plus chaude que la ferme actuelle (ex. la ferme est déjà en Iowa),
  // ne jamais retourner une région plus froide comme "meilleur jumeau" : renvoyer `bestTwin: null`.
  if (warmerExternalRegions.length === 0) {
    return {
      targetFutureClimate,
      warmingDeltaGdd: Number(warmingGdd.toFixed(1)),
      warmingDeltaTempC: Number(
        (targetFutureClimate.meanTempC - localBaselineStats.means.meanTempC).toFixed(2),
      ),
      bestTwin: null,
      status: 'no_warmer_twin_in_catalog',
      reason:
        'Aucune région de référence plus chaude dans le catalogue — prévision basée sur la matrice locale modulée par les régimes futurs CMIP6 (alpha = 0).',
      candidatesRanked: [],
    };
  }

  const decay = CONFIG.hyperparameters.similarityDecayFactor;
  const ranked = warmerExternalRegions
    .map((reg) => {
      const distance = computeNormalizedClimateDistance(targetFutureClimate, reg.baselineStats);
      const similarityPct = Math.round(100 * Math.exp(-decay * distance));
      return {
        id: reg.id,
        name: reg.name,
        coordinates: reg.coordinates,
        isExternalTwin: !isSameLocation(reg),
        distance,
        similarityPct,
        baselineMeans: reg.baselineStats.means,
        baselineStats: reg.baselineStats,
        pairMatrix: reg.pairMatrix,
      };
    })
    .sort((a, b) => a.distance - b.distance);

  return {
    targetFutureClimate,
    warmingDeltaGdd: Number(warmingGdd.toFixed(1)),
    warmingDeltaTempC: Number(
      (targetFutureClimate.meanTempC - localBaselineStats.means.meanTempC).toFixed(2),
    ),
    bestTwin: ranked[0],
    status: 'warmer_twin_found',
    candidatesRanked: ranked,
  };
}

export function computeYearlyBlendingAlpha({
  projectedSeason,
  localBaselineStats,
  twinBaselineStats,
}) {
  if (!twinBaselineStats) return 0;
  const localGdd = localBaselineStats.means.gddBase10;
  const twinGdd = twinBaselineStats?.means?.gddBase10 ?? localGdd;
  const deltaTwinGdd = twinGdd - localGdd;

  // L'écart annuel observé dans la projection ne dépend pas de l'horizon demandé.
  const seasonWarmingGdd = Math.max(0, projectedSeason.gddBase10 - localGdd);

  if (deltaTwinGdd > 40) {
    const rawAlpha = seasonWarmingGdd / deltaTwinGdd;
    return Number(Math.min(1, Math.max(0, rawAlpha)).toFixed(3));
  }

  return 0;
}

/**
 * Extrait l'effet d'une paire (A -> B) dans une région de référence (`referenceBaselineStats`)
 * en classant la saison projetée contre les seuils PROPRES de cette région.
 * La modulation hydrique supplémentaire n'est appliquée que si le sous-régime et le régime normal
 * disposent chacun d'au moins `minRegimeSamplesForStressModulation` (5) observations.
 */
function resolvePairEffectForRegion(pairStat, projectedSeason, referenceBaselineStats) {
  if (!pairStat) return null;

  const regimeInRegion = referenceBaselineStats?.thresholds
    ? classifySeasonAgainstBaseline(projectedSeason, referenceBaselineStats)
    : projectedSeason.regime || 'normal';

  let evidence = resolvePairEvidence(pairStat, regimeInRegion);
  const regimeEntry = pairStat.byRegime?.[regimeInRegion];
  const normalEntry = pairStat.byRegime?.normal;
  const minSamplesMod = CONFIG.sampling.minRegimeSamplesForStressModulation;

  let effect = evidence.meanEffectPct;
  const halfWidth = (entry) =>
    entry.stdErrorPct ??
    Math.max(
      entry.meanEffectPct - entry.intervalPct[0],
      entry.intervalPct[1] - entry.meanEffectPct,
    );
  let baseHalfWidth = halfWidth(evidence);

  if (
    (regimeInRegion === 'sec' || regimeInRegion === 'chaud') &&
    regimeEntry &&
    normalEntry &&
    regimeEntry.sampleCount >= minSamplesMod &&
    normalEntry.sampleCount >= minSamplesMod
  ) {
    const normalEvidence = resolvePairEvidence(pairStat, 'normal');
    const stressDelta = evidence.meanEffectPct - normalEvidence.meanEffectPct;
    const rootWetness = referenceBaselineStats?.means?.soilMoistureRoot ?? 0.55;
    const soilVulnerabilityFactor = Math.max(0.75, Math.min(1.35, (1 - rootWetness) / 0.45));
    const regionRainMean = referenceBaselineStats?.means?.precipMm ?? projectedSeason.precipMm;
    const regionRainStd = referenceBaselineStats?.stds?.precipMm || 50;
    const regionRainZ = (projectedSeason.precipMm - regionRainMean) / regionRainStd;
    const droughtIntensity = Math.max(0, -regionRainZ) * 0.15;
    const stressFactor = soilVulnerabilityFactor * (1 + droughtIntensity);
    effect = normalEvidence.meanEffectPct + stressDelta * stressFactor;
    validatePhysicalEffectPct(effect, 'Extrapolation du stress climatique');
    if (stressFactor !== 1) {
      baseHalfWidth =
        Math.abs(stressFactor) * baseHalfWidth +
        Math.abs(1 - stressFactor) * halfWidth(normalEvidence);
      evidence = {
        ...evidence,
        sampleCount: Math.min(evidence.sampleCount, normalEvidence.sampleCount),
        effectiveYearsCount: Math.min(
          evidence.effectiveYearsCount,
          normalEvidence.effectiveYearsCount,
        ),
        confidence: minConfidence(evidence.confidence, normalEvidence.confidence),
      };
    }
  }

  const roundedEffect = validatePhysicalEffectPct(Number(effect.toFixed(2)));

  return {
    regimeUsed: regimeInRegion,
    meanEffectPct: roundedEffect,
    intervalPct: physicalEffectInterval(roundedEffect, [
      Math.min(roundedEffect, Number((roundedEffect - baseHalfWidth).toFixed(1))),
      Math.max(roundedEffect, Number((roundedEffect + baseHalfWidth).toFixed(1))),
    ]),
    sampleCount: evidence.sampleCount,
    effectiveYearsCount: evidence.effectiveYearsCount,
    regimeSampleCount: evidence.regimeSampleCount,
    confidence: evidence.confidence,
  };
}

/**
 * Fusionne la matrice de paires locale et la matrice de paires du Jumeau Climatique selon `alpha(y)`.
 * Si une paire est absente localement mais présente chez le jumeau (`!localResolved && twinResolved`),
 * elle est interpolée entre la pénalité de paire inconnue `(1 - alpha) * unobservedPenaltyPct`
 * et l'effet du jumeau `alpha * twinEffect` (sans jamais forcer `alphaTwin = 1`).
 */
export function blendPairEffectForSeason({
  pairKey,
  projectedSeason,
  alpha,
  localPairMatrix,
  twinPairMatrix,
  localBaselineStats,
  twinBaselineStats,
  unobservedPenaltyPct = -2.0,
}) {
  if (!Number.isFinite(alpha) || alpha < 0 || alpha > 1) {
    throw new RangeError('Poids du jumeau ou pénalité de paire invalide.');
  }
  validatePhysicalEffectPct(unobservedPenaltyPct, 'Pénalité de paire inconnue');
  const lookup = (matrix) =>
    Object.hasOwn(matrix?.pairs || {}, pairKey) ? matrix.pairs[pairKey] : null;
  const local =
    alpha < 1
      ? resolvePairEffectForRegion(lookup(localPairMatrix), projectedSeason, localBaselineStats)
      : null;
  const twin =
    alpha > 0
      ? resolvePairEffectForRegion(
          lookup(twinPairMatrix),
          projectedSeason,
          twinBaselineStats || localBaselineStats,
        )
      : null;
  const unknown = {
    meanEffectPct: unobservedPenaltyPct,
    intervalPct: physicalEffectInterval(unobservedPenaltyPct, [
      unobservedPenaltyPct - CONFIG.hyperparameters.unobservedHalfWidthPct,
      unobservedPenaltyPct + CONFIG.hyperparameters.unobservedHalfWidthPct,
    ]),
    sampleCount: 0,
    effectiveYearsCount: 0,
    confidence: 'faible',
  };
  const components = [
    { weight: 1 - alpha, evidence: local || unknown, observed: !!local },
    { weight: alpha, evidence: twin || unknown, observed: !!twin },
  ].filter((c) => c.weight > 0);
  const weighted = (fn) => components.reduce((sum, c) => sum + c.weight * fn(c.evidence), 0);
  const observedWeight = components.reduce((sum, c) => sum + c.weight * Number(c.observed), 0);
  const meanEffectPct = validatePhysicalEffectPct(
    Number(weighted((e) => e.meanEffectPct).toFixed(2)),
  );
  return {
    pairKey,
    observed: observedWeight >= 1 - 1e-12,
    observedWeight,
    meanEffectPct,
    intervalPct: physicalEffectInterval(meanEffectPct, [
      Math.min(meanEffectPct, Number(weighted((e) => e.intervalPct[0]).toFixed(1))),
      Math.max(meanEffectPct, Number(weighted((e) => e.intervalPct[1]).toFixed(1))),
    ]),
    localEffectPct: local?.meanEffectPct ?? null,
    twinEffectPct: twin?.meanEffectPct ?? null,
    localRegimeUsed: local?.regimeUsed ?? null,
    twinRegimeUsed: twin?.regimeUsed ?? null,
    alphaTwin: alpha,
    sampleCount: Math.min(...components.map((c) => c.evidence.sampleCount)),
    effectiveYearsCount: Math.min(...components.map((c) => c.evidence.effectiveYearsCount)),
    confidence: minConfidence(...components.map((c) => c.evidence.confidence)),
  };
}

/**
 * Prédit année par année le gain de rendement futur d'une rotation sur l'horizon `projectedSeasons`.
 */
export function forecastFutureRotationYield({
  rotation,
  currentCrop = null,
  offset = 0,
  projectedSeasons,
  localPairMatrix,
  twinMatch,
  localBaselineStats,
  unobservedPenaltyPct = -2.0,
  historicalConfidence = null,
}) {
  validateCurrentCrop(currentCrop);
  const slots = validatedRotationSlots(rotation);
  const L = slots.length;
  const safeOffset = normalizeCycleOffset(offset, L);

  if (L === 0 || !projectedSeasons || projectedSeasons.length === 0) {
    return {
      meanFutureYieldGainPct: 0,
      futureYieldGainRangePct: [0, 0],
      confidence: 'faible',
      yearlyForecast: [],
    };
  }

  validateClimateSeasons(projectedSeasons);
  validatePhysicalEffectPct(unobservedPenaltyPct, 'Pénalité de paire inconnue');
  const twinPairMatrix = twinMatch?.bestTwin?.pairMatrix || null;
  const twinBaselineStats = twinMatch?.bestTwin?.baselineStats || null;
  const twinDistance = twinMatch?.bestTwin?.distance ?? 0;
  if (!Number.isFinite(twinDistance) || twinDistance < 0) {
    throw new RangeError('Distance au jumeau climatique invalide.');
  }
  const {
    horizonUncertaintyPerYearPct,
    twinDistanceUncertaintyFactor,
    longHorizonConfidenceDowngradeYears,
  } = CONFIG.hyperparameters;

  const yearlyForecast = [];
  const baselineEndYear = localBaselineStats.period?.endYear ?? projectedSeasons[0].year - 1;
  let sumGain = 0;
  let sumLow = 0;
  let sumHigh = 0;
  let evaluatedTransitionsCount = 0;
  let observedWeightSum = 0;
  let minSampleInHorizon = Infinity;
  let confidence = 'elevee';

  let prevCrop =
    currentCrop ||
    slots[(safeOffset - 1 + L) % L]?.crop ||
    firstYear({ rotation, offset: safeOffset }).crop;

  for (let idx = 0; idx < projectedSeasons.length; idx++) {
    const season = projectedSeasons[idx];
    const slot = slots[(safeOffset + idx) % L];
    const currCrop = slot.crop;

    const alpha = computeYearlyBlendingAlpha({
      projectedSeason: season,
      localBaselineStats,
      twinBaselineStats,
    });

    const isMultiYearContinuation = currCrop === prevCrop && (CROPS[currCrop]?.years || 1) > 1;

    const pairKey = `${prevCrop}>${currCrop}`;
    const blended = blendPairEffectForSeason({
      pairKey,
      projectedSeason: season,
      alpha,
      localPairMatrix,
      twinPairMatrix,
      localBaselineStats,
      twinBaselineStats,
      unobservedPenaltyPct,
    });

    const horizonUncertaintyPct = Number(
      (
        horizonUncertaintyPerYearPct * Math.max(0, season.year - baselineEndYear) +
        twinDistanceUncertaintyFactor * alpha * twinDistance
      ).toFixed(2),
    );
    const [lowPct, highPct] = physicalEffectInterval(blended.meanEffectPct, [
      Math.min(
        blended.meanEffectPct,
        Number((blended.intervalPct[0] - horizonUncertaintyPct).toFixed(1)),
      ),
      Math.max(
        blended.meanEffectPct,
        Number((blended.intervalPct[1] + horizonUncertaintyPct).toFixed(1)),
      ),
    ]);

    evaluatedTransitionsCount += 1;
    observedWeightSum += blended.observedWeight;
    minSampleInHorizon = Math.min(minSampleInHorizon, blended.sampleCount);
    confidence = minConfidence(confidence, blended.confidence);
    sumGain += blended.meanEffectPct;
    sumLow += lowPct;
    sumHigh += highPct;

    yearlyForecast.push({
      year: season.year,
      stepInHorizon: idx + 1,
      fromCrop: prevCrop,
      crop: currCrop,
      pairKey,
      observed: blended.observed,
      sampleCount: blended.sampleCount,
      effectiveYearsCount: blended.effectiveYearsCount,
      confidence: blended.confidence,
      isMultiYearContinuation,
      projectedRegime: season.regime,
      twinRegimeUsed: blended.twinRegimeUsed,
      projectedTempC: season.meanTempC,
      projectedGdd10: season.gddBase10,
      projectedPrecipMm: season.precipMm,
      alphaTwin: alpha,
      expectedYieldGainPct: blended.meanEffectPct,
      localComponentPct: blended.localEffectPct,
      twinComponentPct: blended.twinEffectPct,
      intervalPct: [lowPct, highPct],
    });

    prevCrop = currCrop;
  }

  const denom = Math.max(1, evaluatedTransitionsCount);
  const meanFutureYieldGainPct = validatePhysicalEffectPct(Number((sumGain / denom).toFixed(2)));
  const futureYieldGainRangePct = physicalEffectInterval(meanFutureYieldGainPct, [
    Math.min(meanFutureYieldGainPct, Number((sumLow / denom).toFixed(1))),
    Math.max(meanFutureYieldGainPct, Number((sumHigh / denom).toFixed(1))),
  ]);
  const observedShare = Number((observedWeightSum / denom).toFixed(2));

  // La confiance future ne peut jamais dépasser la confiance historique du cycle
  if (historicalConfidence) {
    confidence = minConfidence(confidence, historicalConfidence);
  }

  // Dégradation d'un cran sur tout horizon pluriannuel long (>= 12 ans, couvrant l'horizon par défaut 2027-2040)
  if (projectedSeasons.at(-1).year - baselineEndYear >= longHorizonConfidenceDowngradeYears) {
    confidence = downgradeConfidence(confidence);
  }

  const regimeCounts = { normal: 0, sec: 0, chaud: 0 };
  for (const s of projectedSeasons) {
    regimeCounts[s.regime] = (regimeCounts[s.regime] || 0) + 1;
  }

  const firstAlpha = yearlyForecast[0]?.alphaTwin ?? 0;
  const lastAlpha = yearlyForecast[yearlyForecast.length - 1]?.alphaTwin ?? 0;

  return {
    meanFutureYieldGainPct,
    aggregation: 'equal_weight_annual_relative_vigor',
    futureYieldGainRangePct,
    observedShare,
    minSampleInHorizon: Number.isFinite(minSampleInHorizon) ? minSampleInHorizon : 0,
    confidence,
    horizonYearsCount: projectedSeasons.length,
    alphaTrajectory: {
      startYearAlpha: firstAlpha,
      endYearAlpha: lastAlpha,
      meanAlpha: Number(
        (yearlyForecast.reduce((s, y) => s + y.alphaTwin, 0) / yearlyForecast.length).toFixed(3),
      ),
    },
    futureRegimeDistribution: regimeCounts,
    yearlyForecast,
  };
}
