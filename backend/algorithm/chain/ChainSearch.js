/**
 * Step 9b, the search: fill the positions one by one. At each position, every
 * candidate is tried after every partial chain; those that already break a hard
 * constraint are dropped, and the BEAM_WIDTH best partial chains are kept (beam
 * search). At the last position, the closure and the return delays over the whole
 * cycle are checked. The 3 best complete chains are returned.
 *
 * Hard constraints: calendar and climate (CropPlacer); every succession of sold
 * crops observed in the twins, the last one back to the first included; return
 * delays; never two fallow positions in a row; the first crop can be sown again
 * after the last harvest (closure); the first crop follows the crop in place.
 */
import { FALLOW_SHEET_ID, ROLE, SHEETS } from '../../../data/reference/crops.js';
import { BEAM_WIDTH, BEST_CHAINS } from '../config/scoring.js';
import { chainStep, isSold, lastHarvest, sheetIds, toOccupations } from './ChainStep.js';
import { placeCrop } from './CropPlacer.js';
import { scoreChain } from './ChainScorer.js';

/** Was this succession of sold crops observed in the twins? */
export function successionAllowed(previousSoldSheet, sheetId, evidence) {
  if (SHEETS[sheetId].role !== ROLE.SOLD || previousSoldSheet === null) return true;
  return evidence.isObserved(SHEETS[previousSoldSheet].cropId, SHEETS[sheetId].cropId);
}

/** Return delays of a chain, with the history (and the next cycle if `closed`). */
export const delaysRespected = (chain, ctx, closed) =>
  ctx.delays.isAllowed(toOccupations(chain, ctx.catalog), { closed });

/** Can the chain start again: its first crops placed again after its last harvest. */
export function closes(chain, ctx) {
  const sold = chain.filter(isSold).map((s) => s.sheetId);
  if (sold.length && !successionAllowed(sold[sold.length - 1], sold[0], ctx.evidence)) return false;
  let harvest = lastHarvest(chain);
  let previous = chain[chain.length - 1].sheetId;
  for (const step of chain) {
    const position = ctx.firstPosition + ctx.positions + step.firstPosition;
    const placed = placeCrop(step.sheetId, position, harvest, previous, ctx);
    if (!placed) return false;
    if (step.sheetId !== FALLOW_SHEET_ID) return true;
    harvest = placed.harvest;
    previous = step.sheetId;
  }
  return true;
}

/** Sort by descending score; equal scores keep their order. */
function bestFirst(chains, ctx, partial) {
  return chains
    .map((item) => ({ item, score: scoreChain(item.chain ?? item, ctx, { partial }).score }))
    .sort((a, b) => b.score - a.score)
    .map(({ item }) => item);
}

/**
 * @param {import('./CycleContext.js').CycleContext} ctx
 * @returns {ReturnType<typeof chainStep>[][]} up to BEST_CHAINS chains, best first
 */
export function bestChains(ctx, { beamWidth = BEAM_WIDTH, count = BEST_CHAINS } = {}) {
  const N = ctx.positions;
  let beam = [
    { chain: [], position: 0, harvest: ctx.entryHarvest, previousSold: ctx.entrySheetId },
  ];
  const complete = [];
  while (beam.length) {
    const next = [];
    for (const { chain, position, harvest, previousSold } of beam) {
      for (const sheetId of ctx.candidates) {
        const previousStep = chain[chain.length - 1];
        if (sheetId === FALLOW_SHEET_ID && previousStep?.sheetId === FALLOW_SHEET_ID) continue;
        if (!successionAllowed(previousSold, sheetId, ctx.evidence)) continue;
        const previous = previousStep?.sheetId ?? ctx.entrySheetId;
        const placed = placeCrop(sheetId, ctx.firstPosition + position, harvest, previous, ctx);
        if (!placed) continue;
        const last = placed.lastPosition - ctx.firstPosition;
        if (last >= N) continue; // goes beyond the cycle
        const extended = [
          ...chain,
          chainStep(sheetId, placed.sowing, placed.harvest, position, last),
        ];
        const sold = SHEETS[sheetId].role === ROLE.SOLD ? sheetId : previousSold;
        if (last === N - 1) {
          if (closes(extended, ctx) && delaysRespected(extended, ctx, true))
            complete.push(extended);
        } else if (delaysRespected(extended, ctx, false)) {
          next.push({
            chain: extended,
            position: last + 1,
            harvest: placed.harvest,
            previousSold: sold,
          });
        }
      }
    }
    beam = bestFirst(next, ctx, true).slice(0, beamWidth);
  }
  const unique = [];
  const seen = new Set();
  for (const chain of bestFirst(complete, ctx, false)) {
    const key = sheetIds(chain).join('|');
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(chain);
    if (unique.length === count) break;
  }
  return unique;
}
