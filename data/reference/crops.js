/**
 * Crops known by the app, and the crop sheets of the algorithm (step 9b).
 *
 * Two levels:
 *   - CROPS: what grows in a field (display: name, colour, texture). The farmer's
 *     history, the seed reserve and the climate twins speak about crops.
 *   - CROP_SHEETS: one way to grow a crop inside a rotation chain (alfalfa kept
 *     2 or 3 years, soybean sown after winter wheat…), with its calendar and its
 *     values for the scoring criteria.
 *
 * VALUES ARE INDICATIVE (field_shift.py v5.1): they must be checked by an agronomist.
 */

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

/** Crops grown in the sheets below, in the order the seed reserve shows them. */
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

/** Equipment a sheet may need. */
export const EQUIPMENT = { fourragere: { id: 'fourragere', name: 'Récolteuse fourragère' } };

const sheet = (fields) => ({
  role: ROLE.SOLD,
  degreeDays: null,
  onlyAfter: null,
  harvestMonth: null,
  productionYears: 0,
  januaryMinimumC: null,
  frostSensitive: false,
  equipment: null,
  ...fields,
  seedId: fields.seedId ?? fields.cropId,
});

/**
 * Crop sheets (field_shift.py, CULTURES). Months are 0-based decimals in the
 * year (4.25 = early May). The ORDER MATTERS: the chain search tries the
 * candidates in this order and keeps the first one on ties.
 *
 *  sowingWindow     earliest and latest sowing month
 *  degreeDays       growing degree-days (base 10 °C) from sowing to maturity
 *  harvestMonth     fixed harvest / destruction month (winter crops, perennials)
 *  productionYears  perennials: years of production
 *  januaryMinimumC  coldest mean January minimum the crop survives
 *  onlyAfter        double crop: allowed only right after one of these sheets
 *  values           criteria values between 0 and 1 (indicative)
 */
export const CROP_SHEETS = [
  sheet({
    id: 'mais',
    name: 'Maïs',
    cropId: 'mais',
    sowingWindow: [4.25, 5.5],
    degreeDays: 1150,
    frostSensitive: true,
    values: { eau: 0.4, fourrage: 0.4, azote: 0.1, matiere_org: 0.5, marche: 0.9 },
  }),
  sheet({
    id: 'soya',
    name: 'Soya',
    cropId: 'soya',
    sowingWindow: [4.5, 5.75],
    degreeDays: 1000,
    frostSensitive: true,
    values: { eau: 0.5, fourrage: 0.1, azote: 0.7, matiere_org: 0.2, marche: 0.8 },
  }),
  sheet({
    id: 'soya-2e',
    name: 'Soya (2e culture)',
    cropId: 'soya-2e',
    seedId: 'soya',
    sowingWindow: [6.0, 7.0],
    degreeDays: 800,
    onlyAfter: ['ble-automne'],
    frostSensitive: true,
    values: { eau: 0.5, fourrage: 0.1, azote: 0.6, matiere_org: 0.2, marche: 0.75 },
  }),
  sheet({
    id: 'ble-automne',
    name: 'Blé d’automne',
    cropId: 'ble-automne',
    sowingWindow: [8.5, 9.75],
    harvestMonth: 6.65,
    januaryMinimumC: -16,
    values: { eau: 0.7, fourrage: 0.3, azote: 0.2, matiere_org: 0.6, marche: 0.7 },
  }),
  sheet({
    id: 'orge',
    name: 'Orge',
    cropId: 'orge',
    sowingWindow: [3.75, 4.75],
    degreeDays: 800,
    values: { eau: 0.6, fourrage: 0.4, azote: 0.2, matiere_org: 0.5, marche: 0.5 },
  }),
  sheet({
    id: 'canola',
    name: 'Canola',
    cropId: 'canola',
    sowingWindow: [4.25, 5.25],
    degreeDays: 900,
    values: { eau: 0.4, fourrage: 0.0, azote: 0.1, matiere_org: 0.3, marche: 0.7 },
  }),
  sheet({
    id: 'sarrasin',
    name: 'Sarrasin',
    cropId: 'sarrasin',
    sowingWindow: [5.5, 7.0],
    degreeDays: 600,
    frostSensitive: true,
    values: { eau: 0.6, fourrage: 0.0, azote: 0.2, matiere_org: 0.4, marche: 0.4 },
  }),
  sheet({
    id: 'luzerne-2',
    name: 'Luzerne ×2',
    cropId: 'luzerne',
    sowingWindow: [3.75, 5.0],
    harvestMonth: 8.75,
    productionYears: 2,
    januaryMinimumC: -22,
    equipment: 'fourragere',
    values: { eau: 0.6, fourrage: 1.0, azote: 1.0, matiere_org: 0.9, marche: 0.4 },
  }),
  sheet({
    id: 'luzerne-3',
    name: 'Luzerne ×3',
    cropId: 'luzerne',
    sowingWindow: [3.75, 5.0],
    harvestMonth: 8.75,
    productionYears: 3,
    januaryMinimumC: -22,
    equipment: 'fourragere',
    values: { eau: 0.6, fourrage: 1.0, azote: 1.0, matiere_org: 0.9, marche: 0.4 },
  }),
  sheet({
    id: 'foin-2',
    name: 'Foin ×2',
    cropId: 'foin',
    sowingWindow: [3.75, 5.0],
    harvestMonth: 8.75,
    productionYears: 2,
    januaryMinimumC: -28,
    equipment: 'fourragere',
    values: { eau: 0.7, fourrage: 1.0, azote: 0.6, matiere_org: 0.9, marche: 0.35 },
  }),
  sheet({
    id: 'foin-3',
    name: 'Foin ×3',
    cropId: 'foin',
    sowingWindow: [3.75, 5.0],
    harvestMonth: 8.75,
    productionYears: 3,
    januaryMinimumC: -28,
    equipment: 'fourragere',
    values: { eau: 0.7, fourrage: 1.0, azote: 0.6, matiere_org: 0.9, marche: 0.35 },
  }),
  sheet({
    id: 'seigle-couvert',
    name: 'Seigle (couvert)',
    cropId: 'seigle',
    role: ROLE.COVER,
    sowingWindow: [8.5, 10.5],
    harvestMonth: 4.3,
    januaryMinimumC: -30,
    values: { eau: 0.6, fourrage: 0.2, azote: 0.4, matiere_org: 0.6, marche: 0.0 },
  }),
  sheet({
    id: 'jachere',
    name: 'Jachère',
    cropId: 'jachere',
    role: ROLE.FALLOW,
    sowingWindow: null,
    values: { eau: 1.0, fourrage: 0.0, azote: 0.0, matiere_org: 0.0, marche: 0.0 },
  }),
];

export const SHEETS = Object.fromEntries(CROP_SHEETS.map((s) => [s.id, s]));
export const FALLOW_SHEET_ID = 'jachere';

/** Sheets a farmer can have in place now or in a current rotation (sold crops). */
export const SOLD_SHEET_IDS = CROP_SHEETS.filter((s) => s.role === ROLE.SOLD).map((s) => s.id);

/** Display helpers that work for a sheet id as well as a crop id. */
export const cropOf = (id) => CROPS[SHEETS[id]?.cropId ?? id] ?? null;
export const nameOf = (id) => SHEETS[id]?.name ?? CROPS[id]?.name ?? id ?? '—';
export const colorOf = (id) => cropOf(id)?.color ?? '#E5E9E0';
export const textureOf = (id) => cropOf(id)?.texture ?? 'sol';
