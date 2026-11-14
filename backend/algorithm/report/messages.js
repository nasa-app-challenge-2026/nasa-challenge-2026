/**
 * French messages of the plan, built from the structured results of the algorithm.
 * Kept apart so that the algorithm returns data and the wording lives in one place.
 */
import { CROPS, SHEETS, nameOf } from '../../../data/reference/crops.js';
import { SOIL_DISEASES } from '../../../data/reference/returnDelays.js';
import { CROP_DELAYS } from '../../../data/reference/returnDelays.js';
import { RULE_KIND } from '../delays/ReturnDelayRules.js';

const cropName = (id) => CROPS[id]?.name ?? nameOf(id);
const diseaseName = (id) => SOIL_DISEASES[id]?.name ?? id;

/** "Soya après Soya", "même famille (Fabacées) : Luzerne après Soya"… */
export function ruleReasonText(reason) {
  const pair = `${cropName(reason.next)} après ${cropName(reason.previous)}`;
  if (reason.kind === RULE_KIND.SAME_FAMILY) return `même famille (${reason.family}) : ${pair}`;
  if (reason.kind === RULE_KIND.DISEASE) return `${diseaseName(reason.disease)} présente : ${pair}`;
  return pair;
}

/** "Soya après Soya : 2025 puis 2027, 1 an(s) sans, minimum 2" */
export const violationText = (v) =>
  `${ruleReasonText(v.reason)} : ${v.from.year} puis ${v.to.year}, ${v.yearsWithout} an(s) sans, minimum ${v.minimum}`;

/** Warning about a soil disease shared by two crops of different families. */
export const sharedDiseaseText = (w) =>
  `${cropName(w.next)} ${w.yearsWithout} an(s) après ${cropName(w.previous)} : tous deux hôtes de la ` +
  `${diseaseName(w.disease)} (${w.advised} ans sans hôte conseillés si elle apparaît).`;

/** Why a crop cannot come back every cycle. */
export function impossibleText(sheetId, { required, possible, occupiedYears }, cycleYears) {
  const sheet = SHEETS[sheetId];
  const perennial = CROP_DELAYS[sheet.cropId]?.perennial;
  return (
    `${sheet.name} demande ${required} an(s) sans ${cropName(sheet.cropId).toLowerCase()} entre deux ` +
    `${perennial ? 'peuplements' : 'récoltes'} ; un cycle de ${cycleYears} ans n’en laisse que ${possible}. ` +
    `Il faudrait un cycle d’au moins ${required + occupiedYears} ans.`
  );
}

/** "Blé d’automne → Sarrasin" (a succession whose precrop value is unknown). */
export const successionText = ([previous, next]) => `${cropName(previous)} → ${cropName(next)}`;

export { cropName, diseaseName };
