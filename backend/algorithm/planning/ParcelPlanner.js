/**
 * Step 10: the plan of one field, cycle after cycle.
 *
 * Before the first cycle: the field becomes free when the crop in place is
 * harvested; cycle 1 starts at the next position. The history (crop in place and
 * previous years) checks the return delays from cycle 1. The reference is the
 * farmer's current rotation, continued on its own path and scored with the same
 * rules; it is never discarded (its broken delays become alerts).
 *
 * For each cycle, in order: years → climate and twins (steps 3 to 7) → risks and
 * weights (step 8) → the 3 best chains (9b) → keep or change. The chain in place
 * (the farmer's rotation in cycle 1, then the chain kept at the previous cycle) is
 * kept if it respects the return delays, its crops are still grown in the twins and
 * its score is at most 5 points below the best chain; otherwise the best chain
 * replaces it. The next cycle starts from the last harvest and the last sold crop
 * of the chosen chain, which joins the history.
 *
 * After the last cycle: robustness of each adopted chain (RobustnessAnalyzer).
 */
import { SHEETS } from '../../../data/reference/crops.js';
import { EPOCH_YEAR, MONTHS_PER_YEAR } from '../config/calendar.js';
import { KEEP_THRESHOLD_POINTS } from '../config/scoring.js';
import { CycleContext } from '../chain/CycleContext.js';
import { candidateSheets } from '../chain/CandidateSheets.js';
import { bestChains, delaysRespected } from '../chain/ChainSearch.js';
import { replayChain } from '../chain/ChainReplayer.js';
import { scoreChain } from '../chain/ChainScorer.js';
import {
  isFallow,
  isSold,
  lastHarvest,
  lastSoldSheet,
  sheetIds,
  toOccupations,
} from '../chain/ChainStep.js';
import { fieldHistory } from '../delays/FieldHistory.js';
import { defaultDelayCatalog } from '../delays/ReturnDelayCatalog.js';
import { MonthTime } from '../time/MonthTime.js';
import { weightsForCycle } from './CriteriaWeights.js';
import { addRobustness } from './RobustnessAnalyzer.js';
import { DECISION } from './decisions.js';

export { DECISION };

/** How far back the reference rotation may need to be continued. */
const REFERENCE_LENGTH_FACTOR = 3;

/** A scored chain, ready for the plan. */
const scored = (chain, ctx) => (chain ? { chain, ...scoreChain(chain, ctx) } : null);

export class ParcelPlanner {
  /**
   * @param {object} p
   * @param {import('../../../application/rules/timeSettings.js').TimeSettings} p.time
   * @param {import('./FarmerProfile.js').FarmerProfile} p.farmer
   * @param {{ cycleData: (firstYear: number, lastYear: number) =>
   *   { climate: import('../climate/CycleClimate.js').CycleClimate,
   *     evidence: import('../twins/TwinEvidence.js').TwinEvidence } }} p.data steps 3 to 7
   * @param {number} p.today absolute month the app is used
   */
  constructor({
    time,
    farmer,
    data,
    today,
    keepThreshold = KEEP_THRESHOLD_POINTS,
    catalog = defaultDelayCatalog,
  }) {
    Object.assign(this, { time, farmer, data, today, keepThreshold, catalog });
  }

  /** @param {import('./Parcel.js').Parcel} parcel */
  plan(parcel) {
    const { time } = this;
    const freeAt = parcel.inPlaceHarvest ?? this.today;
    const firstPosition = Math.floor((freeAt - time.positionStartMonth) / time.frequencyMonths) + 1;
    const history = fieldHistory(
      { inPlace: this.#inPlaceCrop(parcel), freeYear: MonthTime.yearOf(freeAt), past: parcel.past },
      this.catalog,
    );
    const state = {
      entryHarvest: freeAt,
      entrySheetId: parcel.inPlaceSheetId,
      history,
      inPlace: null,
    };
    const reference = {
      sequence: parcel.referenceSequence(
        REFERENCE_LENGTH_FACTOR * time.positionsPerCycle * time.cycleCount,
      ),
      index: 0,
      entryHarvest: freeAt,
      entrySheetId: parcel.inPlaceSheetId,
      history,
    };
    const cycles = [];
    for (let k = 0; k < time.cycleCount; k++) {
      const cycle = this.#planCycle(
        parcel,
        k,
        firstPosition + k * time.positionsPerCycle,
        state,
        reference,
      );
      cycles.push(cycle);
      if (cycle.decision === DECISION.NONE) break; // nothing feasible: the next cycles have no start
    }
    addRobustness(cycles);
    return { parcelId: parcel.id, freeAt, history, cycles };
  }

