/**
 * What the satellites measure on a field for the erosion risk (step 8), what the water
 * pressure of the farm is made of (water_use), and the soil (step 5). The algorithm sends
 * the values; the screens use these labels.
 */
export const FIELD_MEASURES = {
  slopePct: {
    label: 'Pente',
    unit: '%',
    source: 'SRTM / NASADEM',
    risk: 'erosion',
    explain:
      'Plus la pente est forte, plus la pluie emporte le sol. Le risque est au maximum à 8 %.',
  },
  heavyRainDays: {
    label: 'Jours de forte pluie',
    unit: 'jours par an',
    source: 'GPM IMERG',
    risk: 'erosion',
    explain:
      'Jours avec 25 mm de pluie ou plus : ce sont eux qui creusent le sol nu. Maximum à 8 jours.',
  },
  bareSoilDays: {
    label: 'Jours de sol nu',
    unit: 'jours par an',
    source: 'MODIS / HLS (NDVI)',
    risk: 'erosion',
    explain:
      'Jours où les satellites ne voient aucune plante vivante sur le champ. Maximum à 150 jours.',
  },
};

/**
 * The components of the water pressure of the farm (FarmPlan…waterPressure.components), each
 * from 0 (no pressure) to 1. A component no data base could give is listed in `missing`.
 */
export const WATER_COMPONENTS = {
  aridite: {
    label: 'Aridité',
    explain:
      'Pluie de l’année comparée à l’eau que l’air peut prendre (évapotranspiration de référence). Compte pour 40 %.',
  },
  pluie_ete: {
    label: 'Baisse de la pluie d’été',
    explain:
      'Pluie de juin à août de la seconde moitié de la période comparée à la première. Maximum à −20 %.',
  },
  nappes: {
    label: 'Niveau des nappes',
    explain:
      'Niveau récent des puits suivis près du champ, comparé à leur historique (puits USGS, États-Unis seulement).',
  },
  stress_mesure: {
    label: 'Stress mesuré',
    explain:
      'Sol sec dans la zone des racines (SMAP, sinon le modèle MERRA-2) et stress des plantes (ECOSTRESS).',
  },
};

export const SOIL_PROPERTIES = {
  clayPct: { label: 'Argile', unit: '%' },
  sandPct: { label: 'Sable', unit: '%' },
  organicCarbon: { label: 'Carbone organique', unit: 'g/kg' },
  ph: { label: 'pH', unit: '' },
};

export const RISKS = {
  erosion: { label: 'Risque d’érosion' },
  water: { label: 'Risque de manque d’eau' },
};
