# Architecture

Field Shift suit une **architecture en quatre couches**. Chaque couche est un dossier à la racine du dépôt :

| Couche          | Dossier        | Rôle                                                                                                                                             |
| --------------- | -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Frontend**    | `frontend/`    | Ce que le fermier voit et touche : la page, les écrans, les composants, les styles. Aucun calcul métier, aucun appel réseau.                     |
| **Back end**    | `backend/`     | Le moteur qui calcule les résultats et son contrat : moteur de démo, client du vrai algorithme, schéma JSON, outils de vérification.             |
| **Application** | `application/` | Le contrôleur `app` que les écrans appellent, l'état de l'appli et les règles de structure (rotations, semences, santé du sol, surfaces, tracé). |
| **Data**        | `data/`        | Les données fixes (`reference/` : cultures, textes, ferme de démo, sources) et l'accès au réseau et à la sauvegarde (`access/`).                 |

**Aucune logique métier dans ce dépôt.** Scores, rendements, revenus, stress tests et données NASA de chaque section sont calculés par l'algorithme, branché derrière `backend/` (voir [`ALGO_CONTRACT.md`](ALGO_CONTRACT.md)). Le front ne calcule que la structure que le contrat lui confie (calendrier, cycles, délais de retour, décalage des sections, tracé de la ferme). Le moteur de démo (`backend/mockEngine.js`) ne fait qu'imiter l'algorithme avec des chiffres fictifs pour que l'interface tourne en attendant.

## Qui peut importer quoi

```
frontend/      présentation
   ↓
backend/       moteur + contrat
   ↓
application/   contrôleur, état, règles de structure
   ↓
data/          données fixes, réseau, sauvegarde
```

**Une couche n'importe que les couches en dessous d'elle**, jamais celles au-dessus. Deux précisions :

- Dans `frontend/`, **seul `main.js` importe `backend/`** : il crée le moteur et le donne à l'application (`createApp({ engine: createEngine() })`). Les écrans passent toujours par `app`.
- `frontend/` lit `data/reference/` (noms des cultures, libellés…) mais **jamais `data/access/`** : le réseau et la sauvegarde passent par l'application (`app.loadWeather`, `app.searchPlaces`, `app.setFarmLocation`…).

L'application appelle le moteur (`engine.evaluateFarm`…) **sans l'importer** : elle reçoit l'objet moteur de `main.js` et ne connaît que son interface (`backend/contract/types.js`). Le moteur de démo peut ainsi réutiliser les règles de l'application (délais de retour, calendrier) sans créer de cycle, et brancher le vrai algorithme ne change pas une ligne de l'application.

`tests/architecture.test.js` vérifie ces règles à chaque `npm test` : un import dans le mauvais sens fait échouer la CI.

## Arborescence

```
frontend/              COUCHE PRÉSENTATION
  index.html             page unique (racine de Vite)
  public/                fichiers copiés tels quels : favicon, logos, vidéo de la connexion
  main.js                point d'entrée : assemble les couches, rendu, événements, transitions
  router.js              routes en #/… (marche sur GitHub Pages sans configuration)
  actions.js             actions communes à tous les écrans (RotaAI, sélection…)
  screens/               un fichier par écran (14)
  ui/                    composants réutilisés : en-têtes, widgets, cartes Leaflet, vue 3D, textures, RotaAI
  styles/                tokens (base commune), base, composants, écrans
  lib/                   gabarit HTML sûr, ordre des blocs du tableau de bord
backend/               COUCHE BACK END : LE POINT DE BRANCHEMENT AVEC L'ALGO
  index.js               choisit le moteur (démo ou distant) selon VITE_ALGO_MODE
  mockEngine.js          moteur de démo : respecte le contrat, chiffres fictifs
  remoteEngine.js        appelle le vrai algo en HTTP
  contract/              schéma JSON du contrat, types JSDoc, cas de référence, exemples
  scripts/               génération des exemples, vérification d'un algo
application/           COUCHE APPLICATION
  app.js                 contrôleur : état, appels au moteur, réseau, navigation
  state/                 store observable, état initial, migration des anciennes sauvegardes
  rules/                 règles de structure, testées : rotations, semences, santé du sol, géométrie, tracé des sections
data/                  COUCHE DONNÉES
  reference/             cultures, types de ferme, priorités, ferme de démo, sources, réponses de RotaAI
  access/                météo (Open-Meteo), adresses (Nominatim), sauvegarde locale (localStorage)
tests/                 Vitest : une suite par sujet, plus le respect des couches
docs/                  documentation
```

