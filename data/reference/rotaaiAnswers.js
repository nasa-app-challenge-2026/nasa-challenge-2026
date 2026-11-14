/**
 * RotaAI, version "written in advance": questions are matched by keywords to
 * answers checked by the team. Reliable for the demo video and free to run.
 *
 * To plug a real language model later, keep this file as the fallback and see
 * docs/ROTAAI.md.
 */

/** Suggested questions, per screen. */
export const SUGGESTED = {
  tableau: [
    'C’est quoi l’assolement ?',
    'Pourquoi certaines années sont en ⚠ ?',
    'Que fait « Décaler mes sections » ?',
    'Comment lire la vue 3D ?',
  ],
  rotation: [
    'Pourquoi le soya avant le blé ?',
    'Pourquoi un cadenas sur la patate ?',
    'À quoi sert une couverture d’hiver ?',
    'Pourquoi le cycle est coupé ?',
  ],
  resultats: [
    'D’où vient le gain de rendement ?',
    'Pourquoi comparer au maïs en continu ?',
    'Pourquoi aucune racine profonde ?',
    'C’est quoi la charge de travail ?',
  ],
  champ: [
    'C’est quoi le NDVI ?',
    'D’où viennent ces données ?',
    'Pourquoi activer les capteurs ?',
    'Que fait « Signaler » ?',
  ],
  stress: [
    'Pourquoi la rotation résiste mieux au sec ?',
    'Pourquoi de l’orge à la place du maïs ?',
    'Comment les ravageurs sont touchés ?',
    'D’où viennent ces chiffres ?',
  ],
};

export const GREETING =
  'Bonjour ! Je suis RotaAI. Je vous explique les chiffres et les choix de l’appli. Posez une question ou choisissez-en une ci-dessous.';

const FALLBACK = {
  text: 'Je n’ai pas encore de réponse à ça. Essayez une des questions proposées, ou regardez Détail et sources pour les données et les études.',
  sources: true,
};

