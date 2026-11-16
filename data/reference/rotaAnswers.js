/**
 * Rota, the assistant of the app, version "written in advance". Reliable for the demo video and
 * free to run. Three kinds of answers, all checked by the team, none names a study:
 *
 *   TOPICS   what the « Demander à Rota » buttons of the screens explain. The screens show no
 *            explanation themselves: a button opens Rota on its topic.
 *   INTENTS  answers to free questions, matched by keywords.
 *   OUT_OF_MVP  what Rota says of a feature the MVP does not have.
 *
 * To plug a real language model later, keep this file as the fallback and see docs/ROTA.md.
 */
import { CRITERIA, CRITERIA_IDS } from './criteria.js';
import { FIELD_MEASURES, WATER_COMPONENTS } from './fieldMeasures.js';
import { RESERVE_MODES } from './planning.js';
import { t } from '../i18n/index.js';

/** Suggested questions, per screen (`general`: the screens of the first visit). */
export const SUGGESTED = {
  general: [
    'Comment l’appli choisit mes cultures ?',
    'C’est quoi un jumeau climatique ?',
    'D’où viennent ces données ?',
  ],
  tableau: [
    'Comment lire le tableau de bord ?',
    'Comment l’appli choisit mes cultures ?',
    'Pourquoi garder ou changer ?',
    'C’est quoi un jumeau climatique ?',
  ],
  parcelle: [
    'Pourquoi demander les années précédentes ?',
    'À quoi sert ma rotation actuelle ?',
    'C’est quoi un délai de retour ?',
    'Pourquoi déclarer une maladie du sol ?',
  ],
  champ: [
    'Comment est calculé le risque d’érosion ?',
    'Comment est calculé le risque d’eau ?',
    'À quoi sert le sol ?',
    'D’où viennent ces données ?',
  ],
  plan: [
    'Comment sont choisies ces rotations ?',
    'Comment lire la roue ?',
    'Pourquoi une jachère ?',
    'C’est quoi la robustesse ?',
  ],
  jumeaux: [
    'C’est quoi sigma ?',
    'Pourquoi des modèles climatiques après 10 ans ?',
    'Pourquoi les jumeaux sont plus au sud ?',
    'Pourquoi comparer à 2011-2024 ?',
  ],
};

export const GREETING =
  'Bonjour ! Je suis Rota. Je vous explique comment l’appli construit votre plan. Posez une question ou choisissez-en une ci-dessous.';

/** What Rota answers when the farmer touches something the MVP does not do. */
export const OUT_OF_MVP = 'Hors de portée du MVP.';

const FALLBACK = {
  text: 'Je n’ai pas encore de réponse à ça. Essayez une des questions proposées, ou regardez Détail et sources pour les données et les méthodes.',
  sources: true,
};

const TWIN =
  'Un jumeau climatique est un endroit qui a déjà connu, entre 2011 et 2024, le climat que votre ferme aura pendant un cycle. L’appli regarde ce que les fermiers y cultivent sur un sol comme le vôtre, et avec quel succès vu par satellite.';
const SIGMA =
  'Sigma mesure à quel point deux climats se ressemblent, en tenant compte des écarts normaux d’une année à l’autre. 0 = identiques, moins de 2 = bon jumeau. Au-delà de 2, le climat visé n’existe nulle part et la recommandation est moins fiable.';
const CLIMATE_SOURCE =
  'Pour les cycles qui finissent dans les 10 ans, l’appli prolonge la tendance des 40 dernières années de NASA POWER. Plus loin, une tendance en ligne droite ne suffit plus : elle applique à la vraie météo de la ferme le changement que prévoient plusieurs modèles climatiques, chacun séparément.';
const HOW_CHOSEN =
  'Pour chaque cycle, l’appli calcule le climat de votre ferme, trouve ses jumeaux, garde les cultures qui y poussent, puis essaie des milliers de suites de cultures. Elle écarte celles qui ne respectent pas le calendrier, le gel, les délais de retour ou ce qui se fait chez les jumeaux, et note les autres selon vos priorités.';