## Où mettre du nouveau code

| Je veux ajouter…                                        | Où                                                                                    |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| un écran                                                | `frontend/screens/`, déclaré dans `frontend/screens/index.js` et `frontend/router.js` |
| un composant réutilisé                                  | `frontend/ui/`                                                                        |
| une opération qui appelle le moteur ou le réseau        | une méthode de `app` dans `application/app.js`                                        |
| une règle de calcul sans interface (rotation, surface…) | `application/rules/`, avec un test dans `tests/`                                      |
| un calcul agronomique (score, rendement, donnée NASA)   | nulle part ici : c'est le rôle de l'algorithme, à demander par le contrat             |
| une route du vrai algorithme                            | `backend/`, en commençant par le contrat (`docs/ALGO_CONTRACT.md`)                    |
| un service externe (API, stockage)                      | `data/access/`, appelé depuis `application/app.js`                                    |
| une donnée fixe (culture, texte, source)                | `data/reference/`                                                                     |

## Comment un écran marche

Un écran est un objet :

```js
export default {
  title: 'Rotation', // titre de l'onglet
  rota: 'rotation', // questions proposées par RotaAI sur cet écran
  onEnter(app, params) {}, // à l'arrivée (charger des données…)
  mount(app, params) {}, // après chaque rendu, pour ce qui vit hors du HTML (carte Leaflet) ; idempotent
  unmount(app) {}, // en quittant l'écran (détruire la carte)
  render(state, params, app) {
    // renvoie du HTML (gabarit html`` qui échappe tout)
    return html`<button data-action="place-crop" data-crop="ble">Blé</button>`;
  },
  actions: {
    // appelées par data-action, data-submit, data-change, data-input
    'place-crop': (app, el) =>
      app.updateFarm((farm) => {
        /* … */
      }),
  },
};
```

- **Rendu :** chaque changement d'état redessine l'écran courant. Simple, sans framework, assez rapide ici. Trois choses survivent au redessin : les champs marqués `data-preserve` (valeur et focus), le focus d'un élément `data-refocus` (avec un `id`), et les cartes Leaflet (`mapSlot()` dans `frontend/ui/leafletMap.js`, nœud DOM conservé et ré-attaché).
- **Blocs déplaçables :** un conteneur `data-sortable data-commit="action"` dont les enfants ont `data-sort-id` et une poignée `data-drag-handle` se réordonne à la souris, au doigt ou au clavier (`frontend/ui/dragSort.js`). Pendant un glissement, le rendu attend ; au relâchement, l'action reçoit `{ ids, moved }`. Le tableau de bord l'utilise, l'ordre est dans `prefs.dashboard` (`frontend/lib/dashboard.js`).
- **Transitions :** un changement de page passe par l'API View Transitions (fondu court ; glissement gauche/droite pendant les 5 étapes de configuration). L'en-tête et le bouton RotaAI ont leur propre `view-transition-name` et restent immobiles ; la lettre d'une section (`section-A`…) voyage du tableau de bord au menu de la section. Sans l'API ou avec « réduire les animations », l'écran change simplement.
- **Événements :** un seul écouteur par type sur la page ; il lit `data-action` (clic), `data-submit` (formulaire), `data-change` et `data-input`.
- **Données de la ferme :** toujours via `app.updateFarm(…)`, qui relance le calcul. Les écrans n'appellent jamais le moteur ni le réseau directement.
- **Sécurité :** le gabarit `html```  échappe toutes les valeurs. `raw()` seulement pour du texte de confiance.

## Le moteur

`app.engine` respecte l'interface du contrat (`evaluateFarm`, `proposeRotation`, `getFieldData`). Le moteur de démo et le moteur distant sont interchangeables : changer `VITE_ALGO_MODE` suffit (`backend/index.js`).

## Sauvegarde

L'utilisateur, la ferme, l'étape de configuration et les préférences d'affichage sont gardés dans le `localStorage` du navigateur (`field-shift:v2`, `data/access/storage.js`) ; l'application choisit ce qui est gardé (`persisted` dans `application/state/initialState.js`). C'est un confort de démo : rien n'est partagé, et l'appli marche aussi si le stockage est bloqué. Pour repartir de zéro : vider le stockage du site, ou se déconnecter.

## Outils

Vite sert la page depuis `frontend/` et suit les imports vers les autres couches (`vite.config.js`). `.env.local` reste à la racine du dépôt et la version de production va dans `dist/`.
