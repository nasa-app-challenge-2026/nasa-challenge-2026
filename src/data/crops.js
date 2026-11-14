/**
 * Crop catalogue shared by the UI and the demo engine.
 *
 * `returnDelay` = minimum number of years before the crop may come back on the
 * same section. Values are provisional: to be confirmed by the algo team.
 * `years` = how many consecutive years one planting occupies (alfalfa = 3).
 */
export const CROPS = {
  mais: {
    id: 'mais',
    name: 'Maïs',
    color: '#F2C14E',
    years: 1,
    returnDelay: 2,
    roles: ['gourmand'],
  },
  soya: {
    id: 'soya',
    name: 'Soya',
    color: '#9CC27A',
    years: 1,
    returnDelay: 2,
    roles: ['azote'],
  },
  ble: { id: 'ble', name: 'Blé', color: '#DDB07F', years: 1, returnDelay: 2, roles: [] },
  orge: { id: 'orge', name: 'Orge', color: '#BFD6E6', years: 1, returnDelay: 2, roles: ['sec'] },
  patate: {
    id: 'patate',
    name: 'Patate',
    color: '#C3A3D6',
    years: 1,
    returnDelay: 4,
    roles: [],
  },
  luzerne: {
    id: 'luzerne',
    name: 'Luzerne',
    color: '#7FC0B2',
    years: 3,
    returnDelay: 4,
    roles: ['azote', 'racines', 'couverture'],
  },
};

export const CROP_IDS = Object.keys(CROPS);

/** Winter cover crops, sown between two main crops. */
export const COVERS = {
  seigle: { id: 'seigle', name: 'Seigle', roles: ['couverture'] },
  trefle: { id: 'trefle', name: 'Trèfle', roles: ['couverture', 'azote'] },
  radis: { id: 'radis', name: 'Radis fourrager', roles: ['couverture', 'racines'] },
};

export const COVER_IDS = Object.keys(COVERS);

/** Soil-health roles. `icon` is an SVG path (24×24, stroke). */
export const ROLES = {
  azote: {
    label: 'Fixe l’azote',
    text: 'Les légumineuses (soya, luzerne, trèfle) vivent avec des bactéries dans leurs racines qui captent l’azote de l’air. Elles en laissent dans le sol pour la culture suivante : moins d’engrais à acheter.',
    bg: '#EAF3DE',
    fg: '#27500A',
    icon: 'M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.5 19 2c1 2 2 4.2 2 8 0 5.5-4.8 10-10 10ZM2 21c0-3 1.9-5.4 5.1-6',
  },
  racines: {
    label: 'Racines profondes',
    text: 'La luzerne et le radis fourrager envoient leurs racines très bas. Elles cassent le sol tassé, ouvrent des chemins pour l’eau et remontent des nutriments que les autres cultures n’atteignent pas.',
    bg: '#E6F1FB',
    fg: '#0C447C',
    icon: 'M12 3v14M6 11l6 6 6-6M5 21h14',
  },
  couverture: {
    label: 'Couvre le sol',
    text: 'Une culture de couverture pousse entre deux récoltes, l’automne et l’hiver. Le sol n’est jamais nu : moins d’érosion, plus de matière organique, et l’azote qui reste est retenu au lieu de partir avec la pluie.',
    bg: '#E1F5EE',
    fg: '#085041',
    icon: 'M3 12a9 9 0 0 1 18 0ZM12 12v7a2 2 0 0 0 4 0',
  },
  sec: {
    label: 'Tolère le sec',
    text: 'L’orge a besoin de moins d’eau que le maïs et finit son cycle avant les chaleurs de l’été. Elle réduit le risque les années sèches et laisse plus d’eau dans le sol.',
    bg: '#FAEEDA',
    fg: '#633806',
    icon: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8ZM12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4',
  },
  gourmand: {
    label: 'Gourmand en azote',
    text: 'Le maïs consomme beaucoup d’azote. Placé juste après une légumineuse, il profite de l’azote qu’elle a laissé.',
    bg: '#FCEBEB',
    fg: '#791F1F',
    icon: 'M12 8v4M12 16h.01M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20Z',
  },
};

/** Roles counted in the soil-health summary, in display order. */
export const SOIL_ROLES = ['azote', 'racines', 'couverture', 'sec'];
