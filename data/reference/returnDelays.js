/**
 * Return delays: how many years without a crop before it may come back on the
 * same field (field_shift.py v5.1, part B). A delay counts the years WITHOUT the
 * crop: "potato: 3" = harvest 2027, nothing in 2028, 2029, 2030, harvest 2031.
 *
 * Two sources:
 *   - Fruchtfolge (Pahmeyer et al. 2021, open-source tool): one break per crop,
 *     "1 year out of N" converted to N − 1 years without the crop;
 *   - SARE, Crop Rotation on Organic Farms, appendix 3 (McGrath 2009): years
 *     without a host crop, per soil-borne disease (north-east of the U.S.).
 * The algorithm derives a minimum (hard constraint) and a recommended delay
 * (pest criterion) from them: see backend/algorithm/delays/ReturnDelayCatalog.js.
 */

/** Families whose different crops may follow each other (grasses, SARE chap. 5). */
export const EXEMPT_FAMILIES = ['Poacées'];

/**
 * Soil-borne diseases (SARE, appendix 3). `low` / `high` = years without a host.
 * `crossFamily` = the disease hits crops of different families (gives a warning).
 */
export const SOIL_DISEASES = {
  'moisissure-blanche': {
    name: 'moisissure blanche',
    latin: 'Sclerotinia sclerotiorum',
    low: 5,
    high: 5,
    crossFamily: true,
    hosts: ['haricot-sec', 'pois', 'soya', 'pomme-de-terre', 'carotte', 'chou', 'courge', 'canola'],
  },
  'hernie-cruciferes': {
    name: 'hernie des crucifères',
    latin: 'Plasmodiophora brassicae',
    low: 7,
    high: 7,
    crossFamily: false,
    hosts: ['chou', 'navet', 'radis', 'canola'],
  },
  'jambe-noire': {
    name: 'jambe noire',
    latin: 'Leptosphaeria maculans (Phoma lingam)',
    low: 4,
    high: 4,
    crossFamily: false,
    hosts: ['chou', 'navet', 'radis', 'canola'],
  },
  'pourriture-noire': {
    name: 'pourriture noire',
    latin: 'Xanthomonas campestris',
    low: 3,
    high: 3,
    crossFamily: false,
    hosts: ['chou', 'navet', 'radis'],
  },
  'gale-commune': {
    name: 'gale commune',
    latin: 'Streptomyces scabies',
    low: 3,
    high: 4,
    crossFamily: true,
    hosts: ['pomme-de-terre', 'betterave', 'carotte', 'navet', 'radis'],
  },
  fusariose: {
    name: 'fusariose de l’épi / gibbérelle',
    latin: 'Fusarium graminearum',
    low: 2,
    high: 3,
    crossFamily: false,
    hosts: ['ble-automne', 'orge', 'avoine', 'seigle', 'mais'],
  },
  'pourriture-brune': {
    name: 'pourriture brune de la tige',
    latin: 'Phialophora gregata',
    low: 2,
    high: 3,
    crossFamily: false,
    hosts: ['soya'],
  },
  'nematode-kyste-soya': {
    name: 'nématode à kyste du soya',
    latin: 'Heterodera glycines',
    low: 4,
    high: 4,
    crossFamily: false,
    hosts: ['soya'],
  },
  'pourridies-legumineuses': {
    name: 'pourridiés des légumineuses',
    latin: 'Pythium, Rhizoctonia, Fusarium',
    low: 3,
    high: 4,
    crossFamily: false,
    hosts: ['haricot-sec', 'pois'],
  },
  'anthracnose-luzerne': {
    name: 'anthracnose de la luzerne',
    latin: 'Colletotrichum trifolii (et Aphanomyces)',
    low: 2,
    high: 3,
    crossFamily: false,
    hosts: ['luzerne'],
  },
  'tache-profonde': {
    name: 'tache profonde',
    latin: 'Pythium spp.',
    low: 3,
    high: 4,
    crossFamily: false,
    hosts: ['carotte'],
  },
  'septoriose-celeri': {
    name: 'septoriose du céleri',
    latin: 'Septoria apiicola',
    low: 2,
    high: 2,
    crossFamily: false,
    hosts: ['celeri'],
  },
  'brulure-botrytique': {
    name: 'brûlure botrytique',
    latin: 'Botrytis squamosa',
    low: 3,
    high: 4,
    crossFamily: false,
    hosts: ['oignon'],
  },
  'mildiou-laitue': {
    name: 'mildiou de la laitue',
    latin: 'Bremia lactucae',
    low: 2,
    high: 3,
    crossFamily: false,
    hosts: ['laitue'],
  },
  'mildiou-epinard': {
    name: 'mildiou de l’épinard',
    latin: 'Peronospora effusa',
    low: 2,
    high: 2,
    crossFamily: false,
    hosts: ['epinard'],
  },
  'cercosporiose-betterave': {
    name: 'cercosporiose de la betterave',
    latin: 'Cercospora beticola',
    low: 3,
    high: 3,
    crossFamily: false,
    hosts: ['betterave'],
  },
  'anthracnose-cucurbitacees': {
    name: 'anthracnose des cucurbitacées',
    latin: 'Colletotrichum orbiculare',
    low: 2,
    high: 2,
    crossFamily: false,
    hosts: ['courge'],
  },
  'fletrissure-cucurbitacees': {
    name: 'flétrissure fusarienne des cucurbitacées',
    latin: 'Fusarium oxysporum',
    low: 5,
    high: 7,
    crossFamily: false,
    hosts: ['courge'],
  },
  'septoriose-tomate': {
    name: 'septoriose de la tomate',
    latin: 'Septoria lycopersici',
    low: 3,
    high: 3,
    crossFamily: false,
    hosts: ['tomate'],
  },
  'fletrissure-tomate': {
    name: 'flétrissure fusarienne de la tomate',
    latin: 'Fusarium oxysporum f. sp. lycopersici',
    low: 5,
    high: 7,
    crossFamily: false,
    hosts: ['tomate'],
  },
};

