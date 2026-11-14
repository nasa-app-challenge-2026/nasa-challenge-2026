/**
 * Place an imposed sequence of crops in a cycle (the farmer's current rotation,
 * a chain kept from one cycle to the next, the robustness test).
 *
 * With `fillGaps` (the reference rotation, never discarded): a perennial too long
 * for the end of the cycle is shortened (Luzerne ×3 → ×2); a crop that does not
 * fit leaves an empty position and is tried again at the next one.
 */
import { CROP_SHEETS, SHEETS } from '../../../data/reference/crops.js';
import { chainStep, fallowStep } from './ChainStep.js';
import { placeCrop } from './CropPlacer.js';

/** Shorter versions of a perennial sheet, longest first. */
function shorterSheets(sheetId) {
  const sheet = SHEETS[sheetId];
  return CROP_SHEETS.filter(
    (s) =>
      s.cropId === sheet.cropId &&
      s.productionYears > 0 &&
      s.productionYears < sheet.productionYears,
  ).sort((a, b) => b.productionYears - a.productionYears);
}

/**
 * @param {string[]} sheetIds the sequence to place
 * @param {import('./CycleContext.js').CycleContext} ctx
 * @returns {ReturnType<typeof chainStep>[]|null} null when it does not fill the cycle
 */
export function replayChain(sheetIds, ctx, { fillGaps = false } = {}) {
  const N = ctx.positions;
  const chain = [];
  let position = 0;
  let harvest = ctx.entryHarvest;
  let i = 0;
  const fits = (placed) => placed && placed.lastPosition - ctx.firstPosition < N;
  while (position < N && i < sheetIds.length) {
    let sheetId = sheetIds[i];
    const previous = chain[chain.length - 1]?.sheetId ?? ctx.entrySheetId;
    const tryPlace = (id) => placeCrop(id, ctx.firstPosition + position, harvest, previous, ctx);
    let placed = tryPlace(sheetId);
    if (fillGaps && !fits(placed) && SHEETS[sheetId].productionYears) {
      for (const shorter of shorterSheets(sheetId)) {
        const attempt = tryPlace(shorter.id);
        if (fits(attempt)) {
          sheetId = shorter.id;
          placed = attempt;
          break;
        }
      }
    }
    if (!fits(placed)) {
      if (!fillGaps) return null;
      chain.push(fallowStep(harvest, position));
      position += 1;
      continue;
    }
    const last = placed.lastPosition - ctx.firstPosition;
    chain.push(chainStep(sheetId, placed.sowing, placed.harvest, position, last));
    harvest = placed.harvest;
    position = last + 1;
    i += 1;
  }
  while (fillGaps && position < N) {
    chain.push(fallowStep(harvest, position));
    position += 1;
  }
  return position === N ? chain : null;
}