const KEEP_OR_CHANGE =
  'Au premier cycle, la suite en place est votre rotation actuelle ; ensuite, celle choisie au cycle d’avant. On la garde si elle respecte les délais de retour, si ses cultures poussent encore chez les jumeaux et si sa note est à 5 points ou moins de la meilleure. Sinon, on change.';
const ROBUSTNESS =
  'La robustesse rejoue une suite de cultures dans tous les cycles suivants, avec leur climat et leurs jumeaux, et garde sa pire note. Si elle devient impossible plus tard, l’appli l’affiche.';
const UNMEASURED =
  'Un précédent pas mesuré veut dire que l’enchaînement n’a pas été vu assez souvent dans les champs de la région (moins de 5 fois), ou qu’une des cultures manque aux cartes (foin, canola, sarrasin). Il compte comme une succession peu favorable, pour qu’une culture inconnue ne gagne pas parce qu’elle est inconnue, et l’appli le signale.';
const HISTORY =
  'Les délais de retour se comptent aussi avec ce qui a poussé avant. Si vous avez eu du soya en 2025, l’appli ne peut pas en remettre en 2027. Elle demande autant d’années que le plus long délai de retour des cultures possibles.';
const PESTS =
  'La priorité ravageurs suit, année après année, la pression de chaque maladie, nématode ou insecte du sol : elle monte quand une de ses cultures hôtes pousse et baisse pendant les années sans hôte. Chaque culture est pénalisée par la pression qu’elle trouve en arrivant. Une maladie que vous déclarez part d’une pression pleine.';
const DISEASE =
  'Une maladie du sol que vous connaissez rend obligatoire son délai le plus long pour toutes ses cultures-hôtes. Par exemple, avec la hernie des crucifères, 7 ans sans canola, chou ni radis.';
const CURRENT_ROTATION =
  'Votre rotation actuelle est prolongée cycle après cycle et notée avec les mêmes règles. Elle sert de comparaison : si elle ne respecte pas un délai de retour, l’appli vous le signale, sans la rejeter.';
const EROSION =
  'Le risque d’érosion combine la pente (la moitié), les jours de forte pluie et les jours de sol nu, vus par satellite. Plus il est haut, plus la priorité protection du sol pèse dans la note.';
const WATER_RISK =
  'Le risque d’eau est la pression sur l’eau de la ferme pendant le cycle : l’aridité de sa météo (pluie comparée à l’eau que l’air peut prendre), la baisse de la pluie d’été, le niveau des nappes et le stress mesuré (sol sec, stress des plantes) quand ces mesures existent. Une parcelle irriguée en garde 40 %. La note eau d’une suite de cultures vient d’une simulation de l’eau du sol jour par jour.';
const DASHBOARD =
  'En haut, la météo de la semaine à la ferme. Les boutons des années font avancer toute la page. À gauche, votre ferme en 3D : chaque section porte la culture de l’année choisie ; glissez pour la faire tourner, utilisez la molette pour zoomer, et touchez une section pour la choisir (elle se soulève). Le camembert dans le coin montre la part de chaque culture sur la ferme cette année-là. À droite, une carte par section : la culture de l’année, la rotation du cycle en cours (la culture de l’année est entourée) et la note du plan sur 100. Vous pouvez réordonner les cartes en glissant leur poignée.';
const PRIORITIES = `Classez les quatre priorités, de la plus importante à la moins importante. ${CRITERIA_IDS.map(
  (id) => `${CRITERIA[id].label} : ${CRITERIA[id].text}`,
).join(
  ' ',
)} Chaque suite de cultures reçoit une note sur chacune ; sa note finale est leur moyenne, pondérée par les pourcentages affichés. L’appli donne aussi plus de poids à la protection du sol et à l’eau si votre champ y est fragile.`;

/**
 * What the « Demander à Rota » buttons explain: `q` is shown as the farmer's question, `text` as
 * Rota's answer. `sources: true` adds the link to « Détail et sources ».
 */
