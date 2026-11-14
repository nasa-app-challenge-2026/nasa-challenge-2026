# Qui fait quoi

| Personne                                          | Fichiers                                                                                                                                                                                      |
| ------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Ali** · base commune, tableau de bord, rotation | `src/styles/tokens.css`, `src/styles/components.css`, `src/ui/widgets.js`, `src/ui/layout.js`, `src/ui/isoFarm.js`, `src/ui/textures.js`, `src/screens/tableau.js`, `src/screens/rotation.js` |
| **Loïc** · première visite, compte, RotaAI        | `src/screens/connexion.js`, `typeFerme.js`, `localisation.js`, `tracer.js`, `priorites.js`, `compte.js`, `src/ui/fakeMap.js`, `src/ui/rotaai.js`, `src/rotaai/answers.js`                     |
| **Justin** · analyse d'une section                | `src/screens/champ.js`, `resultats.js`, `explorer.js`, `stress.js`, `sources.js`, `src/ui/revenueChart.js`, `src/data/sources.js`                                                             |
| **Nour et Yanis** · algorithme                    | dépôt séparé, qui respecte `docs/ALGO_CONTRACT.md`                                                                                                                                            |
| **Yanis** · communication                         | vidéo, soumission                                                                                                                                                                             |

## Façon de travailler

1. Une branche par tâche : `ali/tableau-3d`, `loic/carte-leaflet`, `justin/graphique-revenu`.
2. `npm run lint && npm test` avant de pousser.
3. Une pull request vers `main`, relue par une autre personne. La CI vérifie le lint, le format, les tests et la compilation.
4. Chaque fusion dans `main` met le site à jour sur GitHub Pages.
