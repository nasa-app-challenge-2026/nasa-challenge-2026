/**
 * Weights of a cycle: the farmer's weights (rank order centroid, step 1), adjusted
 * to the risks of the field for that cycle (step 8):
 *   erosion × (1 + erosion risk), water × (1 + water risk), forage × 0.3 without livestock.
 */
import { NO_LIVESTOCK_FORAGE_FACTOR } from '../config/scoring.js';

/**
 * @param {Record<string, number>} baseWeights
 * @param {{ erosion: number, water: number }} risks
 * @param {boolean} livestock
 */
export function weightsForCycle(baseWeights, risks, livestock) {
  const weights = { ...baseWeights };
  weights.erosion *= 1 + risks.erosion;
  weights.eau *= 1 + risks.water;
  if (!livestock) weights.fourrage *= NO_LIVESTOCK_FORAGE_FACTOR;
  return weights;
}
