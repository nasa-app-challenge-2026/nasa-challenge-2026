/**
 * Crops and crop sheets as the screens need them: names, colours, textures and the little
 * structure the forms use. The agronomy of a sheet (sowing window, degree-days, harvest date,
 * hardiness, values for the criteria) lives in the algorithm server:
 * backend/server/field_shift/reference/crops.py. The ids are the contract, and
 * tests/contract.test.js checks that both sides know the same ones.
 *
 * Two levels:
 *   - a CROP is what grows in a field (history, seed reserve, crops grown in the twins);
 *   - a SHEET is one way to grow a crop in a rotation chain (alfalfa kept 2 or 3 years, soybean
 *     sown after winter wheat…): the algorithm builds its chains from sheets.
 */

import { translateText } from '../i18n/index.js';

/** `texture` = id of the SVG field pattern (frontend/ui/textures.js). */
export const CROPS = {
  mais: { id: 'mais', name: 'Maïs', color: '#F2C14E', texture: 'mais' },
  soya: { id: 'soya', name: 'Soya', color: '#9CC27A', texture: 'soya' },
  'soya-2e': { id: 'soya-2e', name: 'Soya (2e culture)', color: '#B7D69A', texture: 'soya' },
  'ble-automne': { id: 'ble-automne', name: 'Blé d’automne', color: '#DDB07F', texture: 'ble' },
  orge: { id: 'orge', name: 'Orge', color: '#BFD6E6', texture: 'orge' },
  canola: { id: 'canola', name: 'Canola', color: '#E9D96B', texture: 'canola' },
  sarrasin: { id: 'sarrasin', name: 'Sarrasin', color: '#E3B8C4', texture: 'sarrasin' },
  luzerne: { id: 'luzerne', name: 'Luzerne', color: '#7FC0B2', texture: 'luzerne' },
  foin: { id: 'foin', name: 'Foin', color: '#A9C98A', texture: 'foin' },
  seigle: { id: 'seigle', name: 'Seigle', color: '#C9B98F', texture: 'seigle' },
  jachere: { id: 'jachere', name: 'Jachère', color: '#D9CBB5', texture: 'sol' },
  avoine: { id: 'avoine', name: 'Avoine', color: '#D8D2A0', texture: 'orge' },
  'haricot-sec': { id: 'haricot-sec', name: 'Haricot sec', color: '#B9C98F', texture: 'soya' },
  pois: { id: 'pois', name: 'Pois', color: '#A6CF8E', texture: 'soya' },
  chou: { id: 'chou', name: 'Chou', color: '#9FC7B8', texture: 'legume' },
  navet: { id: 'navet', name: 'Navet', color: '#C7B3D6', texture: 'legume' },
  radis: { id: 'radis', name: 'Radis', color: '#E0A9B5', texture: 'legume' },
  'pomme-de-terre': {
    id: 'pomme-de-terre',
    name: 'Pomme de terre',
    color: '#C3A3D6',
    texture: 'patate',
  },
  tomate: { id: 'tomate', name: 'Tomate', color: '#E59A8A', texture: 'legume' },
  carotte: { id: 'carotte', name: 'Carotte', color: '#EDB27A', texture: 'legume' },
  celeri: { id: 'celeri', name: 'Céleri', color: '#B3D69E', texture: 'legume' },
  oignon: { id: 'oignon', name: 'Oignon', color: '#E7CFA6', texture: 'legume' },
  laitue: { id: 'laitue', name: 'Laitue', color: '#BFE0A0', texture: 'legume' },
  epinard: { id: 'epinard', name: 'Épinard', color: '#8DBF86', texture: 'legume' },
  betterave: { id: 'betterave', name: 'Betterave', color: '#C98B9E', texture: 'legume' },
  courge: { id: 'courge', name: 'Courge', color: '#F0C27B', texture: 'legume' },
};

/**
 * A small picture of each crop, to recognise it at a glance in a rotation (the wheel, the strips).
 * The three small grains share the ear: their colour and their name tell them apart.
 */
const DEFAULT_SYMBOL = '🌱';
const SYMBOLS = {
  mais: '🌽',
  soya: '🌱',
  'soya-2e': '🌱',
  'ble-automne': '🌾',
  orge: '🌾',
  seigle: '🌾',
  avoine: '🌾',
  canola: '🌼',
  sarrasin: '🌸',
  luzerne: '🍀',
  foin: '🌿',
  jachere: '💤',
};

