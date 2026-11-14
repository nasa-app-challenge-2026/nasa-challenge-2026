/**
 * Soil-borne diseases a farmer can declare on a section (SARE, appendix 3). A declared disease makes
 * the algorithm require the longest delay without a host crop; the delays, hosts and sources live in
 * the server (backend/server/field_shift/reference/return_delays.py). The ids are the contract.
 */
export const SOIL_DISEASES = {
  'moisissure-blanche': { name: 'moisissure blanche', latin: 'Sclerotinia sclerotiorum' },
  'hernie-cruciferes': { name: 'hernie des crucifères', latin: 'Plasmodiophora brassicae' },
  'jambe-noire': { name: 'jambe noire', latin: 'Leptosphaeria maculans (Phoma lingam)' },
  'pourriture-noire': { name: 'pourriture noire', latin: 'Xanthomonas campestris' },
  'gale-commune': { name: 'gale commune', latin: 'Streptomyces scabies' },
  fusariose: { name: 'fusariose de l’épi / gibbérelle', latin: 'Fusarium graminearum' },
  'pourriture-brune': { name: 'pourriture brune de la tige', latin: 'Phialophora gregata' },
  'nematode-kyste-soya': { name: 'nématode à kyste du soya', latin: 'Heterodera glycines' },
  'pourridies-legumineuses': {
    name: 'pourridiés des légumineuses',
    latin: 'Pythium, Rhizoctonia, Fusarium',
  },
  'anthracnose-luzerne': {
    name: 'anthracnose de la luzerne',
    latin: 'Colletotrichum trifolii (et Aphanomyces)',
  },
  'tache-profonde': { name: 'tache profonde', latin: 'Pythium spp.' },
  'septoriose-celeri': { name: 'septoriose du céleri', latin: 'Septoria apiicola' },
  'brulure-botrytique': { name: 'brûlure botrytique', latin: 'Botrytis squamosa' },
  'mildiou-laitue': { name: 'mildiou de la laitue', latin: 'Bremia lactucae' },
  'mildiou-epinard': { name: 'mildiou de l’épinard', latin: 'Peronospora effusa' },
  'cercosporiose-betterave': {
    name: 'cercosporiose de la betterave',
    latin: 'Cercospora beticola',
  },
  'anthracnose-cucurbitacees': {
    name: 'anthracnose des cucurbitacées',
    latin: 'Colletotrichum orbiculare',
  },
  'fletrissure-cucurbitacees': {
    name: 'flétrissure fusarienne des cucurbitacées',
    latin: 'Fusarium oxysporum',
  },
  'septoriose-tomate': { name: 'septoriose de la tomate', latin: 'Septoria lycopersici' },
  'fletrissure-tomate': {
    name: 'flétrissure fusarienne de la tomate',
    latin: 'Fusarium oxysporum f. sp. lycopersici',
  },
};
