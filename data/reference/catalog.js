/** Static content: farm types and demo places. */

export const FARM_TYPES = [
  {
    id: 'grandes-cultures',
    name: 'Grandes cultures',
    what: 'Maïs, soya, blé, orge, canola, luzerne, en sections',
    available: true,
    icon: 'M12 21V11M12 11C12 7 9 4 4 4c0 5 3 7 8 7ZM12 14c0-3 2.5-6 8-6 0 4-3 6-8 6Z',
  },
  {
    id: 'maraichage',
    name: 'Maraîchage',
    what: 'Légumes cultivés en planches',
    available: false,
    icon: 'M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.5 19 2c1 2 2 4.2 2 8 0 5.5-4.8 10-10 10ZM2 21c0-3 1.9-5.4 5.1-6',
  },
  {
    id: 'mixte',
    name: 'Cultures et élevage',
    what: 'Céréales et prairies pour les animaux',
    available: false,
    icon: 'M3 21V10l9-6 9 6v11ZM9 21v-6h6v6M3 10h18',
  },
  {
    id: 'paturage',
    name: 'Pâturage tournant',
    what: 'Un troupeau et des enclos',
    available: false,
    icon: 'M4 21V7l2-3 2 3v14M16 21V7l2-3 2 3v14M8 10h8M8 16h8',
  },
  {
    id: 'vergers',
    name: 'Vergers et vignes',
    what: 'Arbres et vigne en place',
    available: false,
    icon: 'M12 22v-6M12 16a6 6 0 1 0 0-12 6 6 0 0 0 0 12Z',
  },
];

/** Suggestions shown before the first address search. */
export const DEMO_PLACES = [
  { label: 'Rang Saint-Pierre', detail: 'Saint-Hyacinthe, QC', lat: 45.6287, lon: -72.94815 },
  { label: 'Saint-Hyacinthe', detail: 'Montérégie, QC · ville', lat: 45.6307, lon: -72.957 },
  { label: 'Saint-Dominique', detail: 'Montérégie, QC', lat: 45.5833, lon: -72.8333 },
];
