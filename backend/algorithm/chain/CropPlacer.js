/**
 * Step 9b, placement rules: can a sheet fill position p after the previous harvest?
 *
 *   - A crop belongs to the position where it is HARVESTED ("wheat 2028" = sown in
 *     2027, harvested in 2028).
 *   - Sowing: inside its window, at least a week after the previous harvest, after
 *     the last spring frost for a frost-sensitive crop.
 *   - Harvest of a summer crop: when the degree-days since sowing are enough, with
 *     the heat of each month of the cycle's climate; it must mature before the first
 *     fall frost. Winter crops and perennials have a fixed harvest date (earlier with
 *     warming).
 *   - A crop longer than f months (alfalfa, hay, wheat with f = 6) spans positions.
 *   - Double crop (soybean after wheat): only right after it, at most a month later.
 *   - A winter crop must survive the January minimum of the cycle.
 */
import { FALLOW_SHEET_ID, SHEETS } from '../../../data/reference/crops.js';
import {
  DOUBLE_CROP_MAX_DELAY_MONTHS,
  MONTHS_PER_YEAR,
  SOWING_DELAY_MONTHS,
  SOWING_STEP_MONTHS,
  SOWING_YEARS_TRIED,
  TIME_EPSILON,
} from '../config/calendar.js';

/**
 * @param {string} sheetId
 * @param {number} position absolute position index
 * @param {number} previousHarvest absolute month
 * @param {string|null} previousSheetId the step before (for double crops)
 * @param {{ time: { frequencyMonths: number, positionStartMonth: number },
 *           climate: import('../climate/CycleClimate.js').CycleClimate }} ctx
 * @returns {{ sowing: number|null, harvest: number, lastPosition: number }|null}
 */
export function placeCrop(sheetId, position, previousHarvest, previousSheetId, { time, climate }) {
  const sheet = SHEETS[sheetId];
  const f = time.frequencyMonths;
  const anchor = time.positionStartMonth;
  const positionStart = anchor + position * f;
  const positionEnd = anchor + (position + 1) * f;
  if (sheetId === FALLOW_SHEET_ID)
    return { sowing: null, harvest: previousHarvest, lastPosition: position };
  if (sheet.januaryMinimumC !== null && climate.januaryMinimumC < sheet.januaryMinimumC)
    return null;
  if (sheet.onlyAfter && !sheet.onlyAfter.includes(previousSheetId)) return null;

  const [windowStart, windowEndOfSheet] = sheet.sowingWindow;
  let windowEnd = windowEndOfSheet;
  const firstYear = Math.floor(previousHarvest / MONTHS_PER_YEAR) - 1;
  for (let year = firstYear; year < firstYear + SOWING_YEARS_TRIED; year++) {
    const yearStart = year * MONTHS_PER_YEAR;
    let sowing = Math.max(yearStart + windowStart, previousHarvest + SOWING_DELAY_MONTHS);
    if (sheet.frostSensitive && climate.lastSpringFrost !== null)
      sowing = Math.max(sowing, yearStart + climate.lastSpringFrost);
    if (sheet.productionYears) sowing = Math.max(sowing, positionStart);
    if (sheet.onlyAfter)
      windowEnd = Math.min(windowEnd, previousHarvest - yearStart + DOUBLE_CROP_MAX_DELAY_MONTHS);

    while (sowing <= yearStart + windowEnd + TIME_EPSILON) {
      const harvest = harvestTime(sheet, sowing, yearStart, windowStart, climate);
      if (harvest === null) break; // not mature before the frost: try the next year
      const withinOnePosition = !sheet.productionYears && harvest - sowing <= f;
      if (harvest >= positionEnd && withinOnePosition) break; // harvested too late for p
      if (harvest >= positionStart) {
        const lastPosition = Math.floor((harvest - anchor) / f);
        if (lastPosition > position && withinOnePosition) break;
        return { sowing, harvest, lastPosition };
      }
      sowing += SOWING_STEP_MONTHS; // harvested before the position: sow later
    }
  }
  return null;
}

/** Harvest of a sheet sown at `sowing`, or null when a summer crop cannot mature. */
function harvestTime(sheet, sowing, yearStart, windowStart, climate) {
  if (sheet.degreeDays !== null) {
    const harvest = climate.maturity(sowing, sheet.degreeDays);
    const frozen =
      sheet.frostSensitive &&
      climate.firstFallFrost !== null &&
      harvest !== null &&
      harvest > yearStart + climate.firstFallFrost;
    return harvest === null || frozen ? null : harvest;
  }
  const month = sheet.harvestMonth - climate.harvestAdvanceMonths;
  let harvest = yearStart + month + MONTHS_PER_YEAR * (Math.max(sheet.productionYears, 1) - 1);
  if (month < windowStart) harvest += MONTHS_PER_YEAR; // sown in fall, harvested the next year
  return harvest;
}
