/**
 * Steps 6 and 7 on the fields kept by the soil filter (step 5): what the farmers of
 * the twins really grow, field by field (USDA Crop Sequence Boundaries in the U.S.,
 * AAFC annual crop inventory in Canada).
 *
 * Weight of a field = area × (1 − σ/2), σ being the climate distance of its cell:
 * a field of a cell at σ ≥ 2 does not count.
 */
import { GOOD_TWIN_MAX_SIGMA } from '../config/climate.js';
import { TOP_ROTATIONS } from '../config/twins.js';
import { mean } from '../math/numbers.js';
import { precropValue } from './PrecropValue.js';
import { rotationOf } from './RotationPattern.js';
import { TwinEvidence } from './TwinEvidence.js';

/**
 * @param {{ sequence: string[], areaHa: number, sigma: number }[]} fields
 * @param {{ crop: string, previous: string, yieldGap: number }[]} fieldYears step 7 data
 * @param {object[]} [twins] the twin cells, kept for the map
 */
export function buildTwinEvidence(fields, fieldYears, twins = []) {
  const rotationWeights = new Map();
  const crops = new Set();
  const pairs = new Map();
  const sigmas = [];
  for (const field of fields) {
    const weight = field.areaHa * Math.max(0, 1 - field.sigma / GOOD_TWIN_MAX_SIGMA);
    if (weight <= 0) continue;
    sigmas.push(field.sigma);
    const rotation = rotationOf(field.sequence);
    if (rotation) rotationWeights.set(rotation, (rotationWeights.get(rotation) ?? 0) + weight);
    field.sequence.forEach((crop) => crops.add(crop));
    for (let i = 1; i < field.sequence.length; i++) {
      const [previous, next] = [field.sequence[i - 1], field.sequence[i]];
      if (previous !== next) pairs.set(`${previous}>${next}`, [previous, next]);
    }
  }
  const successions = [...pairs.values()].map(([previous, next]) => [
    previous,
    next,
    precropValue(fieldYears, previous, next),
  ]);
  const topRotations = [...rotationWeights.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, TOP_ROTATIONS);
  return new TwinEvidence({
    crops,
    successions,
    sigmaMean: sigmas.length ? mean(sigmas) : NaN,
    twins,
    topRotations,
  });
}
