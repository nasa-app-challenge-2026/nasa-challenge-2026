/**
 * What the farmer told the app once for the whole farm (step 1): his ranking of
 * the criteria, livestock, missing equipment, and his seed reserve (a list of
 * seeds, without quantities) with its mode.
 */
import { weightsFromRanking } from '../../../application/rules/priorities.js';
import { SEED_IDS } from '../../../data/reference/crops.js';

export const RESERVE_PREFERRED = 'preferer';
export const RESERVE_ONLY = 'uniquement';
/** The cover crop the app sows automatically: needed in the reserve in "reserve only" mode. */
export const AUTOMATIC_COVER_SEED = 'seigle';

export class FarmerProfile {
  /**
   * @param {object} p
   * @param {string[]} p.ranking            criteria, most important first (may be partial)
   * @param {boolean} [p.livestock]
   * @param {string[]} [p.missingEquipment]
   * @param {Iterable<string>} [p.seeds]    seed ids owned
   * @param {string} [p.reserveMode]        RESERVE_PREFERRED or RESERVE_ONLY
   */
  constructor({
    ranking,
    livestock = false,
    missingEquipment = [],
    seeds = SEED_IDS,
    reserveMode = RESERVE_PREFERRED,
  }) {
    this.ranking = ranking;
    this.livestock = livestock;
    this.missingEquipment = missingEquipment;
    this.seeds = new Set(seeds);
    this.reserveMode = reserveMode;
    this.baseWeights = weightsFromRanking(ranking);
    Object.freeze(this);
  }

  /** Automatic rye covers: always, unless "reserve only" without rye seeds. */
  coversAllowed() {
    return this.reserveMode !== RESERVE_ONLY || this.seeds.has(AUTOMATIC_COVER_SEED);
  }
}
