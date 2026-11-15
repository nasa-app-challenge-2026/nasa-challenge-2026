/**
 * RotaAI, version "written in advance": questions are matched by keywords to
 * answers checked by the team. They explain the algorithm (field_shift v5.1) in
 * plain words. Reliable for the demo video and free to run.
 *
 * To plug a real language model later, keep this file as the fallback and see
 * docs/ROTAAI.md.
 */

/** Suggested questions, per screen. */
export const SUGGESTED = {
  tableau: [
    'C’est quoi un jumeau climatique ?',
    'Comment l’appli choisit mes cultures ?',
    'Pourquoi garder ou changer ?',
    'Comment lire la vue 3D ?',
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
    'D’où viennent ces données ?',
    'Que fait « Signaler » ?',
  ],
  plan: [
    'Pourquoi une jachère ?',
    'Pourquoi du seigle entre deux cultures ?',
    'C’est quoi la robustesse ?',
    'Que veut dire précédent pas mesuré ?',
  ],
  jumeaux: [
    'C’est quoi sigma ?',
    'Pourquoi des modèles climatiques après 10 ans ?',
    'Pourquoi les jumeaux sont plus au sud ?',
    'Pourquoi comparer à 2011-2024 ?',
  ],
};

export const GREETING =
  'Bonjour ! Je suis RotaAI. Je vous explique comment l’appli construit votre plan. Posez une question ou choisissez-en une ci-dessous.';

const FALLBACK = {
  text: 'Je n’ai pas encore de réponse à ça. Essayez une des questions proposées, ou regardez Détail et sources pour les données et les méthodes.',
  sources: true,
};

