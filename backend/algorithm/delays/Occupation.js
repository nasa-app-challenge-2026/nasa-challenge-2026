/**
 * A sold crop on the field, from year `firstYear` to year `lastYear` (both
 * included): one year for an annual crop, its production years for a perennial.
 */
export const OCCUPATION_SOURCE = {
  CHAIN: 'chaîne',
  HISTORY: 'historique',
  NEXT_CYCLE: 'cycle suivant',
  PREVIOUS_CYCLE: 'cycle précédent',
};

export class Occupation {
  constructor(cropId, firstYear, lastYear, source = OCCUPATION_SOURCE.CHAIN) {
    this.cropId = cropId;
    this.firstYear = firstYear;
    this.lastYear = lastYear;
    this.source = source;
    Object.freeze(this);
  }

  shiftedBy(years, source) {
    return new Occupation(this.cropId, this.firstYear + years, this.lastYear + years, source);
  }

  withSource(source) {
    return new Occupation(this.cropId, this.firstYear, this.lastYear, source);
  }
}

/** Years without crop between two occupations (two harvests the same year = −1). */
export const yearsBetween = (before, after) => after.firstYear - before.lastYear - 1;
