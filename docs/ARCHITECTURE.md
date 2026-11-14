# Architecture

Field Shift suit une **architecture en quatre couches**. Chaque couche est un dossier à la racine du dépôt :

| Couche          | Dossier        | Rôle                                                                                                                                                                   |
| --------------- | -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Frontend**    | `frontend/`    | Ce que le fermier voit et touche : la page, les écrans, les composants, les styles. Aucun calcul métier, aucun appel réseau.                                           |
| **Back end**    | `backend/`     | **L'algorithme Field Shift** (`backend/algorithm/`), le moteur qui l'expose à l'appli, le client d'un algorithme distant, le contrat et ses outils.                    |
| **Application** | `application/` | Le contrôleur `app` que les écrans appellent, l'état de l'appli, les règles des entrées du fermier (étape 1) et la lecture du plan pour les écrans.                    |
| **Data**        | `data/`        | Les données fixes (`reference/` : cultures et fiches, délais de retour, critères, textes, ferme de démo, sources) et l'accès au réseau et à la sauvegarde (`access/`). |

**La logique métier vit dans `backend/algorithm/` et nulle part ailleurs.** Les écrans affichent le plan que l'algorithme renvoie (voir [`ALGO_CONTRACT.md`](ALGO_CONTRACT.md)) ; l'application ne fait que valider les entrées du fermier (cycle, fréquence, horizon, classement des critères, réserve, parcelles) et retrouver une année ou un cycle dans le plan. Le fonctionnement de l'algorithme est décrit dans [`ALGORITHME.md`](ALGORITHME.md).

## Qui peut importer quoi

```
frontend/      présentation
   ↓
backend/       algorithme + moteur + contrat
   ↓
application/   contrôleur, état, règles des entrées, lecture du plan
   ↓
data/          données fixes, réseau, sauvegarde
```

**Une couche n'importe que les couches en dessous d'elle**, jamais celles au-dessus. Deux précisions :

- Dans `frontend/`, **seul `main.js` importe `backend/`** : il crée le moteur et le donne à l'application (`createApp({ engine: createEngine() })`). Les écrans passent toujours par `app`.
- `frontend/` lit `data/reference/` (noms des cultures, critères, libellés…) mais **jamais `data/access/`** : le réseau et la sauvegarde passent par l'application (`app.loadWeather`, `app.searchPlaces`, `app.setFarmLocation`…).

L'application appelle le moteur (`engine.planFarm`) **sans l'importer** : elle reçoit l'objet moteur de `main.js` et ne connaît que son interface (`backend/contract/types.js`). L'algorithme, lui, réutilise les règles de l'étape 1 de l'application (`TimeSettings`, poids du classement) et lit la météo NASA POWER par `data/access/nasaPower.js`, sans créer de cycle.

`tests/architecture.test.js` vérifie ces règles à chaque `npm test` : un import dans le mauvais sens fait échouer la CI.

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
  algorithm/             L'ALGORITHME (port de field_shift.py v5.1) : voir docs/ALGORITHME.md
  algorithmEngine.js     moteur par défaut : météo NASA POWER de la ferme + algorithme, dans le navigateur
  remoteEngine.js        appelle un algorithme distant en HTTP (POST /plan)
  index.js               choisit le moteur selon VITE_ALGO_MODE et VITE_FARM_WEATHER
  contract/              schéma JSON du contrat 2.0, types JSDoc, cas de référence, exemples
  scripts/               génération des exemples, vérification d'un algorithme distant
application/           COUCHE APPLICATION
  app.js                 contrôleur : état, appel au moteur, réseau, navigation
  state/                 store observable, état initial, migration des sauvegardes de la version 1
  rules/                 étape 1 (cycle et horizon, priorités, réserve, entrées des sections), lecture du plan, géométrie, tracé
data/                  COUCHE DONNÉES
  reference/             cultures et fiches, délais de retour et maladies, critères, réglages, mesures, ferme de démo, sources, RotaAI
  access/                météo NASA POWER (plan) et Open-Meteo (tableau de bord), adresses (Nominatim), sauvegarde locale
tests/                 Vitest : une suite par sujet, l'algorithme contre la référence Python, le respect des couches
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

| Je veux ajouter…                                         | Où                                                                                    |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| un écran                                                 | `frontend/screens/`, déclaré dans `frontend/screens/index.js` et `frontend/router.js` |
| un composant réutilisé                                   | `frontend/ui/`                                                                        |
| une opération qui appelle le moteur ou le réseau         | une méthode de `app` dans `application/app.js`                                        |
| une règle des entrées du fermier ou de lecture du plan   | `application/rules/`, avec un test dans `tests/`                                      |
| un calcul agronomique (climat, jumeaux, note, délais…)   | `backend/algorithm/`, avec un test dans `tests/algorithm/` (voir `ALGORITHME.md`)     |
| un champ du plan                                         | `backend/algorithm/report/PlanSerializer.js`, puis le schéma et `ALGO_CONTRACT.md`    |
| un service externe (API, stockage)                       | `data/access/`, appelé depuis `application/app.js` ou `backend/algorithmEngine.js`    |
| une donnée fixe (culture, fiche, critère, texte, source) | `data/reference/`                                                                     |

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

`app.engine` respecte l'interface du contrat : `{ name, planFarm(farmInput) → Promise<FarmPlan> }`. Le moteur par défaut (`backend/algorithmEngine.js`) télécharge une fois la météo NASA POWER de la ferme, puis fait tourner l'algorithme dans le navigateur ; s'il n'y a pas de réseau, il utilise la météo fictive et le plan le dit. `VITE_ALGO_MODE=remote` le remplace par un serveur, sans toucher aux écrans.

## Sauvegarde

L'utilisateur, la ferme, l'étape de configuration et les préférences d'affichage sont gardés dans le `localStorage` du navigateur (`field-shift:v2`, `data/access/storage.js`) ; l'application choisit ce qui est gardé (`persisted` dans `application/state/initialState.js`). Une ferme sauvée par la version 1 (rotation éditée à la main) est convertie au chargement (`application/state/migrate.js`) : le tracé, les surfaces et les cultures en place sont gardés, l'ancienne rotation devient la rotation actuelle. Pour repartir de zéro : vider le stockage du site, ou se déconnecter.

## Outils

Vite sert la page depuis `frontend/` et suit les imports vers les autres couches (`vite.config.js`). `.env.local` reste à la racine du dépôt et la version de production va dans `dist/`.
