/**
 * Return delay of every crop, derived from the two sources (Fruchtfolge, SARE):
 *   minimum (hard constraint) = the smaller of the two values;
 *   recommended (pest criterion) = the larger.
 * With a single source, the minimum is 1 year (never two years in a row).
 */
import {
  CROP_DELAYS,
  DELAY_ALIASES,
  EXEMPT_FAMILIES,
  SOIL_DISEASES,
} from '../../../data/reference/returnDelays.js';

/** With a single source, a crop must still skip one year. */
const SINGLE_SOURCE_MINIMUM = 1;

/**
 * @typedef {object} CropDelay
 * @property {string} id
 * @property {string} family
 * @property {number} minimum      years without the crop, at least
 * @property {number} recommended  years without the crop, advised
 * @property {boolean} perennial
 * @property {string[]} diseases   soil diseases it hosts
 */

export class ReturnDelayCatalog {
  constructor({ crops = CROP_DELAYS, diseases = SOIL_DISEASES, aliases = DELAY_ALIASES } = {}) {
    this.diseases = diseases;
    this.aliases = aliases;
    this.exemptFamilies = new Set(EXEMPT_FAMILIES);
    /** @type {Map<string, CropDelay>} */
    this.delays = new Map(Object.entries(crops).map(([id, row]) => [id, this.#derive(id, row)]));
  }

  #derive(id, { family, fruchtfolgeYearsWithout, referenceDisease, perennial }) {
    const sare = referenceDisease ? this.diseases[referenceDisease].low : null;
    const values = [fruchtfolgeYearsWithout, sare].filter((v) => v !== null);
    let minimum = SINGLE_SOURCE_MINIMUM;
    if (values.length === 2) minimum = Math.min(...values);
    else if (values.length === 1) minimum = Math.min(SINGLE_SOURCE_MINIMUM, values[0]);
    return {
      id,
      family,
      fruchtfolge: fruchtfolgeYearsWithout,
      sare,
      minimum,
      recommended: values.length ? Math.max(...values) : minimum,
      perennial,
      diseases: Object.keys(this.diseases).filter((d) => this.diseases[d].hosts.includes(id)),
    };
  }

  /** The crop whose delays apply (double-crop soybean = soybean). */
  speciesOf(cropId) {
    return this.aliases[cropId] ?? cropId;
  }

  /** @returns {CropDelay|undefined} */
  get(cropId) {
    return this.delays.get(this.speciesOf(cropId));
  }

  isExemptFamily(family) {
    return this.exemptFamilies.has(family);
  }

  /** Years without a host required by a declared disease for this crop (0 if none). */
  declaredDiseaseDelay(cropId, declaredDiseases) {
    const species = this.speciesOf(cropId);
    return Math.max(
      0,
      ...declaredDiseases
        .filter((d) => this.diseases[d]?.hosts.includes(species))
        .map((d) => this.diseases[d].high),
    );
  }
}

export const defaultDelayCatalog = new ReturnDelayCatalog();
