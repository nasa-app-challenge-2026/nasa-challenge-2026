/**
 * Demo farm used on first launch and in tests: four sections, three with a
 * 4-year cycle and one with a 3-year cycle (the "cas 2" discussed by the team).
 * The shape is exactly the FarmInput of docs/ALGO_CONTRACT.md.
 *
 * The outline is a 600 m × 600 m block (36 ha) near Saint-Hyacinthe, split in
 * four rectangles whose real areas match `areaHa` (see tests/geo.test.js).
 *
 * `seeds` is the farmer's seed reserve and `currentCrop` what grows on each
 * section now (2026): every first year respects its return delay.
 */
export const DEMO_FARM = {
  version: '1.0',
  farm: {
    id: 'demo',
    name: 'Ferme du rang Saint-Pierre',
    type: 'grandes-cultures',
    location: { lat: 45.6287, lon: -72.94815, label: 'Saint-Hyacinthe, QC' },
    boundary: [
      [45.6314, -72.952],
      [45.6314, -72.9443],
      [45.626, -72.9443],
      [45.626, -72.952],
    ],
    startYear: 2027,
    horizonYears: 12,
    priorities: ['revenu', 'resilience', 'sol', 'eau', 'travail'],
    sensors: false,
    seeds: { crops: ['mais', 'soya', 'ble', 'patate'], covers: ['seigle', 'trefle'] },
  },
  options: { stressYears: 1 },
  sections: [
    {
      id: 'A',
      currentCrop: 'mais',
      areaHa: 12,
      offset: 0,
      note: 'côté route',
      polygon: [
        [45.6314, -72.952],
        [45.6314, -72.94686],
        [45.6287, -72.94686],
        [45.6287, -72.952],
      ],
      rotation: [
        { crop: 'soya', years: 1, cover: null },
        { crop: 'ble', years: 1, cover: 'trefle' },
        { crop: 'mais', years: 1, cover: 'seigle' },
        { crop: 'patate', years: 1, cover: null },
      ],
    },
    {
      id: 'B',
      currentCrop: 'soya',
      areaHa: 8,
      offset: 0,
      note: 'sol plus sableux',
      polygon: [
        [45.6287, -72.94772],
        [45.6287, -72.9443],
        [45.626, -72.9443],
        [45.626, -72.94772],
      ],
      rotation: [
        { crop: 'mais', years: 1, cover: null },
        { crop: 'soya', years: 1, cover: null },
        { crop: 'ble', years: 1, cover: null },
      ],
    },
    {
      id: 'C',
      currentCrop: 'soya',
      areaHa: 10,
      offset: 0,
      note: 'près du ruisseau',
      polygon: [
        [45.6287, -72.952],
        [45.6287, -72.94772],
        [45.626, -72.94772],
        [45.626, -72.952],
      ],
      rotation: [
        { crop: 'ble', years: 1, cover: null },
        { crop: 'mais', years: 1, cover: null },
        { crop: 'soya', years: 1, cover: null },
        { crop: 'patate', years: 1, cover: null },
      ],
    },
    {
      id: 'D',
      currentCrop: 'ble',
      areaHa: 6,
      offset: 0,
      note: 'derrière la grange',
      polygon: [
        [45.6314, -72.94686],
        [45.6314, -72.9443],
        [45.6287, -72.9443],
        [45.6287, -72.94686],
      ],
      rotation: [
        { crop: 'patate', years: 1, cover: null },
        { crop: 'soya', years: 1, cover: null },
        { crop: 'ble', years: 1, cover: null },
        { crop: 'mais', years: 1, cover: null },
      ],
    },
  ],
};