/**
 * One line per crop. `fruchtfolgeYearsWithout` = Fruchtfolge break − 1 (null when
 * the crop is not in Fruchtfolge); `referenceDisease` = the SARE disease whose
 * low value is used for the delays.
 */
const row = (family, fruchtfolgeYearsWithout, referenceDisease, perennial = false) => ({
  family,
  fruchtfolgeYearsWithout,
  referenceDisease,
  perennial,
});

export const CROP_DELAYS = {
  mais: row('Poacées', 1, 'fusariose'),
  'ble-automne': row('Poacées', 1, 'fusariose'),
  orge: row('Poacées', 1, 'fusariose'),
  avoine: row('Poacées', 2, 'fusariose'),
  seigle: row('Poacées', 1, 'fusariose'),
  foin: row('Poacées', 0, null, true),
  sarrasin: row('Polygonacées', 1, null),
  soya: row('Fabacées', 2, 'pourriture-brune'),
  'haricot-sec': row('Fabacées', 2, 'pourridies-legumineuses'),
  pois: row('Fabacées', 4, 'pourridies-legumineuses'),
  luzerne: row('Fabacées', 3, 'anthracnose-luzerne', true),
  canola: row('Brassicacées', 3, 'jambe-noire'),
  chou: row('Brassicacées', 4, 'jambe-noire'),
  navet: row('Brassicacées', 2, 'pourriture-noire'),
  radis: row('Brassicacées', 2, 'pourriture-noire'),
  'pomme-de-terre': row('Solanacées', 2, 'gale-commune'),
  tomate: row('Solanacées', null, 'septoriose-tomate'),
  carotte: row('Apiacées', 3, 'tache-profonde'),
  celeri: row('Apiacées', 2, 'septoriose-celeri'),
  oignon: row('Amaryllidacées', 2, 'brulure-botrytique'),
  laitue: row('Astéracées', 1, 'mildiou-laitue'),
  epinard: row('Amaranthacées', 1, 'mildiou-epinard'),
  betterave: row('Amaranthacées', 3, 'cercosporiose-betterave'),
  courge: row('Cucurbitacées', 1, 'anthracnose-cucurbitacees'),
};

/** Crops of the sheets that share the return delays of another crop. */
export const DELAY_ALIASES = { 'soya-2e': 'soya' };
