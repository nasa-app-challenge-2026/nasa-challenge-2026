/**
 * A field (parcelle) as the algorithm sees it (step 1, block A): the crop in place
 * and when it is harvested (or ends, for a perennial), the crops of the previous
 * years, the rotation the farmer started and where he is in it, the soil diseases
 * he knows, irrigation and the satellite measures of step 8.
 */
import { FALLOW_SHEET_ID, ROLE, SHEETS } from '../../../data/reference/crops.js';

export class Parcel {
  /**
   * @param {object} p
   * @param {string} p.id
   * @param {string|null} [p.inPlace]       crop in place: a sheet id (or another crop id), null = free
   * @param {number|null} [p.inPlaceHarvest] absolute month of its harvest / end, null = free now
   * @param {{ year: number, cropId: string }[]} [p.past] crops of the previous years
   * @param {string[]} [p.currentRotation]  sheet ids of the rotation started
   * @param {number} [p.rotationPosition]   index of the crop in place in it
   * @param {string[]} [p.diseases]         declared soil diseases
   * @param {import('../diagnostic/ParcelDiagnostic.js').ParcelDiagnostic} p.diagnostic
   */
  constructor({
    id,
    inPlace = null,
    inPlaceHarvest = null,
    past = [],
    currentRotation = [],
    rotationPosition = 0,
    diseases = [],
    diagnostic,
  }) {
    Object.assign(this, {
      id,
      inPlace,
      inPlaceHarvest,
      past,
      currentRotation,
      rotationPosition,
      diseases,
      diagnostic,
    });
    Object.freeze(this);
  }

  /** The crop in place as a sold sheet (the entry of the first cycle), or null. */
  get inPlaceSheetId() {
    const sheet = SHEETS[this.inPlace];
    return sheet && sheet.role === ROLE.SOLD ? sheet.id : null;
  }

  /**
   * The farmer's current rotation continued from the crop after the one in place:
   * the reference the plan is compared with. Without a rotation, the crop in place
   * is repeated (and the app says so).
   */
  referenceSequence(length) {
    const rotation = this.currentRotation.length
      ? this.currentRotation
      : [this.inPlaceSheetId ?? FALLOW_SHEET_ID];
    return Array.from(
      { length },
      (_, i) => rotation[(this.rotationPosition + 1 + i) % rotation.length],
    );
  }

  get repeatsInPlaceCrop() {
    return this.currentRotation.length === 0;
  }
}
