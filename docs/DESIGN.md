# Base commune (design)

Les valeurs vivent dans [`frontend/styles/tokens.css`](../frontend/styles/tokens.css). Dans Figma, utilisez les mêmes.

## Couleurs

| Rôle       | Valeur    | Usage              |
| ---------- | --------- | ------------------ |
| Fond       | `#F4F5EF` | pages              |
| Surface    | `#FFFFFF` | cartes             |
| Texte      | `#18211B` | texte principal    |
| Secondaire | `#4A5549` | aides, sources     |
| Bordure    | `#DDE2D6` | contours           |
| Marque     | `#2E6B3B` | boutons principaux |
| Bon        | `#0072B2` | ce qui s'améliore  |
| Mauvais    | `#D55E00` | ce qui se dégrade  |
| Attention  | `#E69F00` | à surveiller       |

Bleu et orange plutôt que vert et rouge : lisibles par les daltoniens. **Une couleur n'est jamais seule** : toujours avec ↑, ↓, ⚠, ✓ ou un mot.

## Cultures

Chaque culture a une couleur plate (pastilles) et une texture de champ (vue 3D, cartes, frise) : `fill="url(#pat-ble)"`. Les textures sont définies une seule fois dans [`frontend/ui/textures.js`](../frontend/ui/textures.js).

## Typographie et mesures

Space Grotesk pour les titres, Inter pour le reste (34, 30, 18, 16, 14, 12). Grille de 8 px, coins de 12 px, boutons de 48 px, zones cliquables d'au moins 44 px.

## Quand un écran est fini

- [ ] Il n'utilise que les composants de la base commune (`frontend/ui/`, `frontend/styles/components.css`)
- [ ] Tout le contenu de la maquette de référence y est
- [ ] Aucune couleur seule
- [ ] Boutons et zones cliquables d'au moins 44 px
- [ ] Lisible sur un écran de téléphone (390 px), sans défilement horizontal
- [ ] Aucun nom d'étude dans les suggestions
- [ ] Les liens vers l'écran d'avant et d'après marchent
- [ ] Les chiffres d'exemple portent le badge « Données d'exemple » tant que l'algo n'est pas branché
