/**
 * Everything step 9b needs to know about one cycle of one field: the time layout,
 * where the field starts (last harvest, last sold crop, history), the climate of
 * the cycle, the twin evidence, the weights and the farmer's constraints.
 */
import { SHEETS } from '../../../data/reference/crops.js';
import { MONTHS_PER_YEAR } from '../config/calendar.js';
import { ReturnDelayChecker } from '../delays/ReturnDelayChecker.js';
import { defaultDelayCatalog } from '../delays/ReturnDelayCatalog.js';

export class CycleContext {
  /**
   * @param {object} p
   * @param {import('../../../application/rules/timeSettings.js').TimeSettings} p.time
   * @param {number} p.firstPosition   absolute index of the cycle's first position
   * @param {number} p.entryHarvest    when the field becomes free (absolute month)
   * @param {string|null} p.entrySheetId last sold sheet before the cycle
   * @param {import('../climate/CycleClimate.js').CycleClimate} p.climate
   * @param {import('../twins/TwinEvidence.js').TwinEvidence} p.evidence
   * @param {Record<string, number>} p.weights criteria weights for this cycle
   * @param {Set<string>|null} p.reserve seeds owned (counted in the 1st cycle only), else null
   * @param {import('../delays/Occupation.js').Occupation[]} p.history what grew before
   * @param {string[]} p.diseases declared soil diseases
   * @param {string[]} p.candidates sheets that may fill a position
   * @param {boolean} p.coversEnabled rye is sown automatically between two crops
   */
  constructor(p) {
    Object.assign(this, p);
    this.catalog = p.catalog ?? defaultDelayCatalog;
    this.entryCropId = p.entrySheetId ? SHEETS[p.entrySheetId].cropId : null;
    this.delays = new ReturnDelayChecker({
      cycleYears: p.time.cycleYears,
      history: p.history,
      diseases: p.diseases,
      catalog: this.catalog,
    });
    Object.freeze(this);
  }

  /** Same context with some fields changed. */
  with(changes) {
    const { entryCropId: _crop, delays: _delays, ...fields } = this;
    return new CycleContext({ ...fields, ...changes });
  }

  get positions() {
    return this.time.positionsPerCycle;
  }

  get cycleMonths() {
    return this.time.cycleYears * MONTHS_PER_YEAR;
  }
}