export const TOPICS = {
  // First visit
  'types-ferme': {
    q: 'Pourquoi choisir un type de ferme ?',
    text: 'La rotation ne marche pas pareil partout : en grandes cultures elle se compte en années, en maraîchage en saisons, au pâturage en jours. Field Shift planifie les grandes cultures. Vous découpez votre ferme en sections A, B, C… et vous dites ce qui y pousse. Pour chaque section et chaque cycle, l’appli calcule le climat à venir, trouve les endroits qui le vivent déjà et construit la meilleure suite de cultures.',
  },
  localiser: {
    q: 'Comment placer ma ferme ?',
    text: 'Cherchez une adresse, un rang ou un village, puis ajustez l’épingle : glissez-la ou cliquez sur la carte. La météo et le climat de votre plan sont lus à cet endroit.',
  },
  tracer: {
    q: 'Comment tracer ma ferme ?',
    text: 'Cliquez d’abord les coins principaux du contour de la ferme, pas chaque courbe, puis fermez-le. Tracez ensuite chaque section de la même façon. Une section est une partie de la ferme qui a la même culture la même année. Ses coins s’aimantent au contour et aux autres sections, pour qu’elles se touchent sans trou. Vous pouvez glisser les coins pour ajuster.',
  },
  cultures: {
    q: 'Pourquoi dire ce que je cultive ?',
    text: 'Pour chaque section, l’appli part de ce qui pousse maintenant et du mois de sa récolte : le plan commence quand le champ se libère. Les années précédentes, les maladies du sol et l’analyse de sol se donnent plus tard, dans « Ma parcelle ».',
  },
  'rotation-actuelle': {
    q: 'À quoi sert ma rotation actuelle ?',
    text: `C’est la suite de cultures que vous suivez aujourd’hui. ${CURRENT_ROTATION} Touchez dans la liste la culture qui est en place en ce moment.`,
  },
  reserve: {
    q: 'À quoi sert ma réserve de semences ?',
    text: `Cochez les semences que vous avez déjà, sans les quantités. « ${RESERVE_MODES.preferer.label} » : ${RESERVE_MODES.preferer.text} « ${RESERVE_MODES.uniquement.label} » : ${RESERVE_MODES.uniquement.text}`,
  },
  temps: {
    q: 'Comment choisir le cycle et l’horizon ?',
    text: 'Le cycle est le nombre d’années après lequel la rotation recommence. La fréquence dit combien de cultures vous récoltez par an : chaque récolte est une position du cycle, et l’appli choisit une culture pour chacune. L’horizon est la durée du plan : toujours un nombre entier de cycles, jusqu’en 2060 au plus. Pour chaque cycle, l’appli calcule le climat de la ferme : dans les 10 prochaines années avec la tendance des 40 dernières années de NASA POWER, au-delà avec des modèles climatiques.',
    sources: true,
  },
  priorites: { q: 'Comment marchent les priorités ?', text: PRIORITIES },
  equipement: {
    q: 'Pourquoi demander mon équipement ?',
    text: 'Sans récolteuse fourragère, l’appli ne propose ni luzerne ni foin.',
  },

  // Dashboard
  tableau: { q: 'Comment lire le tableau de bord ?', text: DASHBOARD },
  chargement: {
    q: 'Pourquoi le plan prend du temps ?',
    text: 'Pour un nouveau lieu, l’appli lit 40 ans de météo NASA POWER, les modèles climatiques, la grille des jumeaux et les cartes de cultures : quelques minutes la première fois, puis tout est gardé. Le calcul lui-même prend quelques secondes : le plus long est la simulation de l’eau du sol, jour par jour, pour les meilleures suites de cultures.',
    sources: true,
  },

  // Plan of a section
  'trois-rotations': {
    q: 'Comment sont choisies ces rotations ?',
    text: `${HOW_CHOSEN} Elle vous montre les trois meilleures : la première est celle qu’elle recommande. Votre rotation actuelle, notée avec les mêmes règles, sert de comparaison.`,
    sources: true,
  },
  'garder-changer': { q: 'Pourquoi garder ou changer ?', text: KEEP_OR_CHANGE },
  note: {
    q: 'Que veut dire la note sur 100 ?',
    text: 'La note est la moyenne des quatre priorités (rendement, eau, protection du sol, ravageurs), pondérée par votre classement et par les risques de la parcelle. 100 serait une rotation parfaite sur les quatre.',
  },
  robustesse: { q: 'C’est quoi la robustesse ?', text: ROBUSTNESS },
  roue: {
    q: 'Comment lire la roue ?',
    text: 'La roue se lit dans le sens des aiguilles d’une montre, à partir de la flèche du haut. Chaque part est une culture du cycle, et sa taille est le temps qu’elle occupe le champ. Arrivée au bout, la rotation recommence. Un point vert entre deux parts est un couvert de seigle semé entre deux cultures. Au centre, la note sur 100.',
  },
  'barres-priorites': {
    q: 'Comment lire les quatre priorités ?',
    text: 'Chaque barre est la note de la rotation sur une priorité, de 0 à 100. Elles sont classées par poids pour cette parcelle. Le trait noir est la note de votre rotation actuelle.',
  },
  calendrier: {
    q: 'D’où viennent les dates de semis et de récolte ?',
    text: 'Chaque culture est semée dès que le gel et la récolte d’avant le permettent, et récoltée quand elle a reçu assez de chaleur, avec le climat prévu pour le cycle. Un couvert est semé entre deux cultures quand l’intervalle est assez long. Une jachère est une position laissée sans culture vendue.',
  },
  'eau-suite': {
    q: 'Comment est comptée l’eau d’une rotation ?',
    text: 'L’appli simule l’eau du sol jour par jour sur la météo du cycle, avec les dates de semis et de récolte et les couverts de la rotation. Elle regarde l’eau que la rotation demande, celle qui manque, la part de la pluie gardée et l’eau laissée au semis suivant. Avec plusieurs modèles climatiques, la note est leur moyenne. La pression sur l’eau est celle de la ferme pendant le cycle.',
    sources: true,
  },
  'ravageurs-suite': {
    q: 'Comment sont comptés les ravageurs ?',
    text: `${PESTS} Une culture pour laquelle on n’a aucune donnée compte sans risque.`,
    sources: true,
  },
  precedent: { q: 'Que veut dire précédent pas mesuré ?', text: UNMEASURED },
  semences: {
    q: 'Pourquoi des semences à se procurer ?',
    text: 'Cette rotation contient des cultures dont la semence n’est pas dans votre réserve. Pour ne voir que vos semences, choisissez « Ma réserve uniquement » dans les réglages.',
  },

  // My field
  risques: {
    q: 'À quoi servent ces deux risques ?',
    text: 'Ce sont les points faibles de la section. Plus le risque d’érosion est haut, plus la priorité « Protection du sol » pèse dans la note du plan. Plus le risque de manque d’eau est haut, plus la priorité « Utilisation de l’eau » pèse. Le risque d’eau affiché ici est celui de la météo récente ; chaque cycle du plan a le sien, calculé sur son climat.',
  },
  'pression-eau': {
    q: 'De quoi est faite la pression sur l’eau ?',
    text: `${Object.values(WATER_COMPONENTS)
      .map((c) => `${c.label} : ${c.explain}`)
      .join(
        ' ',
      )} Une composante que rien ne mesure ici est laissée de côté : les autres se partagent son poids. Une parcelle irriguée ne garde que 40 % de cette pression.`,
    sources: true,
  },
  sol: {
    q: 'À quoi sert le sol ?',
    text: 'Le sol (de 0 à 30 cm) sert à garder, chez les jumeaux climatiques, les champs au même sol que le vôtre. Il vient de SoilGrids, ou de votre analyse de sol si vous l’avez saisie dans « Ma parcelle ».',
  },

  // My parcel
  parcelle: {
    q: 'À quoi servent ces informations ?',
    text: 'C’est tout ce que vous savez de cette section : ce qui pousse, ce qui a poussé, ses maladies, son eau et son sol. Le plan se recalcule dès que vous changez quelque chose.',
  },
  historique: { q: 'Pourquoi demander les années précédentes ?', text: HISTORY },
  maladies: { q: 'Pourquoi déclarer une maladie du sol ?', text: DISEASE },
  irrigation: {
    q: 'Que change une parcelle irriguée ?',
    text: 'Sur une parcelle irriguée, le risque de manque d’eau ne garde que 40 % de la pression sur l’eau, et le plan affiche l’irrigation dont chaque rotation a besoin.',
  },
  'analyse-sol': {
    q: 'À quoi sert mon analyse de sol ?',
    text: 'Si vous avez une analyse de sol, saisissez-la : elle remplace les valeurs de SoilGrids pour trouver, chez les jumeaux climatiques, les champs au même sol que le vôtre.',
  },

  // Climate and twins
  'climat-vise': { q: 'D’où vient le climat visé ?', text: CLIMATE_SOURCE, sources: true },
  jumeaux: { q: 'C’est quoi un jumeau climatique ?', text: `${TWIN} ${SIGMA}`, sources: true },

  // Sources
  sources: {
    q: 'Que trouve-t-on dans les sources ?',
    text: 'Toutes les données (NASA, cartes de cultures) et les méthodes de l’algorithme. « Pas encore calculé » veut dire que la valeur reste inconnue, sans chiffre d’exemple à la place. Ces données sont ouvertes ou gratuites ; celles des centres de données de la NASA demandent un compte Earthdata gratuit.',
  },

  // One topic per satellite measure of the field (« Pente », « Jours de sol nu »…)
  ...Object.fromEntries(
    Object.entries(FIELD_MEASURES).map(([key, m]) => [
      `mesure-${key}`,
      {
        q: `Que mesure « ${m.label} » ?`,
        text: `${m.explain} Source : ${m.source}. Cette mesure compte dans le risque d’érosion.`,
        sources: true,
      },
    ]),
  ),
};

