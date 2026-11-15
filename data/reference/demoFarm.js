/**
 * Demo farm used on first launch and in tests: four sections near Saint-Hyacinthe
 * (Montérégie), drawn on a 600 m × 600 m block (36 ha) of real cropland: the AAFC Annual Crop
 * Inventory sees maize, soybean and wheat on all of it every year from 2019 to 2025 (the first
 * outline, 2.4 km north, was on the town: no soil in SoilGrids, no crop in the maps). The
 * shape is exactly the FarmInput v2 of docs/ALGO_CONTRACT.md.
 *
 * Sections A and B are the two fields of the algorithm's worked example
 * (field_shift.py v5.1): corn harvested in October 2026 in a corn → soybean
 * rotation, and alfalfa ending in September 2027 in alfalfa ×3 → corn → soybean.
 */
export const DEMO_FARM = {
  version: '2.0',
  farm: {
    id: 'demo',
    name: 'Ferme du rang Saint-Pierre',
    type: 'grandes-cultures',
    location: { lat: 45.6077, lon: -72.94395, label: 'Saint-Hyacinthe, QC' },
    boundary: [
      [45.6104, -72.9478],
      [45.6104, -72.9401],
      [45.605, -72.9401],
      [45.605, -72.9478],
    ],
    time: { cycleYears: 4, frequencyMonths: 12, horizonYears: 12 },
    priorities: ['erosion', 'rendement', 'azote', 'reserve', 'matiere_org', 'marche'],
    livestock: false,
    missingEquipment: [],
    seeds: { crops: ['mais', 'soya', 'ble-automne', 'seigle'], mode: 'preferer' },
  },
  sections: [
    {
      id: 'A',
      areaHa: 12,
      note: 'côté route',
      polygon: [
        [45.6104, -72.9478],
        [45.6104, -72.94266],
        [45.6077, -72.94266],
        [45.6077, -72.9478],
      ],
      currentCrop: 'mais',
      currentHarvest: '2026-10',
      history: [
        { year: 2023, crop: 'soya' },
        { year: 2024, crop: 'mais' },
        { year: 2025, crop: 'soya' },
      ],
      currentRotation: ['mais', 'soya'],
      rotationPosition: 0,
      diseases: [],
      irrigated: false,
      soilTest: null,
    },
    {
      id: 'B',
      areaHa: 8,
      note: 'sol plus sableux',
      polygon: [
        [45.6077, -72.94352],
        [45.6077, -72.9401],
        [45.605, -72.9401],
        [45.605, -72.94352],
      ],
      currentCrop: 'luzerne-3',
      currentHarvest: '2027-09',
      history: [
        { year: 2023, crop: 'soya' },
        { year: 2024, crop: 'mais' },
      ],
      currentRotation: ['luzerne-3', 'mais', 'soya'],
      rotationPosition: 0,
      diseases: [],
      irrigated: false,
      soilTest: null,
    },
    {
      id: 'C',
      areaHa: 10,
      note: 'près du ruisseau',
      polygon: [
        [45.6077, -72.9478],
        [45.6077, -72.94352],
        [45.605, -72.94352],
        [45.605, -72.9478],
      ],
      currentCrop: 'soya',
      currentHarvest: '2026-09',
      history: [
        { year: 2023, crop: 'soya' },
        { year: 2024, crop: 'mais' },
        { year: 2025, crop: 'ble-automne' },
      ],
      currentRotation: ['mais', 'soya', 'ble-automne'],
      rotationPosition: 1,
      diseases: [],
      irrigated: false,
      soilTest: null,
    },
    {
      id: 'D',
      areaHa: 6,
      note: 'derrière la grange',
      polygon: [
        [45.6104, -72.94266],
        [45.6104, -72.9401],
        [45.6077, -72.9401],
        [45.6077, -72.94266],
      ],
      currentCrop: 'ble-automne',
      currentHarvest: '2026-07',
      history: [
        { year: 2023, crop: 'mais' },
        { year: 2024, crop: 'soya' },
        { year: 2025, crop: 'pomme-de-terre' },
      ],
      currentRotation: ['mais', 'soya', 'ble-automne'],
      rotationPosition: 2,
      diseases: [],
      irrigated: false,
      soilTest: null,
    },
  ],
};
