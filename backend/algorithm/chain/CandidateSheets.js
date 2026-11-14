/**
 * Step 9b, the candidate crops of a cycle:
 *   - a sold crop is a candidate only if it is grown in the twins of the cycle;
 *   - a crop that needs equipment the farmer does not have is removed;
 *   - in "reserve only" mode, only the seeds of the reserve (plus fallow);
 *   - with one crop a year, rye is not a candidate: it is placed automatically
 *     between two crops (CoverCropPlanner);
 *   - a crop whose minimum return delay does not fit in the cycle is removed, with
 *     a message (impossibleCrops).
 */
import { CROP_SHEETS, ROLE } from '../../../data/reference/crops.js';
import { MONTHS_PER_YEAR } from '../config/calendar.js';
import { impossibleCrops } from '../delays/ReturnDelayChecker.js';
import { RESERVE_ONLY } from '../planning/FarmerProfile.js';

/**
 * @param {object} p
 * @param {import('../twins/TwinEvidence.js').TwinEvidence} p.evidence
 * @param {import('../planning/FarmerProfile.js').FarmerProfile} p.farmer
 * @param {number} p.frequencyMonths
 * @param {number} p.cycleYears
 * @param {string[]} p.diseases declared soil diseases
 * @returns {{ candidates: string[], removed: Map<string, object> }} sheet ids, in sheet order
 */
export function candidateSheets({
  evidence,
  farmer,
  frequencyMonths,
  cycleYears,
  diseases,
  catalog,
}) {
  const allowed = CROP_SHEETS.filter((sheet) => {
    if (sheet.role === ROLE.COVER && frequencyMonths >= MONTHS_PER_YEAR) return false;
    if (sheet.role === ROLE.SOLD && !evidence.isGrown(sheet.cropId)) return false;
    if (sheet.equipment && farmer.missingEquipment.includes(sheet.equipment)) return false;
    if (
      farmer.reserveMode === RESERVE_ONLY &&
      sheet.role !== ROLE.FALLOW &&
      !farmer.seeds.has(sheet.seedId)
    )
      return false;
    return true;
  });
  const removed = impossibleCrops(
    cycleYears,
    allowed.filter((s) => s.role === ROLE.SOLD),
    diseases,
    catalog,
  );
  return { candidates: allowed.filter((s) => !removed.has(s.id)).map((s) => s.id), removed };
}
