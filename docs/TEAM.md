# Qui fait quoi

| Personne                                          | Fichiers                                                                                                                                                                                                                              |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Ali** · base commune, tableau de bord, rotation | `frontend/styles/tokens.css`, `frontend/styles/components.css`, `frontend/ui/widgets.js`, `frontend/ui/layout.js`, `frontend/ui/isoFarm.js`, `frontend/ui/textures.js`, `frontend/screens/tableau.js`, `frontend/screens/rotation.js` |
| **Loïc** · première visite, compte, RotaAI        | `frontend/screens/connexion.js`, `typeFerme.js`, `localisation.js`, `tracer.js`, `priorites.js`, `compte.js`, `frontend/ui/leafletMap.js`, `drawMap.js`, `frontend/ui/rotaai.js`, `data/reference/rotaaiAnswers.js`                   |
| **Justin** · analyse d'une section                | `frontend/screens/champ.js`, `resultats.js`, `explorer.js`, `stress.js`, `sources.js`, `frontend/ui/revenueChart.js`, `data/reference/sources.js`                                                                                     |
| **Nour et Yanis** · algorithme                    | dépôt séparé, qui respecte `docs/ALGO_CONTRACT.md`                                                                                                                                                                                    |
| **Yanis** · communication                         | vidéo, soumission                                                                                                                                                                                                                     |

## Façon de travailler

1. Une branche par tâche : `ali/tableau-3d`, `loic/carte-leaflet`, `justin/graphique-revenu`.
2. `npm run lint && npm test` avant de pousser.
3. Une pull request vers `main`, relue par une autre personne. La CI vérifie le lint, le format, les tests et la compilation.
4. Chaque fusion dans `main` met le site à jour sur GitHub Pages.
