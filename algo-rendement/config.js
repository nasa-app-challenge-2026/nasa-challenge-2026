/**
 * Configuration des sources de données satellites, de la taxonomie botanique et des
 * hyperparamètres statistiques de régularisation pour `algo-rendement`.
 *
 * Distinction méthodologique :
 * - ZÉRO valeur agronomique de transition (A -> B) n'est codée en dur : tous les effets
 *   des 36 paires de cultures proviennent des observations satellites régionales.
 * - Les hyperparamètres du modèle statistique (régularisation Ridge, force du prior bayésien,
 *   poids de la distance climatique) sont regroupés explicitement dans `CONFIG.hyperparameters`.
 */
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));

/**
 * Parse une variable d'environnement numérique avec bornes de sécurité et repli garanti sans NaN.
 */
export function parseEnvNumber(rawValue, fallback, { min = -Infinity, max = Infinity } = {}) {
  if (rawValue === undefined || rawValue === null || String(rawValue).trim() === '') {
    return fallback;
  }
  const n = Number(rawValue);
  if (!Number.isFinite(n) || n < min || n > max) {
    return fallback;
  }
  return n;
}

export const CONFIG = {
  /** Dossier de cache local pour éviter de re-télécharger les mêmes cellules satellites */
  cacheDir: process.env.ALGO_CACHE_DIR || join(__dirname, '.cache'),

  /** Timeout HTTP maximal par requête externe (en millisecondes) */
  httpTimeoutMs: parseEnvNumber(process.env.ALGO_HTTP_TIMEOUT_MS, 15000, {
    min: 1000,
    max: 120000,
  }),

  /** Dossier des snapshots NASA POWER existants du dépôt */
  repoSnapshotsDir: join(__dirname, '..', 'data', 'snapshots', 'nasa-power'),

  credentials: {
    earthdataToken: process.env.NASA_EARTHDATA_TOKEN || '',
    nassApiKey: process.env.USDA_NASS_API_KEY || '',
  },

  /** Points d'accès officiels des ressources du défi NASA Space Apps 2026 */
  endpoints: {
    nasaPowerDaily: 'https://power.larc.nasa.gov/api/temporal/daily/point',
    planetaryComputerStac: 'https://planetarycomputer.microsoft.com/api/stac/v1/search',
    planetaryComputerPoint: 'https://planetarycomputer.microsoft.com/api/data/v1/item/point',
    ornlModisSubset: 'https://modis.ornl.gov/rst/api/v1',
    cmrStacSearch: 'https://cmr.earthdata.nasa.gov/stac/LPCLOUD/search',
    usdaCropScapeValue: 'https://nassgeodata.gmu.edu/axis2/services/CDLService/GetCDLValue',
    aafcCropInventoryRest:
      'https://agriculture.canada.ca/imagery-images/rest/services/annual_crop_inventory',
    usdaNassQuickStats: 'https://quickstats.nass.usda.gov/api/api_GET/',
  },

  /** Paramètres d'échantillonnage régional pour l'extraction des paires (A -> B) */
  sampling: {
    startYear: parseEnvNumber(process.env.ALGO_START_YEAR, 2018, { min: 1981, max: 2030 }),
    endYear: parseEnvNumber(process.env.ALGO_END_YEAR, 2024, { min: 1981, max: 2030 }),
    halfWindowKm: parseEnvNumber(process.env.ALGO_WINDOW_KM, 8, { min: 1, max: 25 }),
    minSamplesHighConfidence: 15,
    minSamplesMediumConfidence: 5,
    minRegimeSamplesForStressModulation: 5,
  },

  /**
   * Hyperparamètres statistiques explicites du modèle (régularisation & incertitude)
   */
  hyperparameters: {
    /** Pénalité L2 de la régression météo Ridge */
    ridgeLambda: 1.0,
    /** Force du prior bayésien (en nombre de champs-années) sur la moyenne globale d'une paire */
    pairPriorStrengthK: 4,
    /** Force du prior bayésien hiérarchique rattachant un sous-régime ('sec'/'chaud') à la moyenne de la paire */
    regimePriorStrengthK: 6,
    /** Force de régularisation de la référence monoculture annuelle vers la moyenne régionale de la culture B */
    monocultureBaselinePriorK: 20,
    /** Écart-type a priori minimal (%) par culture cible pour les paires à très faible échantillon */
    minCropPriorStdPct: 4.0,
    /** Plancher de pénalité (%) appliqué à une paire jamais observée dans la région */
    maxUnobservedPairPenaltyPct: -1.5,
    /** Demi-largeur d'incertitude a priori (%) pour une transition non observée */
    unobservedHalfWidthPct: 8.0,
    /** Poids de la distance euclidienne normalisée du Jumeau Climatique (somme = 1.00) */
    climateDistanceWeights: {
      gddBase10: 0.4,
      meanTempC: 0.25,
      heatStressDays: 0.2,
      precipMm: 0.15,
    },
    /** Facteur de décroissance exponentielle pour l'indice visuel de similarité : 100 * exp(-k * d) */
    similarityDecayFactor: 0.35,
    /** Élargissement annuel de l'incertitude (% par année d'horizon futur) */
    horizonUncertaintyPerYearPct: 0.08,
    /** Élargissement de l'incertitude proportionnel à la distance au jumeau (% par unité de distance * alpha) */
    twinDistanceUncertaintyFactor: 0.25,
    /** Horizon (en années) à partir duquel la confiance est systématiquement abaissée d'un cran */
    longHorizonConfidenceDowngradeYears: 12,
  },
};

/**
 * Table de correspondance officielle entre les codes de classification satellites
 * (USDA Cropland Data Layer & AAC Inventaire annuel des cultures du Canada)
 * et les identifiants de cultures du contrat Field Shift.
 */
export const SATELLITE_CROP_MAPPING_VERSION = 2;

export const SATELLITE_CROP_CODES = {
  usdaCdl: {
    1: 'mais',
    5: 'soya',
    21: 'orge',
    22: 'ble',
    23: 'ble',
    24: 'ble',
    36: 'luzerne',
    43: 'patate',
  },
  aafcCanada: {
    147: 'mais',
    158: 'soya',
    133: 'orge',
    140: 'ble',
    145: 'ble',
    146: 'ble',
    // Pasture / Forages inclut aussi graminées, trèfle et mélanges : pas une luzerne identifiée.
    122: null,
    177: 'patate',
  },
};

/**
 * Familles botaniques et noms scientifiques (conformes à `data/reference/crops.yaml`).
 */
export const CROP_TAXONOMY = {
  mais: { scientificName: 'Zea mays', family: 'Poaceae' },
  ble: { scientificName: 'Triticum aestivum', family: 'Poaceae' },
  orge: { scientificName: 'Hordeum vulgare', family: 'Poaceae' },
  soya: { scientificName: 'Glycine max', family: 'Fabaceae' },
  luzerne: { scientificName: 'Medicago sativa', family: 'Fabaceae' },
  patate: { scientificName: 'Solanum tuberosum', family: 'Solanaceae' },
};
