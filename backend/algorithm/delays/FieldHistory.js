/**
 * What the field grew before its first cycle, as occupations: the crop in place
 * (with all its years if it is a perennial) and the crops the farmer gave for the
 * previous years. Consecutive years of the same crop become one occupation.
 */
import { Occupation, OCCUPATION_SOURCE } from './Occupation.js';
import { defaultDelayCatalog } from './ReturnDelayCatalog.js';

/**
 * @param {object} p
 * @param {{ cropId: string, productionYears?: number }|null} p.inPlace crop in place now
 * @param {number} p.freeYear   year the crop in place is harvested (the field becomes free)
 * @param {{ year: number, cropId: string }[]} [p.past] crops of the previous years
 * @returns {Occupation[]}
 */
export function fieldHistory({ inPlace, freeYear, past = [] }, catalog = defaultDelayCatalog) {
  const occupations = [];
  let inPlaceFirstYear = freeYear + 1;
  if (inPlace) {
    inPlaceFirstYear = freeYear - Math.max(inPlace.productionYears ?? 0, 1) + 1;
    occupations.push(
      new Occupation(
        catalog.speciesOf(inPlace.cropId),
        inPlaceFirstYear,
        freeYear,
        OCCUPATION_SOURCE.HISTORY,
      ),
    );
  }
  for (const { year, cropId } of past) {
    if (year >= inPlaceFirstYear || !cropId) continue; // that year belongs to the crop in place
    occupations.push(
      new Occupation(catalog.speciesOf(cropId), year, year, OCCUPATION_SOURCE.HISTORY),
    );
  }
  occupations.sort((a, b) => a.firstYear - b.firstYear);
  const merged = [];
  for (const o of occupations) {
    const last = merged[merged.length - 1];
    if (last && last.cropId === o.cropId && o.firstYear <= last.lastYear + 1) {
      merged[merged.length - 1] = new Occupation(
        o.cropId,
        last.firstYear,
        Math.max(o.lastYear, last.lastYear),
        OCCUPATION_SOURCE.HISTORY,
      );
    } else merged.push(o);
  }
  return merged;
}
