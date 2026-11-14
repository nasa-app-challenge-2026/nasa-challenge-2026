# Field Shift 🌱

**Planifier la rotation des cultures de sa ferme, section par section, avec les données de la NASA.**

Projet de l'équipe **NASA-LARPERS** pour le [NASA Space Apps Challenge 2026](https://www.spaceappschallenge.org/2026/) (14 et 15 novembre), défi _Field Shift: Adapting Farms with NASA Data_.

> **v2.0 · front end complet, algorithme en cours.** L'interface marche de bout en bout avec un moteur de démo (chiffres fictifs, badge « Données d'exemple »). Le vrai algorithme se branche sans toucher aux écrans : voir [le contrat](docs/ALGO_CONTRACT.md).

![Tableau de bord](docs/screenshots/tableau.png)

## Ce que fait l'appli

1. Le fermier crée son compte, choisit son **type de ferme** (grandes cultures ; les autres types arrivent), place sa ferme sur la carte et la **découpe en sections** A, B, C…
2. Il classe ses **priorités** : revenu, résilience, sol, eau, charge de travail.
3. Le **tableau de bord** montre chaque section, la ferme en vue isométrique avec la texture de la culture de chaque année, un curseur des années, et signale les années où l'assolement est déséquilibré (bouton « Décaler mes sections »).
4. Pour chaque section : les **données NASA** du champ, l'éditeur de **rotation** (délais de retour, cultures sur plusieurs années, couvertures d'hiver, santé du sol), les **résultats** comparés à la monoculture, **explorer et modifier** en direct, et un **stress test** (sécheresse, canicule, ravageurs).
5. **Feux près de la ferme**, un petit bloc du tableau de bord qui tient en une ligne : « Aucun risque pour le moment », sauf gros feu actif à moins de 25 km ou danger d'incendie élevé. Son détail garde l'essentiel : la carte et la liste des feux de l'année (points chauds MODIS et VIIRS de la NASA, zones brûlées et danger d'incendie du Canada ; les plus anciens dans des archives repliées), le brûlage mesuré sur chaque section (NBR des images HLS avant et après le feu), pendant une alerte quoi faire section par section (de la plus proche du feu à la plus loin, avec une couverture d'hiver pour les sections côté feu) et, pour les sections touchées, quoi faire et une rotation ajustée à appliquer (le sol SoilGrids et l'inventaire des cultures d'Agriculture Canada servent au calcul). Un **exemple réel** (feu agricole de mai 2023 en Saskatchewan) montre toute la chaîne.
6. **RotaAI**, en bas à droite, répond aux « pourquoi ».

| Rotation                                   | Résultats                                    |
| ------------------------------------------ | -------------------------------------------- |
| ![Rotation](docs/screenshots/rotation.png) | ![Résultats](docs/screenshots/resultats.png) |

## Démarrer

Il faut Node.js 20 ou plus.

```bash
npm install
npm run dev        # http://localhost:5173
```

| Commande                            | Rôle                                             |
| ----------------------------------- | ------------------------------------------------ |
| `npm run dev`                       | le front Field Shift seul (port 5173 ou suivant) |
| `npm run dev:all`                   | tout : front, `apps/web` (5174) et l'API (8000)  |
| `npm run build` / `npm run preview` | version de production dans `dist/`               |
| `npm test`                          | tests (rotations, contrat avec l'algo, RotaAI)   |
| `npm run lint` / `npm run format`   | qualité du code                                  |
| `npm run fixtures`                  | régénère `contract/examples/`                    |
| `npm run check:algo -- <url>`       | vérifie qu'un algorithme respecte le contrat     |

## Brancher l'algorithme

Le front parle à l'algo à travers **un contrat** : trois routes `POST` en JSON, décrites dans [`docs/ALGO_CONTRACT.md`](docs/ALGO_CONTRACT.md) et [`contract/field-shift.schema.json`](contract/field-shift.schema.json).

```bash
cp .env.example .env.local
# VITE_ALGO_MODE=remote
# VITE_ALGO_URL=http://localhost:8000
npm run check:algo -- http://localhost:8000
npm run dev
```

Pour l'équipe algo : [`docs/PROMPT_ALGO.md`](docs/PROMPT_ALGO.md) est un message prêt à donner à Claude, avec la liste des fichiers à joindre.

## Mettre en ligne

Le workflow [`deploy.yml`](.github/workflows/deploy.yml) publie le site sur GitHub Pages à chaque push sur `main`. Une fois : **Settings → Pages → Source : GitHub Actions**. Pour utiliser le vrai algo en ligne, ajoutez les variables `VITE_ALGO_MODE` et `VITE_ALGO_URL` dans **Settings → Secrets and variables → Actions → Variables**.

## Documentation

| Fichier                                                    | Contenu                                                       |
| ---------------------------------------------------------- | ------------------------------------------------------------- |
| [`docs/ALGO_CONTRACT.md`](docs/ALGO_CONTRACT.md)           | Le contrat front ↔ algo                                       |
| [`docs/PROMPT_ALGO.md`](docs/PROMPT_ALGO.md)               | Message prêt à envoyer pour coder l'algo                      |
| [`docs/FRONT_ARCHITECTURE.md`](docs/FRONT_ARCHITECTURE.md) | Organisation du code, comment ajouter un écran                |
| [`docs/DESIGN.md`](docs/DESIGN.md)                         | Base commune : couleurs, textures, typo, liste « écran fini » |
| [`docs/TEAM.md`](docs/TEAM.md)                             | Qui fait quoi, façon de travailler                            |
| [`docs/ROTAAI.md`](docs/ROTAAI.md)                         | L'assistant, aujourd'hui et plus tard                         |
| [`docs/FRONT_ROADMAP.md`](docs/FRONT_ROADMAP.md)           | Ce qui reste à faire                                          |

## Sources

Les données NASA (POWER, GPM IMERG, SMAP, ECOSTRESS, HLS, NEX-GDDP-CMIP6), SoilGrids et les études utilisées sont listées dans [`src/data/sources.js`](src/data/sources.js) et dans la page « Détail et sources » de l'appli. Polices : Inter et Space Grotesk (Google Fonts, licence SIL OFL).

## Utilisation de l'IA

Claude (Anthropic) a servi à la recherche d'études, aux maquettes, à l'architecture et à une première version de ce code ; l'équipe l'a relu et le maintient. Les réponses de RotaAI sont écrites à l'avance et relues par l'équipe. Le journal détaillé sera tenu pour la déclaration de soumission.

## Limites

Les chiffres du moteur de démo sont fictifs. Les effets de rotation viennent surtout d'études menées aux États-Unis et devront être calibrés pour le Québec. Field Shift aide à décider ; il ne remplace pas l'avis d'un agronome.

## Licence

[MIT](LICENSE) · NASA-LARPERS 2026
