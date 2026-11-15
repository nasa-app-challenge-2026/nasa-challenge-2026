# Architecture

Field Shift suit une **architecture en quatre couches**. Chaque couche est un dossier à la racine du dépôt :

| Couche          | Dossier        | Rôle                                                                                                                                                                                                                                |
| --------------- | -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Frontend**    | `frontend/`    | Ce que le fermier voit et touche : la page, les écrans, les composants, les styles. Aucun calcul métier, aucun appel réseau.                                                                                                        |
| **Back end**    | `backend/`     | Tout ce qui touche l'algorithme : le **serveur Python (FastAPI)** qui le contient (`api/`), le client HTTP que le front utilise pour l'appeler, le contrat (schéma JSON, types, exemples) et son script de vérification. |
| **Application** | `application/` | Le contrôleur `app` que les écrans appellent, l'état de l'appli, les règles des entrées du fermier (étape 1) et la lecture du plan pour les écrans.                                                                                 |
| **Data**        | `data/`        | Les données fixes d'affichage (`reference/` : noms et couleurs des cultures, maladies du sol, critères, textes, ferme de démo, sources) et l'accès au réseau et à la sauvegarde (`access/`).                                        |

**La logique métier vit dans `api/field_shift/algorithm/` et nulle part ailleurs.** Les écrans affichent le plan que le serveur renvoie ; l'application ne fait que proposer au fermier des choix valides (cycle, fréquence, horizon, ordre des critères, réserve, parcelles) et retrouver une année ou un cycle dans le plan. Même les poids des critères viennent du plan. Le fonctionnement de l'algorithme est décrit dans [`ALGORITHME.md`](ALGORITHME.md).

Le front (JavaScript, dans le navigateur) et le serveur (Python) sont **deux programmes** : ils ne se parlent qu'en HTTP, selon le contrat `POST /plan` ([`ALGO_CONTRACT.md`](ALGO_CONTRACT.md)). Pour les lancer ensemble, voir le [`README`](../README.md).

## Qui peut importer quoi

```
frontend/      présentation
   ↓
backend/       client HTTP du serveur, contrat
   ↓
application/   contrôleur, état, règles des entrées, lecture du plan
   ↓
data/          données fixes, réseau, sauvegarde
```

**Une couche n'importe que les couches en dessous d'elle**, jamais celles au-dessus. Deux précisions :

- Dans `frontend/`, **seul `main.js` importe `backend/`** : il crée le moteur et le donne à l'application (`createApp({ engine: createEngine() })`). Les écrans passent toujours par `app`.
- `frontend/` lit `data/reference/` (noms des cultures, critères, libellés…) mais **jamais `data/access/`** : le réseau et la sauvegarde passent par l'application (`app.loadWeather`, `app.searchPlaces`, `app.setFarmLocation`…).

L'application appelle le moteur (`engine.planFarm`) **sans l'importer** : elle reçoit l'objet moteur de `main.js` et ne connaît que son interface (`backend/contract/types.js`).

Le serveur Python (`api/`) n'entre pas dans ce graphe : le JavaScript ne l'importe pas, il l'appelle en HTTP. Il a ses propres couches, dans le même esprit (`api → services → contract, data_access → algorithm → reference`), décrites dans son [`README`](../api/README.md).

`tests/architecture.test.js` (JavaScript) et `api/tests/test_architecture.py` (Python) vérifient ces règles à chaque lancement des tests : un import dans le mauvais sens fait échouer les tests.

## Arborescence

