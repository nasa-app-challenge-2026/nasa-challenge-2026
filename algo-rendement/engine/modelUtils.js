/** Invariants partagés par l'évaluation historique et le transfert vers le jumeau. */
import { CROPS } from '../crops.js';
import { toSlots } from '../rotation.js';
import { CONFIG } from '../config.js';

export const MAX_ROTATION_YEARS = 6;
const CONFIDENCES = ['faible', 'moyenne', 'elevee'];

/** Un indice relatif ne peut pas être négatif ; les hausses ne sont pas plafonnées. */
export function validatePhysicalEffectPct(value, label = 'Effet relatif') {
  if (!Number.isFinite(value) || value < -100) {
    throw new RangeError(`${label} invalide : valeur finie supérieure ou égale à -100 % attendue.`);
  }
  return value;
}

/** Tronque uniquement l'enveloppe d'incertitude au domaine physique, jamais sa moyenne. */
export function physicalEffectInterval(meanEffectPct, intervalPct) {
  validatePhysicalEffectPct(meanEffectPct);
  if (
    !Array.isArray(intervalPct) ||
    intervalPct.length !== 2 ||
    !intervalPct.every(Number.isFinite) ||
    intervalPct[0] > meanEffectPct ||
    intervalPct[1] < meanEffectPct
  ) {
    throw new RangeError('Intervalle de paire non fini ou incohérent.');
  }
  return [Math.max(-100, intervalPct[0]), intervalPct[1]];
}

export function validateCurrentCrop(currentCrop) {
  if (
    currentCrop !== null &&
    (typeof currentCrop !== 'string' || !Object.hasOwn(CROPS, currentCrop))
  ) {
    throw new RangeError(`Culture actuelle invalide (currentCrop=${currentCrop}).`);
  }
}

/** Valider AVANT toSlots : une durée non bornée provoquerait une allocation infinie. */
export function validatedRotationSlots(rotation) {
  if (!Array.isArray(rotation) || rotation.length > MAX_ROTATION_YEARS) {
    throw new RangeError('Rotation invalide : tableau de 6 entrées maximum attendu.');
  }
  let total = 0;
  for (const entry of rotation) {
    if (!entry || typeof entry.crop !== 'string' || !Object.hasOwn(CROPS, entry.crop)) {
      throw new RangeError('Culture inconnue dans la rotation.');
    }
    const years = entry.years ?? 1;
    if (
      !Number.isInteger(years) ||
      years < 1 ||
      years > MAX_ROTATION_YEARS ||
      total + years > MAX_ROTATION_YEARS
    ) {
      throw new RangeError('Durée de rotation invalide : entiers positifs, 6 ans maximum.');
    }
    if (CROPS[entry.crop].years > 1 && years !== CROPS[entry.crop].years) {
      throw new RangeError(
        `La ${entry.crop} doit occuper un bloc de ${CROPS[entry.crop].years} ans.`,
      );
    }
    total += years;
  }
  return toSlots(rotation);
}

export function minConfidence(...values) {
  return CONFIDENCES[Math.min(...values.map((v) => Math.max(0, CONFIDENCES.indexOf(v))))];
}

export function downgradeConfidence(value) {
  return CONFIDENCES[Math.max(0, CONFIDENCES.indexOf(value) - 1)];
}

export function confidenceFromCounts(sampleCount, effectiveYearsCount) {
  if (sampleCount >= CONFIG.sampling.minSamplesHighConfidence && effectiveYearsCount >= 3) {
    return 'elevee';
  }
  if (sampleCount >= CONFIG.sampling.minSamplesMediumConfidence && effectiveYearsCount >= 2) {
    return 'moyenne';
  }
  return 'faible';
}

export function resolvePairEvidence(stat, regime = 'all') {
  const sub = regime !== 'all' ? stat.byRegime?.[regime] : null;
  const evidence = sub || stat;
  const meanEffectPct = validatePhysicalEffectPct(evidence.meanEffectPct);
  const intervalPct = physicalEffectInterval(
    meanEffectPct,
    evidence.intervalPct || stat.intervalPct,
  );
  if (!Number.isInteger(evidence.sampleCount) || evidence.sampleCount < 1) {
    throw new RangeError('Statistique de paire invalide ou intervalle incohérent.');
  }
  const stdErrorPct = evidence.stdErrorPct ?? stat.stdErrorPct;
  const effectiveYearsCount = evidence.effectiveYearsCount ?? 0;
  if (
    !Number.isInteger(effectiveYearsCount) ||
    effectiveYearsCount < 0 ||
    effectiveYearsCount > Math.min(86, evidence.sampleCount) ||
    (stdErrorPct !== undefined && (!Number.isFinite(stdErrorPct) || stdErrorPct < 0))
  ) {
    throw new RangeError('Effectif temporel ou incertitude de paire invalide.');
  }
  let confidence = minConfidence(
    stat.confidence,
    confidenceFromCounts(evidence.sampleCount, effectiveYearsCount),
  );
  if (regime !== 'all' && !sub) confidence = 'faible';
  return {
    meanEffectPct,
    intervalPct,
    stdErrorPct,
    sampleCount: evidence.sampleCount,
    effectiveYearsCount,
    confidence,
    regimeSampleCount: sub?.sampleCount || 0,
  };
}

/** Les effets partagent une référence normalisée à 100 ; un écart n'est pas un ratio. */
export function relativeGainPct(effect, baselineEffect) {
  if (!Number.isFinite(effect) || !Number.isFinite(baselineEffect)) {
    return null;
  }
  validatePhysicalEffectPct(effect);
  validatePhysicalEffectPct(baselineEffect, 'Référence relative');
  if (baselineEffect === -100) return null;
  const gain = 100 * ((1 + effect / 100) / (1 + baselineEffect / 100) - 1);
  return validatePhysicalEffectPct(Number(gain.toFixed(2)), 'Gain relatif');
}