/** Seeds a farmer can own (the crops that have a sheet), in the order the reserve shows them. */
export const SEED_IDS = [
  'mais',
  'soya',
  'ble-automne',
  'orge',
  'canola',
  'sarrasin',
  'luzerne',
  'foin',
  'seigle',
];

/** Other crops the farmer may have grown (they count for the return delays only). */
export const OTHER_CROP_IDS = [
  'avoine',
  'haricot-sec',
  'pois',
  'pomme-de-terre',
  'carotte',
  'chou',
  'navet',
  'radis',
  'tomate',
  'celeri',
  'oignon',
  'laitue',
  'epinard',
  'betterave',
  'courge',
];

/** Role of a sheet in a chain. */
export const ROLE = { SOLD: 'vente', COVER: 'couvert', FALLOW: 'jachere' };

/** Equipment a farmer may lack: without it, no alfalfa and no hay. */
export const EQUIPMENT = { fourragere: { id: 'fourragere', name: 'Récolteuse fourragère' } };

/** Month (1–12) a crop is usually harvested, to prefill the harvest month of a new field. */
export const DEFAULT_HARVEST_MONTH = 10;

const sheet = (fields) => ({
  role: ROLE.SOLD,
  productionYears: 0,
  usualHarvestMonth: DEFAULT_HARVEST_MONTH,
  ...fields,
  seedId: fields.seedId ?? fields.cropId,
});

/**
 * The sheets: `productionYears` = years a planting holds the field (alfalfa ×3 = 3);
 * `seedId` = the seed it is sown with.
 */
export const CROP_SHEETS = [
  sheet({ id: 'mais', name: 'Maïs', cropId: 'mais' }),
  sheet({ id: 'soya', name: 'Soya', cropId: 'soya' }),
  sheet({ id: 'soya-2e', name: 'Soya (2e culture)', cropId: 'soya-2e', seedId: 'soya' }),
  sheet({ id: 'ble-automne', name: 'Blé d’automne', cropId: 'ble-automne', usualHarvestMonth: 7 }),
  sheet({ id: 'orge', name: 'Orge', cropId: 'orge' }),
  sheet({ id: 'canola', name: 'Canola', cropId: 'canola' }),
  sheet({ id: 'sarrasin', name: 'Sarrasin', cropId: 'sarrasin' }),
  sheet({
    id: 'luzerne-2',
    name: 'Luzerne ×2',
    cropId: 'luzerne',
    productionYears: 2,
    usualHarvestMonth: 9,
  }),
  sheet({
    id: 'luzerne-3',
    name: 'Luzerne ×3',
    cropId: 'luzerne',
    productionYears: 3,
    usualHarvestMonth: 9,
  }),
  sheet({
    id: 'foin-2',
    name: 'Foin ×2',
    cropId: 'foin',
    productionYears: 2,
    usualHarvestMonth: 9,
  }),
  sheet({
    id: 'foin-3',
    name: 'Foin ×3',
    cropId: 'foin',
    productionYears: 3,
    usualHarvestMonth: 9,
  }),
  sheet({ id: 'seigle-couvert', name: 'Seigle (couvert)', cropId: 'seigle', role: ROLE.COVER }),
  sheet({ id: 'jachere', name: 'Jachère', cropId: 'jachere', role: ROLE.FALLOW }),
];

export const SHEETS = Object.fromEntries(CROP_SHEETS.map((s) => [s.id, s]));
export const FALLOW_SHEET_ID = 'jachere';

/** Sheets of crops that are sold: the ones a farmer can have in place or in his rotation. */
export const SOLD_SHEET_IDS = CROP_SHEETS.filter((s) => s.role === ROLE.SOLD).map((s) => s.id);

/** Display helpers that work for a sheet id as well as a crop id. */
export const cropOf = (id) => CROPS[SHEETS[id]?.cropId ?? id] ?? null;
export const nameOf = (id) => translateText(SHEETS[id]?.name ?? CROPS[id]?.name ?? id ?? '—');
export const colorOf = (id) => cropOf(id)?.color ?? '#E5E9E0';
export const textureOf = (id) => cropOf(id)?.texture ?? 'sol';
export const symbolOf = (id) => SYMBOLS[cropOf(id)?.id] ?? DEFAULT_SYMBOL;