  #inPlaceCrop(parcel) {
    if (!parcel.inPlace || isFallow({ sheetId: parcel.inPlace })) return null;
    const sheet = SHEETS[parcel.inPlace];
    return sheet
      ? { cropId: sheet.cropId, productionYears: sheet.productionYears }
      : { cropId: parcel.inPlace };
  }

  #planCycle(parcel, k, firstPosition, state, reference) {
    const { time, farmer } = this;
    const firstYear =
      EPOCH_YEAR +
      Math.floor(
        (time.positionStartMonth + firstPosition * time.frequencyMonths) / MONTHS_PER_YEAR,
      );
    const years = [firstYear, firstYear + time.cycleYears - 1];
    const { climate, evidence } = this.data.cycleData(...years);
    const risks = parcel.diagnostic.risksFor(climate);
    const { candidates, removed } = candidateSheets({
      evidence,
      farmer,
      frequencyMonths: time.frequencyMonths,
      cycleYears: time.cycleYears,
      diseases: parcel.diseases,
      catalog: this.catalog,
    });
    const ctx = new CycleContext({
      time,
      firstPosition,
      entryHarvest: state.entryHarvest,
      entrySheetId: state.entrySheetId,
      climate,
      evidence,
      weights: weightsForCycle(farmer.baseWeights, risks, farmer.livestock),
      reserve: k === 0 ? farmer.seeds : null,
      history: state.history,
      diseases: parcel.diseases,
      candidates,
      coversEnabled: time.frequencyMonths >= MONTHS_PER_YEAR && farmer.coversAllowed(),
      catalog: this.catalog,
    });

    const {
      chain: referenceChain,
      ctx: referenceCtx,
      alerts,
    } = this.#continueReference(ctx, reference);
    const top = bestChains(ctx);
    const best = top[0] ?? null;
    let kept = k === 0 ? referenceChain : this.#replayInPlace(state.inPlace, ctx);
    if (kept && !delaysRespected(kept, ctx, true)) kept = null;
    const keep =
      kept &&
      (!best || scoreChain(best, ctx).score - scoreChain(kept, ctx).score <= this.keepThreshold);
    const choice = keep ? kept : best;
    const cycle = {
      index: k + 1,
      years,
      climate,
      evidence,
      risks,
      weights: ctx.weights,
      removed,
      decision: choice ? (keep ? DECISION.KEEP : DECISION.CHANGE) : DECISION.NONE,
      chosen: scored(choice, ctx),
      reference: scored(referenceChain, referenceCtx),
      referenceAlerts: alerts,
      alternatives: top
        .filter((c) => !choice || sheetIds(c).join() !== sheetIds(choice).join())
        .slice(0, 2)
        .map((c) => scored(c, ctx)),
      context: ctx,
    };
    if (choice) {
      state.inPlace = choice;
      state.history = [...state.history, ...toOccupations(choice, this.catalog)];
      state.entryHarvest = lastHarvest(choice);
      state.entrySheetId = lastSoldSheet(choice, state.entrySheetId);
    }
    return cycle;
  }

  /** The farmer's rotation goes on along its own path; its delay problems become alerts. */
  #continueReference(ctx, reference) {
    const referenceCtx = ctx.with({
      entryHarvest: reference.entryHarvest,
      entrySheetId: reference.entrySheetId,
      history: reference.history,
    });
    const chain = replayChain(reference.sequence.slice(reference.index), referenceCtx, {
      fillGaps: true,
    });
    if (!chain) return { chain: null, ctx: referenceCtx, alerts: [] };
    const occupations = toOccupations(chain, this.catalog);
    const alerts = referenceCtx.delays.violations(occupations, { closed: true });
    reference.history = [...reference.history, ...occupations];
    reference.index += chain.filter((s) => !isFallow(s)).length;
    reference.entryHarvest = lastHarvest(chain);
    reference.entrySheetId = lastSoldSheet(chain, reference.entrySheetId);
    return { chain, ctx: referenceCtx, alerts };
  }

  /** The chain kept at the previous cycle, placed again if its crops are still grown in the twins. */
  #replayInPlace(chain, ctx) {
    const stillGrown = chain.every(
      (s) => !isSold(s) || ctx.evidence.isGrown(SHEETS[s.sheetId].cropId),
    );
    return stillGrown ? replayChain(sheetIds(chain), ctx) : null;
  }
}
