/**
 * A chain = the crops that fill the N positions of a cycle, in order. Each step is
 * one sheet sown at `sowing` and harvested at `harvest` (absolute months), from
 * position `firstPosition` to `lastPosition` (relative to the cycle). A fallow
 * step has no sowing: its harvest is the previous harvest. Cover crops placed
 * between two steps have no position.
 */
import { FALLOW_SHEET_ID, ROLE, SHEETS } from '../../../data/reference/crops.js';
import { Occupation } from '../delays/Occupation.js';
import { MonthTime } from '../time/MonthTime.js';

export function chainStep(sheetId, sowing, harvest, firstPosition = null, lastPosition = null) {
  return Object.freeze({ sheetId, sowing, harvest, firstPosition, lastPosition });
}

export const fallowStep = (previousHarvest, position) =>
  chainStep(FALLOW_SHEET_ID, null, previousHarvest, position, position);

export const sheetOf = (step) => SHEETS[step.sheetId];
export const isSold = (step) => sheetOf(step).role === ROLE.SOLD;
export const isFallow = (step) => step.sheetId === FALLOW_SHEET_ID;
export const isCover = (step) => step.firstPosition === null;

/** Sheet ids of the steps, the identity of a chain. */
export const sheetIds = (chain) => chain.map((s) => s.sheetId);
export const lastHarvest = (chain) => chain[chain.length - 1].harvest;

/** The last sold sheet of a chain, or `fallback`. */
export function lastSoldSheet(chain, fallback = null) {
  for (let i = chain.length - 1; i >= 0; i--) if (isSold(chain[i])) return chain[i].sheetId;
  return fallback;
}

/**
 * The sold crops of a chain as occupations of the field (years), for the return
 * delays: an annual crop counts for the year of its harvest, a perennial from the
 * year it is sown to its last harvest.
 * @param {import('../delays/ReturnDelayCatalog.js').ReturnDelayCatalog} catalog
 */
export function toOccupations(chain, catalog) {
  return chain
    .filter((step) => isSold(step) && step.harvest !== null)
    .map((step) => {
      const sheet = sheetOf(step);
      const lastYear = MonthTime.yearOf(step.harvest);
      const firstYear = sheet.productionYears ? MonthTime.yearOf(step.sowing) : lastYear;
      return new Occupation(catalog.speciesOf(sheet.cropId), firstYear, lastYear);
    });
}
