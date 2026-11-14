/**
 * Step 5: in the twin cells, keep only the fields whose soil looks like the field's.
 *
 * SoilGrids 2.0 (250 m), mean over 0–30 cm of 4 properties: clay, sand, organic
 * carbon, pH. A soil test of the farmer replaces SoilGrids for his field. Each
 * difference is divided by a tolerance (organic carbon compared in logarithm), then
 * the root mean square of the 4 differences: ≤ 1 = equivalent soil. With fewer
 * than 200 fields left, the tolerances are widened by 25 % (and the app says so).
 */
import {
  MIN_FIELDS_AFTER_SOIL_FILTER,
  SAME_SOIL_MAX_DISTANCE,
  SOIL_TOLERANCES,
  SOIL_TOLERANCE_WIDENING,
} from '../config/twins.js';

/**
 * @typedef {{ clayPct: number, sandPct: number, organicCarbon: number, ph: number }} Soil
 *          organicCarbon in g/kg
 */

/** Distance between two soils (≤ 1 = same soil). */
export function soilDistance(a, b, tolerances = SOIL_TOLERANCES) {
  const gaps = [
    (a.clayPct - b.clayPct) / tolerances.clayPct,
    (a.sandPct - b.sandPct) / tolerances.sandPct,
    Math.log(a.organicCarbon / b.organicCarbon) / Math.log(tolerances.organicCarbonRatio),
    (a.ph - b.ph) / tolerances.ph,
  ];
  return Math.sqrt(gaps.reduce((s, g) => s + g * g, 0) / gaps.length);
}

const widened = (tolerances) => ({
  clayPct: tolerances.clayPct * SOIL_TOLERANCE_WIDENING,
  sandPct: tolerances.sandPct * SOIL_TOLERANCE_WIDENING,
  organicCarbonRatio: tolerances.organicCarbonRatio ** SOIL_TOLERANCE_WIDENING,
  ph: tolerances.ph * SOIL_TOLERANCE_WIDENING,
});

export class SoilFilter {
  /** @param {Soil} fieldSoil the farmer's soil test, or SoilGrids at the field */
  constructor(fieldSoil, { minFields = MIN_FIELDS_AFTER_SOIL_FILTER } = {}) {
    this.fieldSoil = fieldSoil;
    this.minFields = minFields;
  }

  /**
   * @template {{ soil: Soil }} F
   * @param {F[]} fields fields of the twin cells
   * @returns {{ fields: F[], widened: boolean }}
   */
  keepComparable(fields) {
    const keep = (tolerances) =>
      fields.filter(
        (f) => soilDistance(this.fieldSoil, f.soil, tolerances) <= SAME_SOIL_MAX_DISTANCE,
      );
    const strict = keep(SOIL_TOLERANCES);
    if (strict.length >= this.minFields) return { fields: strict, widened: false };
    return { fields: keep(widened(SOIL_TOLERANCES)), widened: true };
  }
}