/** Order matters on ties: specific intents first. */
export const INTENTS = [
  {
    keys: ['soya avant', 'soya puis', 'apres le soya', 'soya et ble'],
    text: 'Le soya est une légumineuse : il laisse de l’azote dans le sol. Le blé qui suit en profite, et les études par satellite mesurent environ +8 % de rendement pour cet enchaînement (avec le blé de printemps). Attention : soya puis blé d’hiver donne l’inverse, environ −12 %.',
    sources: true,
  },
  {
    keys: ['cadenas', 'patate', 'delai', 'revenir', 'trop tot'],
    text: 'La patate attire des maladies et des insectes qui restent dans le sol plusieurs années. Il faut attendre au moins 4 ans avant d’en replanter au même endroit : c’est son délai de retour. Le cadenas apparaît quand votre cycle la ferait revenir trop tôt.',
  },
  {
    keys: ['couverture', 'hiver', 'seigle', 'trefle', 'radis'],
    text: 'Une couverture d’hiver pousse entre deux récoltes. Le sol n’est jamais nu : moins d’érosion, plus de matière organique. Le trèfle ajoute de l’azote, le radis fourrager casse le sol tassé, et le seigle protège bien contre l’érosion.',
    sources: true,
  },
  {
    keys: ['coupe', 'pas exactement', '12 ans', 'duree d analyse'],
    text: 'La ferme est analysée sur une seule durée, 12 ans par défaut. Si votre cycle ne rentre pas exactement (5 ans, par exemple), le dernier cycle s’arrête en route. Ce n’est pas une erreur : c’est la fin de la période d’analyse.',
  },
  {
    keys: ['decaler', 'decalage'],
    text: '« Décaler mes sections » change l’année de départ de chaque section dans son cycle, sans toucher à vos cultures. L’appli essaie les combinaisons et garde celle qui a le moins d’années déséquilibrées.',
  },
  {
    keys: ['assolement'],
    text: 'L’assolement, c’est découper la ferme en sections décalées dans le temps. La même année, A est en maïs, B en soya, C en blé : la ferme a toujours plusieurs cultures. Le revenu est plus stable et les machines servent chaque année.',
  },
  {
    keys: ['⚠', 'desequilibr', 'alerte', 'meme culture'],
    text: 'Une année est en ⚠ quand deux sections ont la même culture. Ça arrive quand les cycles n’ont pas la même durée : ils glissent l’un par rapport à l’autre. Ce n’est pas interdit, mais la ferme perd une partie de l’avantage de l’assolement.',
  },
  {
    keys: ['3d', 'vue', 'losange', 'souleve'],
    text: 'Chaque losange est une section. Sa texture montre la culture de l’année choisie avec le curseur : blé doré, maïs en rangs, soya en touffes. La section sélectionnée se soulève. Bougez le curseur pour voir la ferme changer d’année en année.',
  },
  {
    keys: ['sec', 'secheresse', 'resiste'],
    text: 'Des cultures différentes n’ont pas besoin d’eau au même moment, et un sol plus riche garde mieux l’eau. Les études sur plusieurs sites d’Amérique du Nord montrent que les rotations diversifiées perdent beaucoup moins de rendement les années sèches.',
    sources: true,
  },
  {
    keys: ['orge'],
    text: 'L’orge demande moins d’eau que le maïs et finit son cycle avant les chaleurs de l’été. La mettre à la place du maïs une année réduit le risque les années sèches.',
  },
  {
    keys: ['ravageur', 'insecte', 'maladie'],
    text: 'Beaucoup d’insectes et de maladies vivent sur une seule culture. Quand la culture change chaque année, ils ne trouvent plus de quoi se nourrir et leur nombre baisse. C’est un des premiers avantages de la rotation.',
  },
  {
    keys: ['gain', 'rendement', '%', 'pourcent'],
    text: 'Le gain vient de deux choses : l’effet de chaque enchaînement de cultures, mesuré par des études sur des millions de champs vus par satellite, et les conditions de votre section (pluie, chaleur, sol) d’après les données de la NASA. La fourchette montre l’écart entre bonnes et mauvaises années.',
    sources: true,
  },
  {
    keys: ['continu', 'monoculture', 'comparer'],
    text: 'Le maïs en continu est la pratique la plus courante sans rotation : c’est la référence la plus parlante. Il perd environ 4 % de rendement par rapport à une rotation, et beaucoup plus les années sèches.',
    sources: true,
  },
  {
    keys: ['racine', 'profond', 'tasse'],
    text: 'Les racines profondes (luzerne, radis fourrager) cassent le sol tassé et aident l’eau à descendre. Si votre rotation n’en a pas, un radis fourrager en couverture d’hiver est la façon la plus simple d’en ajouter.',
  },
  {
    keys: ['charge', 'travail', 'machine', 'equipement'],
    text: 'La charge de travail compte le nombre de cultures différentes, donc de semoirs, de récolteuses et de périodes de récolte. Plus de cultures, c’est un meilleur sol, mais un peu plus de travail.',
  },
  {
    keys: ['ndvi', 'vigueur'],
    text: 'Le NDVI est un indice de 0 à 1 calculé à partir des images satellites. Plus il est haut, plus les plantes sont vertes et en santé. On le tire des images HLS (Landsat et Sentinel-2) de la NASA.',
    sources: true,
  },
  {
    keys: ['capteur', 'sonde'],
    text: 'Les satellites estiment l’humidité du sol sur une grande zone. Si vous avez des sondes dans votre champ, l’appli utilise vos mesures à la place : c’est plus précis, surtout pour les grandes fermes.',
  },
  {
    keys: ['signaler', 'fausse', 'erreur'],
    text: 'Si une donnée vous semble fausse (il a beaucoup plus plu que ce qui est affiché, par exemple), « Signaler » nous le dit. On vérifie la donnée et on peut corriger le calcul de votre section.',
  },
  {
    keys: ['donnee', 'source', 'nasa', 'vient', 'satellite', 'chiffre'],
    text: 'Les données viennent de satellites de la NASA : NASA POWER pour la météo, GPM IMERG pour la pluie, SMAP pour l’humidité du sol, ECOSTRESS pour l’évapotranspiration et HLS pour la vigueur des plantes. Toutes les sources sont dans Détail et sources.',
    sources: true,
  },
  {
    keys: ['azote', 'legumineuse'],
    text: 'Les légumineuses (soya, luzerne, trèfle) vivent avec des bactéries dans leurs racines qui captent l’azote de l’air. Elles en laissent dans le sol pour la culture suivante : moins d’engrais à acheter.',
  },
  {
    keys: ['rotation', 'pourquoi changer', 'ca sert'],
    text: 'Changer de culture chaque année casse le cycle des ravageurs, nourrit le sol (surtout avec les légumineuses) et répartit le risque. Les études mesurent en général +5 à +10 % de rendement, et beaucoup moins de pertes les années sèches.',
    sources: true,
  },
  {
    keys: ['bonjour', 'salut', 'allo', 'hello'],
    text: 'Bonjour ! Demandez-moi pourquoi l’appli propose une culture, ce que veut dire un score, ou d’où viennent les données.',
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
