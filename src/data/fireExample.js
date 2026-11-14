/**
 * A real farm fire, to see the whole chain at work on the fire page (#/feux)
 * without changing the user's farm. Nothing here is invented: the place, the
 * date and the burned area come from the services the page queries.
 *
 * Early May 2023, about 28 km north-west of Melfort (Saskatchewan): 27 VIIRS
 * hotspots on farmland between May 1 and May 4, a 406 ha burned area in the
 * national burned-area map (NBAC), and the AAFC crop inventory labels part of
 * it "burnt area" in 2023 after a year of oats and canola.
 *
 * Section A sits inside the burned area, section B on the field next to it
 * (wheat, then canola), outside the fire. They are 300 m squares (9 ha).
 * The rotations only use the app's catalogue; they are not the real ones.
 */
export const FIRE_EXAMPLE = {
  id: 'exemple',
  name: 'Exemple réel · feu agricole de mai 2023',
  location: { lat: 53.0853, lon: -104.8115, label: 'Près de Melfort, Saskatchewan' },
  boundary: [
    [53.0891, -104.8162],
    [53.0891, -104.8068],
    [53.0815, -104.8068],
    [53.0815, -104.8162],
  ],
  radiusKm: 10,
  years: 5,
  sections: [
    {
      id: 'A',
      areaHa: 9,
      offset: 0,
      note: 'dans la zone brûlée',
      polygon: [
        [53.08449, -104.81597],
        [53.08449, -104.81148],
        [53.08179, -104.81148],
        [53.08179, -104.81597],
      ],
      rotation: [
        { crop: 'ble', years: 1, cover: null },
        { crop: 'orge', years: 1, cover: null },
        { crop: 'soya', years: 1, cover: null },
      ],
    },
    {
      id: 'B',
      areaHa: 9,
      offset: 0,
      note: 'champ voisin, hors du feu',
      polygon: [
        [53.08884, -104.81159],
        [53.08884, -104.8071],
        [53.08615, -104.8071],
        [53.08615, -104.81159],
      ],
      rotation: [
        { crop: 'orge', years: 1, cover: null },
        { crop: 'soya', years: 1, cover: null },
        { crop: 'ble', years: 1, cover: null },
      ],
    },
  ],
};
