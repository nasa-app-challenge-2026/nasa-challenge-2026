# Field Shift — interface bilingue et cartes de rotation

Travail local sur `UI-yanis`, sans commit et sans modification de l’algorithme Python.

## Fichiers et comportement

- `data/i18n/index.js`, `messages.js` : catalogue EN/FR, `t(clé, variables)`, pluriels avec `Intl.PluralRules`, nombres et dates selon la langue. Les phrases françaises existantes servent de clés au catalogue.
- `frontend/lib/localizeHtml.js`, `html.js` : adaptation des templates existants. Seuls les textes et attributs lisibles sont localisés ; les identifiants, routes, valeurs des formulaires, classes et styles restent intacts. `verbatim()` protège les noms, adresses et questions saisis par l’utilisateur.
- `application/state/initialState.js`, `frontend/actions.js`, `main.js`, `index.html`, `ui/layout.js`, `screens/connexion.js` : anglais par défaut, préférence `prefs.language`, bouton EN ⇄ FR, langue du document et titre de page. Changer de langue conserve section, cycle et année.
- `data/reference/crops.js`, `rotaAnswers.js`, `data/access/geocode.js` : noms des cultures, recherche géographique dans la langue choisie et compréhension de questions Rota en anglais. Les réponses canoniques restent disponibles pour être réaffichées dans l’autre langue.
- `screens/tableau.js`, `parcelle.js`, `ui/dragSort.js`, `ui/farm3d/*` : section entièrement cliquable, clavier natif, protection contre le clic après un glisser, survol/focus transmis à la scène existante. Suppression du raccourci Ma parcelle dans la carte 3D, lien Consulter la rotation / View rotation.
- `screens/plan.js`, `ui/rotationDialog.js`, `ui/rotationViews.js` : trois recommandations et la référence dans une grille commune, détails dans des templates inertes. Boîte de dialogue native, animation de 450 ms depuis la position mesurée, fermeture inverse, défilement interne, fond inerte, restauration du focus, fondu de 140 ms en mouvement réduit. Les explications Rota s’ouvrent dans la carte.
- `ui/planWidgets.js`, `weatherWidget.js`, `leafletMap.js`, `drawMap.js`, `screens/champ.js`, `jumeaux.js`, `localisation.js`, `tracer.js`, `cultures.js`, `compte.js`, `ui/rota.js` : formats localisés, textes des cartes conservées entre rendus, protection des saisies et libellés accessibles.
- `frontend/styles/interactions.css` : présentation responsive avec les tokens existants.
- `tests/i18n.test.js`, `screens.smoke.test.js`, `dashboard.test.js`, `weather.test.js`, `scripts/verify-ui.mjs` : couverture des langues, nouveaux états et interactions.

`package-lock.json` était déjà modifié au début de cette demande, à la suite de l’installation de `three` lors du lancement précédent. Aucune dépendance d’exécution n’a été ajoutée pour ces changements.

## Améliorations supplémentaires

1. Sélecteurs d’année avec cibles tactiles d’au moins 44 px.
2. Barre des cycles défilante horizontalement pour éviter le débordement mobile.
3. Navigation des pages de section horizontale sur mobile pour réduire la hauteur avant le contenu.
4. En-tête, badges et boutons adaptés aux petits écrans et aux libellés traduits.
5. États explicites pour une ferme sans section, un plan sans cycle et des informations de section incomplètes ; un lien permet de compléter les informations au lieu d’attendre indéfiniment.
6. Explications Rota intégrées à la carte ouverte, à portée du focus modal.
7. Bouton de langue également présent dès la connexion et pendant la configuration.
8. Contrôles Leaflet traduits en conservant la carte, ses couches et son cadrage ; cadrage initial sans animation pour éviter une erreur Leaflet observée lors de navigations rapides.
9. Chargement 3D annulé si le tableau a été quitté avant la fin de l’import.

## Vérifications

- Tests unitaires et de rendu : `npm test`, **100 tests réussis**.
- Lint : `npm run lint`, **réussi**.
- Compilation : `npm run build`, **réussie**.
- Chrome : anglais/français, fenêtres 1440 × 900 et 390 × 900 ; tableau, clic et activation clavier des sections, quatre rotations (référence incluse), fermeture par ×/Échap/fond, focus piégé et restitué, blocage du défilement arrière-plan, Rota dans la carte, changement de cycle, persistance de la langue, réorganisation par clavier et pointeur, mouvement réduit et absence de débordement horizontal.
- Passage dans les autres écrans, dont la configuration, les réglages, les sources, le champ et les jumeaux ; contrôle des erreurs JavaScript.

Les scénarios navigateur utilisent le plan de contrat `ferme-demo.plan.json` via interception de la réponse HTTP. Cela permet de vérifier tous les états avec des données reproductibles, sans dépendre des téléchargements NASA. L’interface de développement et le serveur Python restent les serveurs locaux du projet. Ces vérifications ne valident pas les résultats des services scientifiques en direct.

Pour reproduire les interactions avec Chrome installé et Vite sur `127.0.0.1:5173` :

```powershell
npm install --prefix .qa --no-save --package-lock=false playwright-core
node scripts/verify-ui.mjs
```

Playwright est un outil de vérification isolé dans `.qa`, pas une dépendance de l’application. Les captures sont produites dans ce dossier.

## Limites des messages serveur

Les messages connus d’application et du client HTTP, les violations de délais de retour, maladies partagées, cultures incompatibles avec un cycle, phrases du modèle ravageurs et les trois alertes du modèle d’eau sont couverts par le catalogue, sans toucher à l’algorithme.

La traduction exhaustive des diagnostics techniques libres reste à traiter côté contrat API :

- corps d’erreur arbitraire renvoyé par `POST /plan`, relayé par `backend/remoteEngine.js` ;
- détails de validation FastAPI/Pydantic non répertoriés dans le catalogue ;
- diagnostics des fournisseurs distants et nouveaux libellés de provenance construits dans `api/field_shift/data_access/` ou `api/water_use/`.

Ces textes n’ont pas d’identifiant stable. Un texte inconnu peut donc garder sa langue d’origine ; le catalogue couvre les messages connus sans inventer une traduction de diagnostics nouveaux. Pour garantir la couverture de tout retour possible, l’API doit fournir un code de message et ses paramètres. Les noms propres, adresses et textes saisis par l’utilisateur sont volontairement conservés.
