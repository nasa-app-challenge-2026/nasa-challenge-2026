/**
 * Farms saved by an older version of the app (contract 1.0: one rotation edited by
 * hand per section, offsets, covers) are brought to the FarmInput 2.0: the drawing,
 * the areas and the crops in place are kept; the old rotation becomes the current
 * rotation (the reference the algorithm compares with).
 */
import { DEMO_FARM } from '../../data/reference/demoFarm.js';
import { SHEETS } from '../../data/reference/crops.js';
import { deriveSeeds } from '../rules/seeds.js';

export const CURRENT_VERSION = '2.0';

/** Crops of contract 1.0 → sheets of the algorithm. */
const OLD_CROPS = {
  mais: 'mais',
  soya: 'soya',
  ble: 'ble-automne',
  orge: 'orge',
  patate: 'pomme-de-terre',
  luzerne: 'luzerne-3',
};
const DEFAULT_HARVEST_MONTH = '10';

function migrateSection(s, currentYear) {
  const currentCrop = OLD_CROPS[s.currentCrop] ?? null;
  const rotation = (s.rotation ?? []).map((e) => OLD_CROPS[e.crop]).filter((id) => SHEETS[id]);
  const position = Math.max(0, rotation.indexOf(currentCrop));
  return {
    id: s.id,
    areaHa: s.areaHa,
    note: s.note,
    polygon: s.polygon ?? [],
    currentCrop,
    currentHarvest: currentCrop ? `${currentYear}-${DEFAULT_HARVEST_MONTH}` : null,
    history: [],
    currentRotation: rotation,
    rotationPosition: position,
    diseases: [],
    irrigated: false,
    soilTest: null,
  };
}

export function migrateFarm(saved, currentYear = new Date().getFullYear()) {
  if (saved?.version === CURRENT_VERSION) return structuredClone(saved);
  const base = structuredClone(DEMO_FARM);
  const farm = {
    ...base,
    farm: {
      ...base.farm,
      ...(saved.farm?.id ? { id: saved.farm.id } : {}),
      name: saved.farm?.name ?? base.farm.name,
      location: saved.farm?.location ?? base.farm.location,
      boundary: saved.farm?.boundary ?? base.farm.boundary,
    },
    sections: (saved.sections ?? []).map((s) => migrateSection(s, currentYear)),
  };
  if (!farm.sections.length) farm.sections = base.sections;
  farm.farm.seeds = deriveSeeds(farm);
  if (!farm.farm.seeds.crops.length) farm.farm.seeds = base.farm.seeds;
  return farm;
}
