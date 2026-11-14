/**
 * The three reference cases agreed by the team (sections A to D, 12 years).
 * Used to generate contract/examples/*.json and by the tests.
 */
import { DEMO_FARM } from '../src/data/demoFarm.js';

const R4 = [
  { crop: 'soya', years: 1, cover: null },
  { crop: 'ble', years: 1, cover: null },
  { crop: 'mais', years: 1, cover: null },
  { crop: 'patate', years: 1, cover: null },
];
const R3 = [
  { crop: 'mais', years: 1, cover: null },
  { crop: 'soya', years: 1, cover: null },
  { crop: 'ble', years: 1, cover: null },
];
const R5 = [
  { crop: 'mais', years: 1, cover: null },
  { crop: 'soya', years: 1, cover: null },
  { crop: 'luzerne', years: 3, cover: null },
];

const section = (id, rotation, offset) => ({ id, areaHa: 10, offset, rotation });

function farm(name, sections) {
  return {
    version: '1.0',
    farm: { ...DEMO_FARM.farm, id: name, name },
    options: { stressYears: 1 },
    sections,
  };
}

export const CASES = {
  'cas1-meme-rotation-decalee': farm('Cas 1', [
    section('A', R4, 0),
    section('B', R4, 1),
    section('C', R4, 2),
    section('D', R4, 3),
  ]),
  'cas2-durees-differentes': farm('Cas 2', [
    section('A', R4, 0),
    section('B', R4, 1),
    section('C', R4, 2),
    section('D', R3, 0),
  ]),
  'cas3-luzerne-cycle-coupe': farm('Cas 3', [
    section('A', R3, 0),
    section('B', R3, 1),
    section('C', R3, 2),
    section('D', R5, 0),
  ]),
  'ferme-demo': structuredClone(DEMO_FARM),
};
