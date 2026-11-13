# Architecture du front end

```
index.html            page unique
src/
  main.js             point d'entrée : routeur, rendu, délégation des événements
  app.js              contrôleur : état, appels au moteur, navigation
  router.js           routes en #/… (marche sur GitHub Pages sans configuration)
  actions.js          actions communes à tous les écrans (RotaAI, sélection…)
  state/              store observable, état initial, sauvegarde locale
  algo/               LE POINT DE BRANCHEMENT AVEC L'ALGO
    index.js            choisit le moteur (démo ou distant) selon VITE_ALGO_MODE
    mockEngine.js       moteur de démo, respecte le contrat, chiffres fictifs
    remoteEngine.js     appelle le vrai algo en HTTP
    types.js            types JSDoc du contrat
  lib/                logique pure, testée : rotations, calendrier, santé du sol, HTML sûr
  data/               catalogue des cultures, ferme de démo, sources, textes
  rotaai/             réponses de RotaAI (écrites à l'avance)
  ui/                 composants réutilisés : en-têtes, widgets, vue 3D, textures, RotaAI
  screens/            un fichier par écran (13)
  styles/             tokens (base commune), base, composants, écrans
contract/             schéma JSON du contrat, exemples, cas de référence
scripts/              génération des exemples, vérification de l'algo
tests/                Vitest : rotations, contrat, RotaAI
```

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

- **Rendu :** chaque changement d'état redessine l'écran courant. Simple, sans framework, assez rapide ici. Trois choses survivent au redessin : les champs marqués `data-preserve` (valeur et focus), le focus d'un élément `data-refocus` (avec un `id`), et les cartes Leaflet (`mapSlot()` dans `src/ui/leafletMap.js`, nœud DOM conservé et ré-attaché).
- **Blocs déplaçables :** un conteneur `data-sortable data-commit="action"` dont les enfants ont `data-sort-id` et une poignée `data-drag-handle` se réordonne à la souris, au doigt ou au clavier (`src/ui/dragSort.js`). Pendant un glissement, le rendu attend ; au relâchement, l'action reçoit `{ ids, moved }`. Le tableau de bord l'utilise, l'ordre est dans `prefs.dashboard` (`src/lib/dashboard.js`).
- **Transitions :** un changement de page passe par l'API View Transitions (fondu court ; glissement gauche/droite pendant les 5 étapes de configuration). L'en-tête et le bouton RotaAI ont leur propre `view-transition-name` et restent immobiles ; la lettre d'une section (`section-A`…) voyage du tableau de bord au menu de la section. Sans l'API ou avec « réduire les animations », l'écran change simplement.
- **Événements :** un seul écouteur par type sur la page ; il lit `data-action` (clic), `data-submit` (formulaire), `data-change` et `data-input`.
- **Données de la ferme :** toujours via `app.updateFarm(…)`, qui relance le calcul. Les écrans n'appellent jamais le moteur directement.
- **Sécurité :** le gabarit `html```  échappe toutes les valeurs. `raw()` seulement pour du texte de confiance.

## Le moteur

`app.engine` respecte l'interface du contrat (`evaluateFarm`, `proposeRotation`, `getFieldData`). Le moteur de démo et le moteur distant sont interchangeables : changer `VITE_ALGO_MODE` suffit.

## Sauvegarde

L'utilisateur, la ferme et l'étape de configuration sont gardés dans le `localStorage` du navigateur (`field-shift:v2`). C'est un confort de démo : rien n'est partagé, et l'appli marche aussi si le stockage est bloqué. Pour repartir de zéro : vider le stockage du site, ou se déconnecter.
