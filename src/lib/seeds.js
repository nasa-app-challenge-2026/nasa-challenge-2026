/**
 * The farmer's seed reserve (`farm.seeds`): which main crops and winter covers
 * they can sow. The engine builds its proposals from it; the farmer can still
 * pick anything by hand (the UI then flags the missing seeds).
 *
 * Shape (contract): { crops: CropId[], covers: CoverId[] }.
 */
import { CROPS, CROP_IDS, COVERS } from '../data/crops.js';
import { toSlots } from './rotation.js';

/** Seeds implied by what the farm already grows: current crops + crops in the rotations. */
export function deriveSeeds(farmInput) {
  const crops = new Set();
  const covers = new Set();
  for (const s of farmInput.sections ?? []) {
    if (CROPS[s.currentCrop]) crops.add(s.currentCrop);
    for (const slot of toSlots(s.rotation ?? [])) {
      if (CROPS[slot.crop]) crops.add(slot.crop);
      if (COVERS[slot.cover]) covers.add(slot.cover);
    }
  }
  return { crops: CROP_IDS.filter((c) => crops.has(c)), covers: [...covers] };
}

/** The reserve, or a derived one for farms saved before seeds existed. */
export function getSeeds(farmInput) {
  const s = farmInput.farm?.seeds;
  return s && Array.isArray(s.crops)
    ? { crops: s.crops, covers: s.covers ?? [] }
    : deriveSeeds(farmInput);
}

export const hasSeed = (farmInput, crop) => getSeeds(farmInput).crops.includes(crop);

/** Crops of a rotation that are not in the reserve, in catalogue order. */
export function missingSeeds(farmInput, rotation) {
  const have = new Set(getSeeds(farmInput).crops);
  const used = new Set(
    toSlots(rotation)
      .map((s) => s.crop)
      .filter(Boolean),
  );
  return CROP_IDS.filter((c) => used.has(c) && !have.has(c));
}

/** Add crops to the reserve (mutates `farmInput`, keeps catalogue order). */
export function addSeeds(farmInput, cropIds) {
  const seeds = getSeeds(farmInput);
  const set = new Set([...seeds.crops, ...cropIds.filter((c) => CROPS[c])]);
  farmInput.farm.seeds = { crops: CROP_IDS.filter((c) => set.has(c)), covers: [...seeds.covers] };
}
