/** Optimisation de l'indice annuel relatif, sous l'hypothèse vigueur/rendement du modèle. */
import { CROPS, CROP_IDS } from '../crops.js';
import { currentCropConflict, rotationErrors } from '../rotation.js';
import { CONFIG } from '../config.js';
import { forecastFutureRotationYield, normalizeCycleOffset } from './climateTwins.js';
import {
  MAX_ROTATION_YEARS,
  minConfidence,
  physicalEffectInterval,
  relativeGainPct,
  resolvePairEvidence,
  validateCurrentCrop,
  validatePhysicalEffectPct,
  validatedRotationSlots,
} from './modelUtils.js';

const ALLOWED_REGIMES = new Set(['all', 'normal', 'sec', 'chaud']);

export function validateCycleYears(cycleYears) {
  const n = Number(cycleYears);
  if (!Number.isInteger(n) || n < 2 || n > MAX_ROTATION_YEARS) {
    throw new RangeError(
      `Paramètre cycleYears invalide (${cycleYears}) : entier entre 2 et 6 ans attendu.`,
    );
  }
  return n;
}

export function validateRegime(regime) {
  const r = String(regime ?? 'all');
  if (!ALLOWED_REGIMES.has(r)) throw new RangeError(`Régime climatique invalide (${regime}).`);
  return r;
}

export function computeUnobservedPairPenalty(pairMatrix) {
  const effects = Object.values(pairMatrix?.pairs || {})
    .map((p) => p.meanEffectPct)
    .filter(Number.isFinite)
    .sort((a, b) => a - b);
  if (!effects.length) return -2.5;
  return validatePhysicalEffectPct(
    Number(
      Math.min(
        CONFIG.hyperparameters.maxUnobservedPairPenaltyPct,
        effects[Math.floor(effects.length * 0.25)],
      ).toFixed(2),
    ),
    'Pénalité de paire inconnue',
  );
}

export function evaluateRotationYieldFromPairs({
  rotation,
  pairMatrix,
  currentCrop = null,
  offset = 0,
  regime = 'all',
}) {
  const validRegime = validateRegime(regime);
  validateCurrentCrop(currentCrop);
  const slots = validatedRotationSlots(rotation);
  const L = slots.length;
  const safeOffset = normalizeCycleOffset(offset, L);
  const pairs = pairMatrix?.pairs || {};
  const penalty = computeUnobservedPairPenalty(pairMatrix);
  const halfWidth = CONFIG.hyperparameters.unobservedHalfWidthPct;
  const transitions = [];
  let previous = currentCrop || slots[(safeOffset - 1 + L) % L]?.crop;

  // Une observation par année, y compris les continuations des cultures pérennes.
  // La culture actuelle remplace l'antécédent cyclique de la première année.
  for (let i = 0; i < L; i++) {
    const crop = slots[(safeOffset + i) % L].crop;
    const pairKey = `${previous}>${crop}`;
    const stat = Object.hasOwn(pairs, pairKey) ? pairs[pairKey] : null;
    const resolved = stat
      ? resolvePairEvidence(stat, validRegime)
      : {
          meanEffectPct: penalty,
          intervalPct: physicalEffectInterval(penalty, [penalty - halfWidth, penalty + halfWidth]),
          sampleCount: 0,
          effectiveYearsCount: 0,
          confidence: 'faible',
        };
    const monoKey = `${crop}>${crop}`;
    const mono = Object.hasOwn(pairs, monoKey)
      ? resolvePairEvidence(pairs[monoKey], validRegime)
      : null;
    transitions.push({
      step: i + 1,
      from: previous,
      to: crop,
      pairKey,
      observed: !!stat,
      ...resolved,
      isMultiYearContinuation: previous === crop && CROPS[crop].years > 1,
      gainVsMonoculturePct: mono
        ? relativeGainPct(resolved.meanEffectPct, mono.meanEffectPct)
        : null,
      monocultureEffectPct: mono?.meanEffectPct ?? null,
      ...(stat?.calibratedYield ? { calibratedYield: stat.calibratedYield } : {}),
    });
    previous = crop;
  }

  const mean = (fn) => transitions.reduce((sum, t) => sum + fn(t), 0) / Math.max(1, L);
  const monoAvailable = L > 0 && transitions.every((t) => t.monocultureEffectPct !== null);
  const meanYieldGainPct = validatePhysicalEffectPct(
    Number(mean((t) => t.meanEffectPct).toFixed(2)),
    'Moyenne du cycle',
  );
  return {
    meanYieldGainPct,
    gainVsMonocultureCyclePct: monoAvailable
      ? relativeGainPct(
          mean((t) => t.meanEffectPct),
          mean((t) => t.monocultureEffectPct),
        )
      : null,
    yieldGainRangePct: physicalEffectInterval(meanYieldGainPct, [
      Math.min(meanYieldGainPct, Number(mean((t) => t.intervalPct[0]).toFixed(1))),
      Math.max(meanYieldGainPct, Number(mean((t) => t.intervalPct[1]).toFixed(1))),
    ]),
    openingTransition: currentCrop ? transitions[0] || null : null,
    observedShare: Number(mean((t) => Number(t.observed)).toFixed(2)),
    minSampleInCycle: L ? Math.min(...transitions.map((t) => t.sampleCount)) : 0,
    confidence: L ? minConfidence(...transitions.map((t) => t.confidence)) : 'faible',
    evaluationBasis: currentCrop ? 'first_cycle_from_current_crop' : 'closed_cycle',
    aggregation: 'equal_weight_annual_relative_vigor',
    transitions,
  };
}

