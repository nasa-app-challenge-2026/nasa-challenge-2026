/**
 * What steps 4 to 7 hand to the chain building (step 9b) for one cycle: the crops
 * grown in the twins, the successions observed there (crop A one year → crop B the
 * next), the value of each previous crop (in %, or unknown) and the mean sigma.
 */
const pairKey = (previous, next) => `${previous}>${next}`;

export class TwinEvidence {
  /**
   * @param {object} p
   * @param {Iterable<string>} p.crops crop ids grown in the twin fields
   * @param {Iterable<[string, string, number|null]>} p.successions [previous, next, value %]
   * @param {number} [p.sigmaMean]
   * @param {{ cell: object, sigma: number, sources: string[] }[]} [p.twins] the twin cells (map)
   * @param {[string, number][]} [p.topRotations] most frequent rotations and their weight
   */
  constructor({ crops, successions, sigmaMean = 1, twins = [], topRotations = [] }) {
    this.crops = new Set(crops);
    this.precropValues = new Map();
    for (const [previous, next, value] of successions)
      this.precropValues.set(pairKey(previous, next), value ?? null);
    this.sigmaMean = sigmaMean;
    this.twins = twins;
    this.topRotations = topRotations;
  }

  isGrown(cropId) {
    return this.crops.has(cropId);
  }

  /** Was "previous → next" seen in the twins? A crop after itself always counts as seen. */
  isObserved(previous, next) {
    return previous === next || this.precropValues.has(pairKey(previous, next));
  }

  /** Value (%) of `previous` for `next`: a number, null (seen, < 20 fields) or undefined (never seen). */
  precropValue(previous, next) {
    return this.precropValues.get(pairKey(previous, next));
  }
}
