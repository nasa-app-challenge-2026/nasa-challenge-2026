/**
 * The nine criteria of the chain score (step 9b of field_shift.py v5.1). The
 * farmer ranks the ones that matter to him; the algorithm turns the ranking into
 * weights (rank order centroid) and scores every chain on each criterion (0 to 1).
 */
export const CRITERIA = {
  rendement: {
    label: 'Rendement',
    text: 'Chaque culture aide-t-elle la suivante ? Mesuré par satellite dans les champs jumeaux.',
    icon: 'M3 17l6-6 4 4 8-8M14 7h7v7',
  },
  eau: {
    label: 'Eau',
    text: 'Des cultures sobres en eau, surtout si l’été devient plus sec.',
    icon: 'M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5S12.5 5 12 2.5C11.5 5 10 7.4 8 9 6 10.6 5 12.5 5 15a7 7 0 0 0 7 7Z',
  },
  fourrage: {
    label: 'Fourrage',
    text: 'Nourrir le troupeau (compte peu sans bétail).',
    icon: 'M4 20h16M6 20V9l6-5 6 5v11M10 20v-5h4v5',
  },
  azote: {
    label: 'Azote',
    text: 'Des légumineuses qui laissent de l’azote : moins d’engrais à acheter.',
    icon: 'M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.5 19 2c1 2 2 4.2 2 8 0 5.5-4.8 10-10 10ZM2 21c0-3 1.9-5.4 5.1-6',
  },
  erosion: {
    label: 'Érosion',
    text: 'Garder le sol couvert par une culture vivante le plus longtemps possible.',
    icon: 'M3 12a9 9 0 0 1 18 0ZM12 12v7a2 2 0 0 0 4 0',
  },
  matiere_org: {
    label: 'Matière organique',
    text: 'Des cultures qui nourrissent le sol pour les années suivantes.',
    icon: 'M12 21V11M12 11C12 7 9 4 4 4c0 5 3 7 8 7ZM12 14c0-3 2.5-6 8-6 0 4-3 6-8 6Z',
  },
  marche: {
    label: 'Marché',
    text: 'Des cultures qui se vendent bien.',
    icon: 'M12 2v20M17 6H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6',
  },
  ravageurs: {
    label: 'Ravageurs',
    text: 'Laisser à chaque culture son délai de retour conseillé, pour casser le cycle des maladies.',
    icon: 'M12 13a5 5 0 1 0 0 10 5 5 0 0 0 0-10ZM12 13V9M8 9h8M9 9 7 5M15 9l2-4M7 16H3M21 16h-4',
  },
  reserve: {
    label: 'Ma réserve',
    text: 'Semer d’abord les semences que j’ai déjà.',
    icon: 'M3 7l9-4 9 4v10l-9 4-9-4ZM3 7l9 4 9-4M12 11v10',
  },
};

/** Fixed order of the criteria (field_shift.py, CRITERES). */
export const CRITERIA_IDS = [
  'rendement',
  'eau',
  'fourrage',
  'azote',
  'erosion',
  'matiere_org',
  'marche',
  'ravageurs',
  'reserve',
];
