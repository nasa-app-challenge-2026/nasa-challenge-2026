/** Static content: farm types, priorities, demo places, sources. */

export const FARM_TYPES = [
  {
    id: 'grandes-cultures',
    name: 'Grandes cultures',
    what: 'Maïs, soya, blé, patate, en sections',
    available: true,
    scale: 'des années',
    how: 'Une culture par an et par section. Vous découpez votre ferme en sections A, B, C, D et vous choisissez une rotation pour chacune. L’appli décale les sections pour avoir plusieurs cultures chaque année.',
    icon: 'M12 21V11M12 11C12 7 9 4 4 4c0 5 3 7 8 7ZM12 14c0-3 2.5-6 8-6 0 4-3 6-8 6Z',
  },
  {
    id: 'maraichage',
    name: 'Maraîchage',
    what: 'Légumes cultivés en planches',
    available: false,
    scale: 'des saisons',
    how: 'La rotation se fait par familles de légumes (tomate et patate, chou, oignon, pois), planche par planche, avec parfois 2 ou 3 récoltes dans la même saison.',
    icon: 'M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.5 19 2c1 2 2 4.2 2 8 0 5.5-4.8 10-10 10ZM2 21c0-3 1.9-5.4 5.1-6',
  },
  {
    id: 'mixte',
    name: 'Cultures et élevage',
    what: 'Céréales et prairies pour les animaux',
    available: false,
    scale: 'des années',
    how: 'Les céréales alternent avec une prairie de 2 à 4 ans (luzerne, trèfle) qui nourrit le troupeau. Le fumier revient sur les champs.',
    icon: 'M3 21V10l9-6 9 6v11ZM9 21v-6h6v6M3 10h18',
  },
  {
    id: 'paturage',
    name: 'Pâturage tournant',
    what: 'Un troupeau et des enclos',
    available: false,
    scale: 'des jours',
    how: 'Ce sont les animaux qui tournent : quelques jours par enclos, pendant que l’herbe repousse dans les autres.',
    icon: 'M4 21V7l2-3 2 3v14M16 21V7l2-3 2 3v14M8 10h8M8 16h8',
  },
  {
    id: 'vergers',
    name: 'Vergers et vignes',
    what: 'Arbres et vigne en place',
    available: false,
    scale: 'des dizaines d’années',
    how: 'Les arbres restent 20 à 40 ans : presque pas de rotation. L’enjeu est de ne pas replanter la même espèce au même endroit.',
    icon: 'M12 22v-6M12 16a6 6 0 1 0 0-12 6 6 0 0 0 0 12Z',
  },
];

export const PRIORITIES = {
  revenu: {
    label: 'Revenu',
    text: 'Gagner le plus possible sur la durée de la rotation.',
    icon: 'M12 2v20M17 6H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6',
  },
  resilience: {
    label: 'Résilience',
    text: 'Tenir le coup les années sèches, chaudes ou avec ravageurs.',
    icon: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z',
  },
  sol: {
    label: 'Santé du sol',
    text: 'Garder un sol riche et vivant pour les prochaines années.',
    icon: 'M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.5 19 2c1 2 2 4.2 2 8 0 5.5-4.8 10-10 10ZM2 21c0-3 1.9-5.4 5.1-6',
  },
  eau: {
    label: 'Eau',
    text: 'Utiliser moins d’eau et mieux résister au manque de pluie.',
    icon: 'M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5S12.5 5 12 2.5C11.5 5 10 7.4 8 9 6 10.6 5 12.5 5 15a7 7 0 0 0 7 7Z',
  },
  travail: {
    label: 'Charge de travail',
    text: 'Limiter le travail en plus et le nombre de machines différentes.',
    icon: 'M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.8-3.8a6 6 0 0 1-7.9 7.9l-6.9 6.9a2.1 2.1 0 0 1-3-3l6.9-6.9a6 6 0 0 1 7.9-7.9Z',
  },
};

/** Weight of each priority rank (1st … 5th), in percent. */
export const PRIORITY_WEIGHTS = [35, 25, 18, 13, 9];

/** Suggestions shown before the first address search. */
export const DEMO_PLACES = [
  { label: 'Rang Saint-Pierre', detail: 'Saint-Hyacinthe, QC', lat: 45.6287, lon: -72.94815 },
  { label: 'Saint-Hyacinthe', detail: 'Montérégie, QC · ville', lat: 45.6307, lon: -72.957 },
  { label: 'Saint-Dominique', detail: 'Montérégie, QC', lat: 45.5833, lon: -72.8333 },
];

export const STRESS_SCENARIOS = [
  {
    id: 'normal',
    name: 'Normale',
    sub: 'Une année moyenne',
    title: 'Année normale',
    desc: 'Pluie et température proches de la moyenne des 10 dernières années sur votre section.',
    source: 'NASA POWER et GPM IMERG',
    icon: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8ZM12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4',
  },
  {
    id: 'sec',
    name: 'Sécheresse',
    sub: '40 % de pluie en moins',
    title: 'Année sèche',
    desc: 'Il pleut beaucoup moins pendant l’été. Une rotation diversifiée perd nettement moins de rendement qu’une monoculture dans ces années-là.',
    source: 'NASA SMAP, GPM IMERG',
    icon: 'M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5S12.5 5 12 2.5C11.5 5 10 7.4 8 9 6 10.6 5 12.5 5 15a7 7 0 0 0 7 7ZM4 4l16 16',
  },
  {
    id: 'chaud',
    name: 'Canicule',
    sub: '+3 °C en juillet',
    title: 'Année chaude',
    desc: 'Des vagues de chaleur pendant la floraison. L’avantage de la rotation diminue un peu pour le maïs, mais reste positif.',
    source: 'NASA POWER, projections NEX-GDDP-CMIP6',
    icon: 'M14 4v10.5a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0Z',
  },
  {
    id: 'ravageurs',
    name: 'Ravageurs',
    sub: 'Insectes et maladies',
    title: 'Année à ravageurs',
    desc: 'Une forte présence d’insectes ou de maladies liés à une culture. La rotation casse leur cycle : ils trouvent moins de nourriture d’une année à l’autre.',
    source: 'Études sur la rotation (voir Sources)',
    icon: 'M12 13a5 5 0 1 0 0 10 5 5 0 0 0 0-10ZM12 13V9M8 9h8M9 9 7 5M15 9l2-4M7 16H3M21 16h-4',
  },
];

export const SCORE_LABELS = { eau: 'Eau', sol: 'Sol', resilience: 'Résilience', revenu: 'Revenu' };
export const SCORE_KEYS = ['eau', 'sol', 'resilience', 'revenu'];

export const BASELINES = {
  'mais-continu': { label: 'Maïs en continu', name: 'du maïs en continu' },
  'mais-soya': { label: 'Maïs-soya', name: 'la rotation maïs-soya' },
};