/** Order matters on ties: specific intents first. */
export const INTENTS = [
  { keys: ['jumeau', 'analogue'], text: TWIN, sources: true },
  { keys: ['sigma', 'σ', 'ressemblance'], text: SIGMA, sources: true },
  {
    keys: ['plus au sud', 'sud'],
    text: 'Votre ferme va se réchauffer : le climat qu’elle aura ressemble à celui d’endroits un peu plus chauds aujourd’hui, souvent plus au sud. Plus le cycle est loin, plus il fait chaud, plus les jumeaux s’éloignent.',
  },
  { keys: ['modele', '10 ans', 'cmip6'], text: CLIMATE_SOURCE, sources: true },
  {
    keys: ['2011', '2024', 'comparer a'],
    text: 'La météo NASA POWER remonte à 1981, mais les cartes de cultures du Québec commencent en 2011. On compare donc les climats sur les années où l’on sait aussi ce que les jumeaux cultivaient.',
  },
  { keys: ['choisit', 'comment l appli', 'construit'], text: HOW_CHOSEN },
  { keys: ['garder', 'changer'], text: KEEP_OR_CHANGE },
  { keys: ['robustesse'], text: ROBUSTNESS },
  {
    keys: ['jachere', 'repos', 'vide'],
    text: 'Une jachère est une position laissée sans culture vendue. Avec les couverts de seigle, le sol reste couvert, ce qui plaît à la priorité protection du sol. Jamais deux jachères de suite. Si l’appli en propose souvent, les fiches des cultures sont à revoir avec un agronome.',
  },
  {
    keys: ['seigle', 'couvert', 'couverture'],
    text: 'Avec une culture par an, l’appli sème un seigle dans chaque intervalle assez long entre une récolte et le semis suivant. Le sol n’est pas nu l’hiver : moins d’érosion, plus de matière organique.',
  },
  { keys: ['pas mesure', 'precedent inconnu', 'inconnu', 'lacune'], text: UNMEASURED },
  {
    keys: ['delai', 'retour', 'revenir', 'trop tot'],
    text: 'Le délai de retour, c’est le nombre d’années sans une culture avant de la remettre au même endroit, pour que ses maladies et ses insectes disparaissent du sol. Par exemple, au moins 2 ans sans soya. Le minimum est obligatoire. La priorité ravageurs va plus loin : elle suit la pression de chaque maladie, nématode ou insecte du sol, année après année.',
    sources: true,
  },
  { keys: ['annees precedentes', 'historique', 'precedentes'], text: HISTORY },
  { keys: ['ravageur', 'nematode', 'insecte', 'pression'], text: PESTS, sources: true },
  { keys: ['maladie', 'hernie'], text: DISEASE },
  { keys: ['rotation actuelle', 'reference', 'actuelle'], text: CURRENT_ROTATION },
  { keys: ['erosion', 'protection du sol'], text: EROSION, sources: true },
  { keys: ['risque d eau', 'eau', 'secheresse'], text: WATER_RISK, sources: true },
  { keys: ['3d', 'vue', 'camembert', 'souleve'], text: DASHBOARD },
  {
    keys: ['donnee', 'source', 'nasa', 'vient', 'satellite', 'chiffre'],
    text: 'La météo de la ferme vient de NASA POWER, les modèles climatiques de NEX-GDDP-CMIP6, les jumeaux de la grille NASA POWER et des cartes de cultures (AAC, USDA), le sol de SoilGrids, la pente de Copernicus DEM et le sol nu de MODIS. L’eau utilise aussi les puits USGS, SMAP et ECOSTRESS quand ils sont disponibles. Tout est dans Détail et sources.',
    sources: true,
  },
  { keys: ['priorite', 'poids', 'critere'], text: PRIORITIES },
  {
    keys: ['bonjour', 'salut', 'allo', 'hello'],
    text: 'Bonjour ! Demandez-moi pourquoi l’appli propose une culture, ce qu’est un jumeau climatique ou d’où viennent les données.',
  },
];