```
frontend/              COUCHE PRÉSENTATION
  index.html             page unique (racine de Vite)
  public/                fichiers copiés tels quels : favicon, logos, vidéo de la connexion
  main.js                point d'entrée : assemble les couches, rendu, événements, transitions
  router.js              routes en #/… (marche sur GitHub Pages sans configuration)
  actions.js             actions communes à tous les écrans (RotaAI, sélection, année, cycle)
  screens/               un fichier par écran
  ui/                    composants : en-têtes, widgets, plan (chaîne, calendrier, critères), éditeurs des entrées, cartes Leaflet, vue 3D, textures, RotaAI
  styles/                tokens (base commune), base, composants, écrans
  lib/                   gabarit HTML sûr, ordre des blocs du tableau de bord
backend/               COUCHE BACK END
  index.js               donne le moteur à l'appli : le client du serveur, à l'adresse VITE_ALGO_URL
  remoteEngine.js        client HTTP du serveur (POST /plan) et erreurs lisibles
  contract/              schéma JSON du contrat 2.0, types JSDoc, exemples (entrées et plans)
  scripts/               check-algo.mjs : vérifie qu'un serveur respecte le contrat (npm run check:algo)
api/                   LE SERVEUR (Python, FastAPI) : voir api/README.md
  field_shift/algorithm/     L'ALGORITHME (étapes 2 à 10), sans code web ni donnée : voir docs/ALGORITHME.md
  field_shift/contract/      le format d'échange (Pydantic) et les deux traducteurs
  field_shift/services/      PlanService et RankingService : une requête de bout en bout
  field_shift/api/           l'application FastAPI : routes et réglages
  field_shift/data_access/   les services de données (NASA POWER, NEX-GDDP-CMIP6, SoilGrids, MODIS, cartes de cultures), gardés sur disque
  field_shift/reference/     fiches des cultures, délais de retour, critères
  water_use/                 le bilan d'eau du sol (note eau d'une rotation)
  tests/                     pytest : l'algorithme contre sa référence, les sources (services simulés), l'API, le contrat, les couches
application/           COUCHE APPLICATION
  app.js                 contrôleur : état, appel au moteur, réseau, navigation
  state/                 store observable, état initial, migration des sauvegardes de la version 1
  rules/                 étape 1 (cycle et horizon, priorités, réserve, entrées des sections), lecture du plan, géométrie, tracé
data/                  COUCHE DONNÉES
  reference/             cultures (noms, couleurs), maladies du sol, critères, réglages des formulaires, mesures, ferme de démo, sources, RotaAI
  access/                météo du jour Open-Meteo (tableau de bord), adresses (Nominatim), sauvegarde locale
tests/                 Vitest : une suite par sujet, le contrat côté front, le respect des couches
docs/                  documentation
```

## Les écrans

| Route                  | Écran              | Contenu                                                                                                                                      |
| ---------------------- | ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `#/connexion`          | Connexion          | compte de démo                                                                                                                               |
| `#/type-de-ferme`      | Type de ferme      | grandes cultures (les autres types arrivent)                                                                                                 |
| `#/localisation`       | Localisation       | point de la ferme (météo NASA POWER, centre des jumeaux)                                                                                     |
| `#/tracer`             | Tracer la ferme    | contour et sections                                                                                                                          |
| `#/cultures`           | Mes cultures       | culture en place, mois de récolte, rotation actuelle de chaque section ; réserve de semences                                                 |
| `#/temps`              | Cycle et horizon   | cycle, fréquence, horizon                                                                                                                    |
| `#/priorites`          | Priorités          | classement des 9 critères, bétail, équipement                                                                                                |
| `#/tableau`            | Tableau de bord    | météo du jour, vue 3D, toute la ferme par année, une carte par section (cycle, garder/changer, note), curseur des années                     |
| `#/section/A/parcelle` | Ma parcelle        | toutes les entrées de la section, années précédentes, maladies, irrigation, analyse de sol                                                   |
| `#/section/A/champ`    | Mon champ          | risques érosion et eau, mesures satellites, sol                                                                                              |
| `#/section/A/plan`     | Plan par cycle     | décision, note contre la rotation actuelle, chaîne et calendrier, lacunes, semences, cultures retirées, 9 critères, alternatives, robustesse |
| `#/section/A/jumeaux`  | Climat et jumeaux  | climat visé du cycle, jumeaux et carte (une flèche par modèle)                                                                               |
| `#/sources`            | Détail et sources  | données et méthodes, réelles ou fictives                                                                                                     |
| `#/compte`             | Compte et réglages | profil, ferme, semences, cycle et horizon, priorités                                                                                         |

## Où mettre du nouveau code

| Je veux ajouter…                                                       | Où                                                                                                                                                              |
| ---------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| un écran                                                               | `frontend/screens/`, déclaré dans `frontend/screens/index.js` et `frontend/router.js`                                                                           |
| un composant réutilisé                                                 | `frontend/ui/`                                                                                                                                                  |
| une opération qui appelle le moteur ou le réseau                       | une méthode de `app` dans `application/app.js`                                                                                                                  |
| une règle des entrées du fermier ou de lecture du plan                 | `application/rules/`, avec un test dans `tests/`                                                                                                                |
| un calcul agronomique (climat, jumeaux, note, délais…)                 | `api/field_shift/algorithm/`, avec un test dans `api/tests/` (voir `ALGORITHME.md`)                                                       |
| une donnée agronomique (fiche de culture, délai de retour, critère)    | `api/field_shift/reference/`                                                                                                                         |
| un champ du plan                                                       | `api/field_shift/contract/` (modèle et traducteur), puis le schéma, `ALGO_CONTRACT.md` et les exemples (`python -m field_shift.tools.make_examples`) |
| un service externe lu par le serveur (NASA POWER…)                     | `api/field_shift/data_access/`                                                                                                                       |
| un service externe lu par le front (adresses, météo du jour, stockage) | `data/access/`, appelé depuis `application/app.js`                                                                                                              |
| une donnée fixe d'affichage (nom, couleur, texte, source)              | `data/reference/` (les identifiants sont ceux du contrat : `tests/contract.test.js` le vérifie)                                                                 |

