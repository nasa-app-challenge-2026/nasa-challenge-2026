/**
 * Automatic cover crops (one crop a year): a rye is sown in every gap long enough
 * between a harvest and the next sowing (corn harvested in October, soybean sown in
 * May). With 6 or 4 months per position, rye is a crop like the others and takes
 * its own position instead.
 */
import { CROP_SHEETS, ROLE } from '../../../data/reference/crops.js';
import { MONTHS_PER_YEAR, SOWING_DELAY_MONTHS } from '../config/calendar.js';
import { chainStep } from './ChainStep.js';

const COVER_SHEETS = CROP_SHEETS.filter((s) => s.role === ROLE.COVER);

/**
 * @param {ReturnType<typeof chainStep>[]} chain
 * @param {{ coversEnabled: boolean, entryHarvest: number,
 *           climate: import('../climate/CycleClimate.js').CycleClimate }} ctx
 * @returns {ReturnType<typeof chainStep>[]} cover steps (no position)
 */
export function coverCrops(chain, { coversEnabled, entryHarvest, climate }) {
  if (!coversEnabled) return [];
  const covers = [];
  let previousHarvest = entryHarvest;
  for (const next of chain.filter((step) => step.sowing !== null)) {
    for (const cover of COVER_SHEETS) {
      if (cover.januaryMinimumC !== null && climate.januaryMinimumC < cover.januaryMinimumC)
        continue;
      const yearStart = Math.floor(previousHarvest / MONTHS_PER_YEAR) * MONTHS_PER_YEAR;
      const sowing = Math.max(
        yearStart + cover.sowingWindow[0],
        previousHarvest + SOWING_DELAY_MONTHS,
      );
      if (sowing > yearStart + cover.sowingWindow[1]) continue;
      const end = yearStart + MONTHS_PER_YEAR + cover.harvestMonth - climate.harvestAdvanceMonths;
      if (end <= next.sowing - SOWING_DELAY_MONTHS) {
        covers.push(chainStep(cover.id, sowing, end));
        break;
      }
    }
    previousHarvest = next.harvest;
  }
  return covers;
}