export const normalize = (s) =>
  String(s ?? '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[’']/g, ' ');

const reply = ({ text, sources }) => ({ text, sources: !!sources });

const ENGLISH_INTENTS = {
  jumeau: ['twin', 'analogue'],
  sigma: ['sigma', 'similarity'],
  'plus au sud': ['south'],
  modele: ['model', '10 years', 'cmip6'],
  2011: ['2011', '2024', 'compare'],
  choisit: ['choose', 'chooses', 'chosen', 'build', 'select'],
  garder: ['keep', 'change'],
  robustesse: ['robustness'],
  jachere: ['fallow', 'rest', 'empty'],
  seigle: ['rye', 'cover crop', 'cover'],
  'pas mesure': ['unmeasured', 'unknown pre-crop', 'gap'],
  delai: ['return period', 'too soon'],
  'annees precedentes': ['previous years', 'history'],
  ravageur: ['pest', 'nematode', 'insect', 'pressure'],
  maladie: ['disease', 'clubroot'],
  'rotation actuelle': ['current rotation', 'reference'],
  erosion: ['erosion', 'soil protection'],
  'risque d eau': ['water', 'drought'],
  '3d': ['3d', 'view', 'pie chart', 'dashboard'],
  donnee: ['data', 'source', 'nasa', 'satellite'],
  priorite: ['priority', 'priorities', 'weight', 'criterion'],
  bonjour: ['hello', 'hi'],
};

/** What a « Demander à Rota » button shows: the question and its answer, or null. */
export function explain(topicId) {
  const topic = TOPICS[topicId];
  return topic ? { q: topic.q, ...reply(topic) } : null;
}

/**
 * Best answer for a free-text question: the topic that asks exactly this, else the intent with
 * the most keyword hits.
 */
export function answer(question) {
  const q = normalize(question).trim();
  const topic = Object.values(TOPICS).find(
    (topic) => normalize(topic.q).trim() === q || normalize(t(topic.q)).trim() === q,
  );
  if (topic) return reply(topic);
  let best = null;
  let score = 0;
  for (const intent of INTENTS) {
    const keys = [...intent.keys, ...(ENGLISH_INTENTS[intent.keys[0]] ?? [])];
    const hits = keys.filter((k) => q.includes(normalize(k))).length;
    if (hits > score) {
      score = hits;
      best = intent;
    }
  }
  return best ? reply(best) : FALLBACK;
}