export function findBestMultiCropRotationsForYield({
  pairMatrix,
  cycleYears = 4,
  availableCrops = CROP_IDS,
  currentCrop = null,
  offset = 0,
  minDistinctCrops = 2,
  regime = 'all',
  topK = 5,
  projectedSeasons = null,
  twinMatch = null,
  localBaselineStats = null,
}) {
  const validCycleYears = validateCycleYears(cycleYears);
  const validRegime = validateRegime(regime);
  validateCurrentCrop(currentCrop);
  const safeOffset = normalizeCycleOffset(offset, validCycleYears);
  const safeTopK = Math.max(1, Math.min(50, Math.floor(Number(topK) || 5)));
  if (
    !Number.isInteger(minDistinctCrops) ||
    minDistinctCrops < 1 ||
    minDistinctCrops > CROP_IDS.length
  ) {
    throw new RangeError('minDistinctCrops doit être un entier entre 1 et 6.');
  }
  if (!Array.isArray(availableCrops) || availableCrops.length > 1000) {
    throw new TypeError('availableCrops doit être un tableau de 1000 identifiants maximum.');
  }
  const pool = [
    ...new Set(availableCrops.filter((c) => typeof c === 'string' && Object.hasOwn(CROPS, c))),
  ];
  const candidates = [];
  const seq = [];
  const evaluateCandidate = () => {
    const rotation = seq.map((crop) => ({ crop, years: CROPS[crop].years, cover: null }));
    if (
      rotationErrors(rotation).length ||
      currentCropConflict({ rotation, currentCrop, offset: safeOffset }) ||
      new Set(seq).size < minDistinctCrops
    )
      return;
    const evaluation = evaluateRotationYieldFromPairs({
      rotation,
      pairMatrix,
      currentCrop,
      offset: safeOffset,
      regime: validRegime,
    });
    if (evaluation.observedShare < 0.5) return;
    const futureForecast =
      projectedSeasons?.length && localBaselineStats
        ? forecastFutureRotationYield({
            rotation,
            currentCrop,
            offset: safeOffset,
            projectedSeasons,
            localPairMatrix: pairMatrix,
            twinMatch,
            localBaselineStats,
            unobservedPenaltyPct: computeUnobservedPairPenalty(pairMatrix),
            historicalConfidence: evaluation.confidence,
          })
        : null;
    candidates.push({
      rotation,
      cropsSequence: [...seq],
      distinctCrops: new Set(seq).size,
      rankingScore: futureForecast?.meanFutureYieldGainPct ?? evaluation.meanYieldGainPct,
      ...evaluation,
      ...(futureForecast ? { futureForecast } : {}),
    });
  };
  const walk = (yearsUsed) => {
    if (yearsUsed === validCycleYears) return evaluateCandidate();
    for (const crop of pool) {
      if (yearsUsed + CROPS[crop].years > validCycleYears) continue;
      seq.push(crop);
      walk(yearsUsed + CROPS[crop].years);
      seq.pop();
    }
  };
  walk(0);
  candidates.sort(
    (a, b) =>
      Number(b.observedShare === 1) - Number(a.observedShare === 1) ||
      b.rankingScore - a.rankingScore ||
      b.observedShare - a.observedShare,
  );
  return candidates.slice(0, safeTopK);
}
