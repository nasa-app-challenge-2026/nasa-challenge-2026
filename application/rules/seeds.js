/**
 * The farmer's seed reserve (`farm.seeds`, step 1 block B): the list of seeds he
 * owns, without quantities, and the mode: "preferer" (default, the reserve counts
 * in the score) or "uniquement" (only the reserve is proposed).
 */
import { SEED_IDS, SHEETS } from '../../data/reference/crops.js';

export const DEFAULT_RESERVE_MODE = 'preferer';

/** Seeds implied by what the farm grows now: crops in place and in the current rotations. */
export function deriveSeeds(farmInput) {
  const owned = new Set();
  for (const s of farmInput.sections ?? []) {
    for (const id of [s.currentCrop, ...(s.currentRotation ?? [])]) {
      const seed = SHEETS[id]?.seedId ?? id;
      if (SEED_IDS.includes(seed)) owned.add(seed);
    }
  }
  return { crops: SEED_IDS.filter((c) => owned.has(c)), mode: DEFAULT_RESERVE_MODE };
}

export function getSeeds(farmInput) {
  const s = farmInput.farm?.seeds;
  return s && Array.isArray(s.crops)
    ? { crops: s.crops, mode: s.mode ?? DEFAULT_RESERVE_MODE }
    : deriveSeeds(farmInput);
}

/** Add or remove a seed (keeps the catalogue order). Mutates `farmInput`. */
export function toggleSeed(farmInput, seedId) {
  const seeds = getSeeds(farmInput);
  const set = new Set(seeds.crops);
  if (set.has(seedId)) set.delete(seedId);
  else set.add(seedId);
  farmInput.farm.seeds = { ...seeds, crops: SEED_IDS.filter((c) => set.has(c)) };
}

/** Add seeds to the reserve. Mutates `farmInput`. */
export function addSeeds(farmInput, seedIds) {
  const seeds = getSeeds(farmInput);
  const set = new Set([...seeds.crops, ...seedIds]);
  farmInput.farm.seeds = { ...seeds, crops: SEED_IDS.filter((c) => set.has(c)) };
}

export function setReserveMode(farmInput, mode) {
  farmInput.farm.seeds = { ...getSeeds(farmInput), mode };
}