/** Order matters on ties: specific intents first. */
export const INTENTS = [
  {
    keys: ['jumeau', 'analogue'],
    text: 'Un jumeau climatique est un endroit qui a déjà connu, entre 2011 et 2024, le climat que votre ferme aura pendant un cycle. L’appli regarde ce que les fermiers y cultivent sur un sol comme le vôtre, et avec quel succès vu par satellite.',
    sources: true,
  },
  {
    keys: ['sigma', 'σ', 'ressemblance'],
    text: 'Sigma mesure à quel point deux climats se ressemblent, en tenant compte des écarts normaux d’une année à l’autre. 0 = identiques, moins de 2 = bon jumeau. Au-delà de 2, le climat visé n’existe nulle part et la recommandation est moins fiable.',
    sources: true,
  },
  {
    keys: ['plus au sud', 'sud'],
    text: 'Votre ferme va se réchauffer : le climat qu’elle aura ressemble à celui d’endroits un peu plus chauds aujourd’hui, souvent plus au sud. Plus le cycle est loin, plus il fait chaud, plus les jumeaux s’éloignent.',
  },
  {
    keys: ['modele', '10 ans', 'cmip6'],
    text: 'Pour les cycles qui finissent dans les 10 ans, l’appli prolonge la tendance des 40 dernières années de NASA POWER. Plus loin, une tendance en ligne droite ne suffit plus : elle applique à la vraie météo de la ferme le changement que prévoient plusieurs modèles climatiques, chacun séparément.',
    sources: true,
  },
  {
    keys: ['2011', '2024', 'comparer a'],
    text: 'La météo NASA POWER remonte à 1981, mais les cartes de cultures du Québec commencent en 2011. On compare donc les climats sur les années où l’on sait aussi ce que les jumeaux cultivaient.',
  },
  {
    keys: ['choisit', 'comment l appli', 'construit'],
    text: 'Pour chaque cycle, l’appli calcule le climat de votre ferme, trouve ses jumeaux, garde les cultures qui y poussent, puis essaie des milliers de suites de cultures. Elle écarte celles qui ne respectent pas le calendrier, le gel, les délais de retour ou ce qui se fait chez les jumeaux, et note les autres selon vos priorités.',
  },
  {
    keys: ['garder', 'changer'],
    text: 'Au premier cycle, la suite en place est votre rotation actuelle ; ensuite, celle choisie au cycle d’avant. On la garde si elle respecte les délais de retour, si ses cultures poussent encore chez les jumeaux et si sa note est à 5 points ou moins de la meilleure. Sinon, on change.',
  },
  {
    keys: ['robustesse'],
    text: 'La robustesse rejoue une suite de cultures dans tous les cycles suivants, avec leur climat et leurs jumeaux, et garde sa pire note. Si elle devient impossible plus tard, l’appli l’affiche.',
  },
  {
    keys: ['jachere', 'repos', 'vide'],
    text: 'Une jachère est une position laissée sans culture vendue. Avec les couverts de seigle, le sol reste couvert, ce qui plaît à la priorité protection du sol. Jamais deux jachères de suite. Si l’appli en propose souvent, les fiches des cultures sont à revoir avec un agronome.',
  },
  {
    keys: ['seigle', 'couvert', 'couverture'],
    text: 'Avec une culture par an, l’appli sème un seigle dans chaque intervalle assez long entre une récolte et le semis suivant. Le sol n’est pas nu l’hiver : moins d’érosion, plus de matière organique.',
  },
  {
    keys: ['pas mesure', 'precedent inconnu', 'inconnu', 'lacune'],
    text: 'Un précédent pas mesuré veut dire que l’enchaînement n’a pas été vu assez souvent dans les champs de la région (moins de 5 fois), ou qu’une des cultures manque aux cartes (foin, canola, sarrasin). Il compte comme une succession peu favorable, pour qu’une culture inconnue ne gagne pas parce qu’elle est inconnue, et l’appli le signale.',
  },
  {
    keys: ['delai', 'retour', 'revenir', 'trop tot'],
    text: 'Le délai de retour, c’est le nombre d’années sans une culture avant de la remettre au même endroit, pour que ses maladies et ses insectes disparaissent du sol. Par exemple, au moins 2 ans sans soya. Le minimum est obligatoire. La priorité ravageurs va plus loin : elle suit la pression de chaque maladie, nématode ou insecte du sol, année après année.',
    sources: true,
  },
  {
    keys: ['annees precedentes', 'historique', 'precedentes'],
    text: 'Les délais de retour se comptent aussi avec ce qui a poussé avant. Si vous avez eu du soya en 2025, l’appli ne peut pas en remettre en 2027. Elle demande autant d’années que le plus long délai de retour des cultures possibles.',
  },
  {
    keys: ['ravageur', 'nematode', 'insecte', 'pression'],
    text: 'La priorité ravageurs suit, année après année, la pression de chaque maladie, nématode ou insecte du sol : elle monte quand une de ses cultures hôtes pousse et baisse pendant les années sans hôte. Chaque culture est pénalisée par la pression qu’elle trouve en arrivant. Une maladie que vous déclarez part d’une pression pleine.',
    sources: true,
  },
  {
    keys: ['maladie', 'hernie'],
    text: 'Une maladie du sol que vous connaissez rend obligatoire son délai le plus long pour toutes ses cultures-hôtes. Par exemple, avec la hernie des crucifères, 7 ans sans canola, chou ni radis.',
  },
  {
    keys: ['rotation actuelle', 'reference', 'actuelle'],
    text: 'Votre rotation actuelle est prolongée cycle après cycle et notée avec les mêmes règles. Elle sert de comparaison : si elle ne respecte pas un délai de retour, l’appli vous le signale, sans la rejeter.',
  },
  {
    keys: ['erosion', 'protection du sol'],
    text: 'Le risque d’érosion combine la pente (la moitié), les jours de forte pluie et les jours de sol nu, vus par satellite. Plus il est haut, plus la priorité protection du sol pèse dans la note.',
    sources: true,
  },
  {
    keys: ['risque d eau', 'eau', 'secheresse'],
    text: 'Le risque d’eau est la pression sur l’eau de la ferme pendant le cycle : l’aridité de sa météo (pluie comparée à l’eau que l’air peut prendre), la baisse de la pluie d’été, le niveau des nappes et le stress mesuré (sol sec, stress des plantes) quand ces mesures existent. Une parcelle irriguée en garde 40 %. La note eau d’une suite de cultures vient d’une simulation de l’eau du sol jour par jour.',
    sources: true,
  },
  {
    keys: ['3d', 'vue', 'losange', 'souleve'],
    text: 'Chaque forme est une section. Sa texture montre la culture de l’année choisie avec le curseur. La section sélectionnée se soulève. Bougez le curseur pour suivre le plan année après année.',
  },
  {
    keys: ['signaler', 'fausse', 'erreur'],
    text: 'Si une donnée vous semble fausse, « Signaler » nous le dit. On vérifie la donnée et on peut corriger le calcul de votre section.',
  },
  {
    keys: ['donnee', 'source', 'nasa', 'vient', 'satellite', 'chiffre'],
    text: 'La météo de la ferme vient de NASA POWER, les modèles climatiques de NEX-GDDP-CMIP6, les jumeaux de la grille NASA POWER et des cartes de cultures (AAC, USDA), le sol de SoilGrids, la pente de Copernicus DEM et le sol nu de MODIS. L’eau utilise aussi les puits USGS, SMAP et ECOSTRESS quand ils sont disponibles. Tout est dans Détail et sources.',
    sources: true,
  },
  {
    keys: ['priorite', 'poids', 'critere'],
    text: 'Vous classez quatre priorités : le rendement, l’utilisation de l’eau, la protection du sol et les ravageurs. La première pèse le plus. Chaque suite de cultures reçoit une note sur chacune, puis leur moyenne pondérée. L’appli donne aussi plus de poids à la protection du sol et à l’eau si votre champ y est fragile.',
  },
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

/** Best answer for a free-text question: the intent with the most keyword hits. */
export function answer(question) {
  const q = normalize(question);
  let best = null;
  let score = 0;
  for (const intent of INTENTS) {
    const hits = intent.keys.filter((k) => q.includes(normalize(k))).length;
    if (hits > score) {
      score = hits;
      best = intent;
    }
  }
  return best ? { text: best.text, sources: !!best.sources } : FALLBACK;
}
