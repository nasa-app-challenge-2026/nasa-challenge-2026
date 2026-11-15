# Qui fait quoi

| Personne                                          | Fichiers                                                                                                                                                                                                                                       |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Ali** · base commune, tableau de bord, rotation | `frontend/styles/tokens.css`, `frontend/styles/components.css`, `frontend/ui/widgets.js`, `frontend/ui/layout.js`, `frontend/ui/isoFarm.js`, `frontend/ui/textures.js`, `frontend/screens/tableau.js`, `frontend/screens/parcelle.js`          |
| **Loïc** · première visite, compte, RotaAI        | `frontend/screens/connexion.js`, `typeFerme.js`, `localisation.js`, `tracer.js`, `cultures.js`, `temps.js`, `priorites.js`, `compte.js`, `frontend/ui/leafletMap.js`, `drawMap.js`, `frontend/ui/rotaai.js`, `data/reference/rotaaiAnswers.js` |
| **Justin** · analyse d'une section                | `frontend/screens/champ.js`, `plan.js`, `jumeaux.js`, `sources.js`, `frontend/ui/planWidgets.js`, `data/reference/sources.js`                                                                                                                  |
| **Nour et Yanis** · algorithme                    | `backend/server/` (algorithme, contrat, tests), `backend/contract/`, `data/reference/crops.js` et `diseases.js` (voir `docs/ALGORITHME.md`)                                                                                                    |
| **Yanis** · communication                         | vidéo, soumission                                                                                                                                                                                                                              |

## Façon de travailler

1. Une branche par tâche : `ali/tableau-3d`, `loic/carte-leaflet`, `justin/graphique-revenu`.
2. `npm run lint && npm test` avant de pousser.
3. Une pull request vers `main`, relue par une autre personne. Il n'y a pas de CI : lancez le lint, le format, les tests et la compilation avant de pousser.
4. Chaque fusion dans `main` met le site à jour sur GitHub Pages.
