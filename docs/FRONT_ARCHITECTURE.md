# Architecture du front end

```
index.html            page unique
src/
  main.js             point d'entrée : routeur, rendu, délégation des événements
  app.js              contrôleur : état, appels au moteur, navigation
  router.js           routes en #/… (marche sur GitHub Pages sans configuration)
  actions.js          actions communes à tous les écrans (RotaAI, sélection…)
  fireController.js   données des feux dans l'état : chargement, caches, feu choisi
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
  screens/            un fichier par écran (14)
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

## Feux près de la ferme

Un petit bloc `fire` du tableau de bord, et sa page de détail `src/screens/feux.js` (`#/feux`, pas dans le menu principal : on y arrive par le bloc). Calme par défaut : « Aucun risque pour le moment », sauf gros feu actif cette semaine ou danger d'incendie élevé (`fireStatus`) ; rayon fixe de 25 km sur 10 ans, partagé avec le bloc ; feux de plus de 12 mois rangés dans des archives repliées ; seules les sections touchées ont une carte (quoi faire, rotation proposée, « Pourquoi ? » replié). Pendant une alerte (`fireStatus` = `alert`), `alertAdvice` classe les sections de la plus proche du feu à la plus loin : ce qui est au champ selon la saison (`fieldFuel`, d'après `currentCrop`), les travaux de la semaine, et pour les sections côté feu une couverture d'hiver (seigle, sinon trèfle) prise dans la réserve de semences (`fireCoverAdvice`), sans toucher aux délais de retour, à appliquer et comparer dans l'explorateur ; l'exemple réel montre ce que l'appli aurait conseillé pendant son feu. Tout passe par le navigateur, sans clé ni serveur : SCIFV de Ressources naturelles Canada (points chauds NASA, zones brûlées, danger), HLS de la NASA sur Microsoft Planetary Computer (NBR par section), inventaire des cultures d'AAC, SoilGrids. Le réseau est dans `src/lib/fireData.js`, la logique pure (événements, gravité, sol, effet, rotation proposée) dans `src/lib/wildfire.js`, testée dans `tests/wildfire.test.js`. Détail des services : [data-sources.md](data-sources.md#feux-près-de-la-ferme-front).
