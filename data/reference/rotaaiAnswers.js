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
    'Que veut dire précédent inconnu ?',
  ],
  jumeaux: [
    'C’est quoi sigma ?',
    'Pourquoi des modèles climatiques après 10 ans ?',
    'Pourquoi les jumeaux sont plus au sud ?',
    'Pourquoi comparer à 2011-2024 ?',
  ],
  feux: [
    'Que faire si un feu approche ?',
    'C’est quoi le dNBR ?',
    'Pourquoi une couverture après un feu ?',
    'C’est quoi un point chaud ?',
    'Pourquoi des feux sur des terres agricoles ?',
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
    keys: ['dnbr', 'nbr', 'gravite'],
    text: 'Le NBR compare deux lumières invisibles à l’œil : l’infrarouge proche, que renvoient les plantes vertes, et l’infrarouge moyen, que renvoient le sol nu et les cendres. Le dNBR, c’est la baisse du NBR entre une image prise juste avant le feu et une prise juste après. Sous 0,1 : pas de brûlage. De 0,1 à 0,27 : faible. Au-delà de 0,44 : fort. Une récolte fait aussi baisser le NBR, d’où l’importance de dates rapprochées.',
    sources: true,
  },
  {
    keys: ['apres un feu', 'apres le feu', 'couverture apres', 'sol brule'],
    text: 'Après un feu, le sol est à nu : le vent et la pluie l’emportent, et il a perdu une partie de son azote et de sa matière organique. Une culture de couverture (seigle d’automne, avoine au printemps, trèfle) le protège tout de suite, et ses racines nourrissent la vie du sol. Le trèfle refait aussi de l’azote pour la culture suivante.',
  },
  {
    keys: [
      'feu approche',
      'que faire si un feu',
      'feu actif',
      'feu proche',
      'pendant un feu',
      'pendant le feu',
      'coupe-feu',
      'coupe feu',
    ],
    text: 'Quand un gros feu brûle à moins de 25 km, l’appli classe vos sections de la plus proche du feu à la plus loin. Côté feu : récoltez d’abord les céréales mûres et passez le disque sur une bande de chaume, car la terre nue arrête un feu d’herbe. Une culture verte brûle mal. Pour la rotation, elle propose un couvert de seigle sur les sections côté feu : il reverdit tôt au printemps, quand les feux de chaume sont fréquents. Le reste ne change pas : si le feu touche une section, l’appli mesure le brûlage après coup et propose de changer la prochaine culture de sa rotation.',
  },
  {
    keys: ['point chaud', 'points chauds', 'hotspot', 'viirs', 'modis', 'firms'],
    text: 'Un point chaud, c’est un pixel où un satellite de la NASA (MODIS ou VIIRS) a vu une chaleur anormale : souvent un feu, parfois une usine ou une torchère. Les pixels font de 375 m à 1 km : un point chaud près d’une section ne prouve pas qu’elle a brûlé. C’est pour ça que l’appli mesure ensuite le brûlage avec les images HLS, à 30 m.',
    sources: true,
  },
  {
    keys: ['terres agricoles', 'feux agricoles', 'brulage', 'chaume', 'feu de champ'],
    text: 'Beaucoup de feux près des fermes sont des brûlages de chaume, d’andains ou de fossés, au printemps et à l’automne. Ils sont plus petits que les feux de forêt, mais ils laissent aussi le sol à nu. Le type de végétation de chaque point chaud vient de la carte des combustibles du Canada.',
  },
  {
    keys: ['danger', 'risque d incendie', 'indice foret'],
    text: 'Le danger d’incendie du jour vient des prévisions de Ressources naturelles Canada : bas, modéré, élevé, très élevé ou extrême. Il combine la météo (chaleur, vent, sécheresse) et l’état de la végétation. À partir d’« élevé », évitez les brûlages et suivez les avis de votre province.',
    sources: true,
  },
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
    text: 'Une jachère est une position laissée sans culture vendue. Avec les couverts de seigle, le sol reste couvert, ce qui plaît aux critères eau et érosion. Jamais deux jachères de suite. Si l’appli en propose souvent, les fiches des cultures sont à revoir avec un agronome.',
  },
  {
    keys: ['seigle', 'couvert', 'couverture'],
    text: 'Avec une culture par an, l’appli sème un seigle dans chaque intervalle assez long entre une récolte et le semis suivant. Le sol n’est pas nu l’hiver : moins d’érosion, plus de matière organique.',
  },
  {
    keys: ['precedent inconnu', 'inconnu', 'lacune'],
    text: 'Un précédent inconnu veut dire que l’enchaînement a été vu chez les jumeaux, mais dans moins de 20 champs : on ne peut pas mesurer s’il aide la culture suivante. Il compte neutre dans la note, et l’appli le signale.',
  },
  {
    keys: ['delai', 'retour', 'revenir', 'trop tot'],
    text: 'Le délai de retour, c’est le nombre d’années sans une culture avant de la remettre au même endroit, pour que ses maladies et ses insectes disparaissent du sol. Par exemple, au moins 2 ans sans soya. Le minimum est obligatoire ; le délai conseillé compte dans le critère ravageurs.',
    sources: true,
  },
  {
    keys: ['annees precedentes', 'historique', 'precedentes'],
    text: 'Les délais de retour se comptent aussi avec ce qui a poussé avant. Si vous avez eu du soya en 2025, l’appli ne peut pas en remettre en 2027. Elle demande autant d’années que le plus long délai de retour des cultures possibles.',
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
    keys: ['erosion'],
    text: 'Le risque d’érosion combine la pente (la moitié), les jours de forte pluie et les jours de sol nu, vus par satellite. Plus il est haut, plus le critère érosion pèse dans la note.',
    sources: true,
  },
  {
    keys: ['risque d eau', 'eau', 'secheresse'],
    text: 'Le risque d’eau combine le stress des plantes en été, la sécheresse des racines, la baisse de pluie prévue pour le cycle et la baisse des réserves d’eau de la région. Une parcelle irriguée en garde 40 %.',
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
    text: 'La météo de la ferme vient de NASA POWER. Le reste viendra de SoilGrids, des cartes de cultures (USDA, AAC) et de satellites NASA (HLS, SRTM, GPM IMERG, MODIS, ECOSTRESS, SMAP, GRACE-FO) ; pour l’instant ces données sont des exemples. Tout est dans Détail et sources.',
    sources: true,
  },
  {
    keys: ['priorite', 'poids', 'critere'],
    text: 'Vous classez les critères qui comptent ; le premier pèse le plus. Un critère non classé garde un petit poids. L’appli donne aussi plus de poids à l’érosion et à l’eau si votre champ y est fragile.',
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
