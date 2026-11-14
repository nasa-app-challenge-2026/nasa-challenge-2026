/**
 * What the satellites measure on a field for the diagnostic (step 8) and its soil
 * (step 5). The algorithm sends the values; the screens use these labels.
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
  summerStressIndex: {
    label: 'Stress des plantes en été',
    unit: 'indice ESI',
    source: 'ECOSTRESS',
    risk: 'water',
    explain:
      'Indice de stress hydrique : 1 = les plantes ont toute l’eau qu’il leur faut. Le stress commence sous 0,8.',
  },
  rootZoneDrought: {
    label: 'Sécheresse des racines',
    unit: '0 à 1',
    source: 'SMAP L4',
    risk: 'water',
    explain: 'Manque d’eau dans la zone des racines (0 = humide, 1 = très sec).',
  },
  groundwaterTrendCmPerYear: {
    label: 'Réserves d’eau régionales',
    unit: 'cm par an',
    source: 'GRACE-FO',
    risk: 'water',
    explain: 'Évolution des réserves d’eau de la région (négatif = elles baissent).',
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