## Comment un écran marche

Un écran est un objet :

```js
export default {
  title: 'Plan par cycle', // titre de l'onglet
  rota: 'plan', // questions proposées par RotaAI sur cet écran
  onEnter(app, params) {}, // à l'arrivée (charger des données…)
  mount(app, params) {}, // après chaque rendu, pour ce qui vit hors du HTML (carte Leaflet) ; idempotent
  unmount(app) {}, // en quittant l'écran (détruire la carte)
  render(state, params, app) {
    // renvoie du HTML (gabarit html`` qui échappe tout)
    return html`<button data-action="set-cycle" data-cycle="2">Cycle 2</button>`;
  },
  actions: {
    // appelées par data-action, data-submit, data-change, data-input
    'toggle-irrigated': (app, el) =>
      app.updateSection(el.dataset.id, (s) => (s.irrigated = !s.irrigated)),
  },
};
```

- **Rendu :** chaque changement d'état redessine l'écran courant. Simple, sans framework, assez rapide ici. Trois choses survivent au redessin : les champs marqués `data-preserve` (valeur et focus), le focus d'un élément `data-refocus` (avec un `id`), et les cartes Leaflet (`mapSlot()` dans `frontend/ui/leafletMap.js`, nœud DOM conservé et ré-attaché).
- **Blocs déplaçables :** un conteneur `data-sortable data-commit="action"` dont les enfants ont `data-sort-id` et une poignée `data-drag-handle` se réordonne à la souris, au doigt ou au clavier (`frontend/ui/dragSort.js`). Le tableau de bord l'utilise, l'ordre est dans `prefs.dashboard` (`frontend/lib/dashboard.js`).
- **Transitions :** un changement de page passe par l'API View Transitions (fondu court ; glissement gauche/droite pendant les 6 étapes de configuration). Sans l'API ou avec « réduire les animations », l'écran change simplement.
- **Événements :** un seul écouteur par type sur la page ; il lit `data-action` (clic), `data-submit` (formulaire), `data-change` et `data-input`.
- **Données de la ferme :** toujours via `app.updateFarm(…)` ou `app.updateSection(id, …)`, qui relancent le plan. Les écrans n'appellent jamais le moteur ni le réseau directement.
- **Sécurité :** le gabarit `html```  échappe toutes les valeurs. `raw()` seulement pour du texte de confiance.

## Le moteur

`app.engine` respecte l'interface du contrat : `{ name, planFarm(farmInput) → Promise<FarmPlan> }`. Le moteur est le client du serveur Python (`backend/remoteEngine.js`) : il envoie la ferme à `POST {VITE_ALGO_URL}/plan` et rend le plan. Le serveur télécharge la météo NASA POWER du lieu (une fois par lieu, gardée en mémoire), lance l'algorithme et répond ; sans réseau, il utilise une météo fictive et le plan le dit (`meta.sources.farmWeather`). Si le serveur ne répond pas, l'écran affiche l'erreur avec un bouton « Réessayer ».

`VITE_ALGO_URL` vaut `http://localhost:8000` avec `npm run dev` et n'a pas de valeur par défaut en production : le site publié doit être configuré avec l'adresse du serveur.

## Sauvegarde

L'utilisateur, la ferme, l'étape de configuration et les préférences d'affichage sont gardés dans le `localStorage` du navigateur (`field-shift:v2`, `data/access/storage.js`) ; l'application choisit ce qui est gardé (`persisted` dans `application/state/initialState.js`). Une ferme sauvée par la version 1 (rotation éditée à la main) est convertie au chargement (`application/state/migrate.js`) : le tracé, les surfaces et les cultures en place sont gardés, l'ancienne rotation devient la rotation actuelle. Pour repartir de zéro : vider le stockage du site, ou se déconnecter.

## Outils

Vite sert la page depuis `frontend/` et suit les imports vers les autres couches (`vite.config.js`). `.env.local` reste à la racine du dépôt et la version de production va dans `dist/`.

Le serveur se lance à part, depuis `api/` (voir son [`README`](../api/README.md)). Il n'y a pas de CI : avant de pousser, lancez vous-même `npm run lint`, `npm test` et `npm run build` pour le front, `ruff check .` et `pytest` (dans `api/`) pour le serveur.
