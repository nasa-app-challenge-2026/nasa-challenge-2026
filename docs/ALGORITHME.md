# L'algorithme Field Shift dans le code

Ce document explique comment l'algorithme de rotations (_Field Shift — pipeline v5.1_, référence Python `field_shift.py`) est codé dans ce dépôt, où trouver chaque étape et comment le faire évoluer.

- **Où :** [`backend/algorithm/`](../backend/algorithm/), dans la couche back end (voir [`ARCHITECTURE.md`](ARCHITECTURE.md)).
- **Langage :** JavaScript (modules ES), sans dépendance. Il tourne dans le navigateur : le site reste publiable sur GitHub Pages sans serveur.
- **Fidélité :** sur les mêmes entrées, il donne les mêmes chaînes, décisions et notes que `field_shift.py` (à 10⁻⁹ près). 17 plans de parcelles, sur 9 scénarios, sont vérifiés à chaque `npm test` (voir [Tests](#tests)).

## L'idée en une phrase

Pour chaque cycle de rotation, l'algorithme calcule le climat que la ferme aura, cherche les endroits qui ont déjà vécu ce climat (ses jumeaux climatiques), regarde ce qu'on y cultive et avec quel succès, puis construit la meilleure suite de cultures pour la parcelle en respectant le calendrier, le climat, les délais de retour et les priorités du fermier.

## Le parcours d'un calcul

```
frontend (écrans)
   │  FarmInput 2.0 (contrat)
   ▼
application/app.js ── engine.planFarm(farm) ──► backend/algorithmEngine.js
                                                   │ 1. météo NASA POWER de la ferme (data/access/nasaPower.js),
                                                   │    ou météo fictive si l'API ne répond pas
                                                   ▼
                                     backend/algorithm/FieldShiftAlgorithm.js
                                                   │ 2. lit le FarmInput        input/FarmInputReader.js
                                                   │ 3. pour chaque section :   planning/ParcelPlanner.js
                                                   │      pour chaque cycle :   étapes 3 à 10
                                                   │ 4. écrit le FarmPlan 2.0   report/PlanSerializer.js
                                                   ▼
                                    FarmPlan 2.0 ──► application ──► écrans
```

Un plan complet (4 sections, 3 cycles, une culture par an) prend environ 0,2 s ; le premier calcul attend en plus le téléchargement de la météo NASA POWER (≈ 0,7 Mo, une fois par lieu et par session).

## Les étapes et leurs fichiers

| Étape du PDF                    | Ce qu'elle fait                                                                                | Fichiers                                                                                                                                                                          |
| ------------------------------- | ---------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1** Entrées du fermier        | parcelles, réserve, cycle / fréquence / horizon, priorités → poids (rank order centroid)       | `application/rules/timeSettings.js` (`TimeSettings`), `application/rules/priorities.js`, `planning/FarmerProfile.js`, `planning/Parcel.js`, `input/FarmInputReader.js`            |
| **2** Climat en 5 chiffres      | degrés-jours, pluie d'été, saison sans gel, jours > 30 °C, minimum de janvier, année par année | `climate/IndicatorTable.js`                                                                                                                                                       |
| **3** Climat visé par cycle     | cas 1 : tendance des 40 ans de NASA POWER ; cas 2 : modèles climatiques (deltas)               | `climate/TargetClimateProjector.js`, `climate/TemperatureTrend.js`, `climate/DeltaMethod.js`, `climate/CycleClimateBuilder.js`, `climate/CycleClimate.js`                         |
| **4** Jumeaux climatiques       | distance sigma (Mahalanobis → percentile chi), 10 cases par climat visé, réunion des modèles   | `twins/SigmaDissimilarity.js`, `twins/ClimateTwinFinder.js`, `math/distributions.js`, `math/linearAlgebra.js`                                                                     |
| **5** Filtre sol                | distance de sol, élargissement de 25 % sous 200 champs                                         | `twins/SoilComparison.js`                                                                                                                                                         |
| **6** Rotations observées       | séquence de 8 ans → rotation canonique ; poids d'un champ = surface × (1 − σ/2)                | `twins/RotationPattern.js`, `twins/TwinEvidenceBuilder.js`                                                                                                                        |
| **7** Valeur du précédent       | verdure → écart de rendement → valeur de A avant B (min. 20 champs)                            | `twins/PrecropValue.js`, `twins/TwinEvidence.js`                                                                                                                                  |
| **8** Diagnostic de la parcelle | risques érosion et eau, refaits à chaque cycle ; poids ajustés                                 | `diagnostic/ParcelDiagnostic.js`, `planning/CriteriaWeights.js`                                                                                                                   |
| **Délais de retour** (partie B) | minimum et recommandé par culture, familles, maladies déclarées, vigilances                    | `delays/ReturnDelayCatalog.js`, `delays/ReturnDelayRules.js`, `delays/ReturnDelayChecker.js`, `delays/Occupation.js`, `delays/FieldHistory.js`                                    |
| **9b** Meilleure chaîne         | candidates, placement (calendrier, gel), couverts, note sur 9 critères, recherche en faisceau  | `chain/CandidateSheets.js`, `chain/CropPlacer.js`, `chain/CoverCropPlanner.js`, `chain/ChainScorer.js`, `chain/ChainSearch.js`, `chain/ChainReplayer.js`, `chain/CycleContext.js` |
| **10** Plan par cycle           | référence, garder ou changer (≤ 5 points), raccord entre cycles, robustesse                    | `planning/ParcelPlanner.js`, `planning/RobustnessAnalyzer.js`, `planning/decisions.js`                                                                                            |
| Sortie                          | plan → JSON du contrat, messages en français, libellé des chaînes                              | `report/PlanSerializer.js`, `report/messages.js`, `report/chainLabel.js`                                                                                                          |

Les dossiers restants :

- `config/` : **toutes les constantes** (seuils, tolérances, pas de temps, poids des risques). Aucun nombre « magique » dans le reste du code : chaque valeur a un nom et un commentaire qui dit d'où elle vient.
- `math/` : outils numériques sans lien avec l'agronomie (moyennes, pente, arrondi « à la Python », distribution chi, résolution linéaire, générateur pseudo-aléatoire reproductible).
- `time/MonthTime.js` : les dates de la construction des chaînes sont des **mois décimaux depuis janvier 2000** (321,6 ≈ 19 octobre 2026), comme dans la référence.
- `weather/DailyWeather.js` : une série météo quotidienne (tmax, tmin, pluie) immuable.
- `sources/` : d'où viennent les données (voir la section suivante).

Les données fixes partagées avec les écrans sont dans la couche data :

| Fichier                                                                 | Contenu                                                                                                                                                                                            |
| ----------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`data/reference/crops.js`](../data/reference/crops.js)                 | les cultures (noms, couleurs) et les **fiches** de l'algorithme : fenêtre de semis, degrés-jours, date de récolte fixe, années de production, minimum de janvier, équipement, valeurs des critères |
| [`data/reference/returnDelays.js`](../data/reference/returnDelays.js)   | table des délais (Fruchtfolge, maladie de référence SARE, famille) et les 20 maladies du sol du guide SARE                                                                                         |
| [`data/reference/criteria.js`](../data/reference/criteria.js)           | les 9 critères de la note et leur ordre                                                                                                                                                            |
| [`data/reference/planning.js`](../data/reference/planning.js)           | cycle 2 à 6 ans, fréquences 12 / 6 / 4 mois, fin des projections (2060), modes de la réserve                                                                                                       |
| [`data/reference/fieldMeasures.js`](../data/reference/fieldMeasures.js) | libellés et sources des mesures satellites de l'étape 8                                                                                                                                            |

## Les classes principales

| Classe / fonction               | Rôle                                                                                                                           |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `FieldShiftAlgorithm`           | façade : construit les sources de données pour une ferme, puis `planFarm(input, today)` → `FarmPlan`                           |
| `ParcelPlanner`                 | `plan(parcel)` : la boucle des cycles d'une parcelle (étape 10)                                                                |
| `CycleContext`                  | tout ce qu'un cycle sait : positions, point de départ, climat, jumeaux, poids, réserve, historique, candidates                 |
| `bestChains(ctx)`               | recherche en faisceau (400 chaînes partielles gardées à chaque position) → les 3 meilleures chaînes complètes                  |
| `scoreChain(chain, ctx)`        | les 9 critères et la note sur 100 ; trouve aussi les couverts, les lacunes, les semences à acheter, les vigilances             |
| `placeCrop(sheet, position, …)` | une culture entre-t-elle dans une position ? date de semis et de récolte                                                       |
| `ReturnDelayChecker`            | contraintes dures (violations), critère ravageurs, vigilances des maladies partagées                                           |
| `TargetClimateProjector`        | `project(premièreAnnée, dernièreAnnée)` : climats visés (un par modèle après 10 ans) et calendrier du cycle                    |
| `ClimateTwinFinder`             | `twinsOf(climatsVisés)` : les cases jumelles, réunies sur tous les modèles                                                     |
| `CycleClimate`                  | calendrier d'un cycle : chaleur de chaque mois, gels, minimum de janvier, avance des récoltes, `maturity(semis, degrés-jours)` |
| `TwinEvidence`                  | ce que les étapes 4 à 7 donnent à l'étape 9b : cultures pratiquées, enchaînements observés, valeurs de précédent, σ moyen      |
| `CycleDataProvider`             | `cycleData(a0, a1)` : enchaîne les étapes 3 à 7 pour un cycle (avec cache)                                                     |

## D'où viennent les données

L'algorithme reçoit ses données par **injection** : `ParcelPlanner` ne connaît que `data.cycleData(a0, a1)` et chaque parcelle porte son diagnostic. Changer de source ne touche pas au cœur.

| Donnée                                    | Aujourd'hui                                                                                                                                                            | Fichier                                                  |
| ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| Météo de la ferme 1985–2024 (étapes 2–3)  | **réelle : API NASA POWER** au point de la ferme ; si l'API ne répond pas, série fictive (même recette que la démo Python)                                             | `data/access/nasaPower.js`, `sources/DemoFarmWeather.js` |
| Modèles NEX-GDDP-CMIP6 (cas 2)            | **fictifs** : 3 modèles (réchauffement × 0,8 / 1 / 1,3, pluie × 1,05 / 1 / 0,92, biais de +1 °C), comme la démo Python                                                 | `sources/DemoClimateModels.js`                           |
| Climat observé de la grille (étape 4)     | **fictif** : grille de 0,5° autour de la ferme, ancrée sur le climat réel de la ferme et déplacée par des gradients plausibles ; la vraie recherche sigma s'y applique | `sources/DemoTwinAtlas.js`                               |
| Cultures et précédents des jumeaux (5–7)  | **fictifs** : la table de la démo Python (canola tant que le cycle est à moins de 1,5 °C de 2015, double culture blé-soya ensuite)                                     | `sources/DemoTwinCrops.js`                               |
| Mesures satellites et sol (étapes 5 et 8) | **fictifs** : les valeurs de la démo Python, un peu différentes d'une section à l'autre ; l'analyse de sol du fermier remplace SoilGrids                               | `sources/DemoFieldMeasures.js`                           |

Le plan dit toujours d'où viennent ses chiffres (`meta.sources`, affiché en haut des écrans) et `meta.demo` vaut `true` tant qu'une source est fictive (badge « Données d'exemple »).

### Brancher une vraie source

Les fichiers de NEX-GDDP-CMIP6, des cartes de cultures (USDA, AAC) et de NASA HLS pèsent des centaines de Mo : ils se préparent sur un serveur, pas dans le navigateur. Deux chemins :

1. **Garder l'algorithme dans le navigateur** et lui donner des fichiers pré-calculés (petits) :
   - modèles : un objet `{ name, simulate(début, fin) → { historical, future } }` par modèle (`DailyWeather` en °C et mm/jour), passé à `TargetClimateProjector` ;
   - grille : une liste de `GridCell` `{ id, lat, lon, cultivated, indicators: IndicatorTable }` pour 2011–2024, passée à `ClimateTwinFinder` ;
   - jumeaux : appeler `buildTwinEvidence(champs, champsAnnées, jumeaux)` (étapes 6–7) sur les champs gardés par `SoilFilter` (étape 5) ;
   - mesures : les six valeurs de `ParcelDiagnostic` et le sol de chaque section.
     Ces objets remplacent les `demo*` dans `FieldShiftAlgorithm` (constructeur) et `FarmInputReader`.
2. **Déplacer le calcul sur un serveur** qui répond à `POST /plan` avec le même contrat (voir [`ALGO_CONTRACT.md`](ALGO_CONTRACT.md)) : `VITE_ALGO_MODE=remote`. `npm run check:algo -- <url>` vérifie le serveur.

## Les règles importantes, en bref

- **Positions.** Un cycle de C ans avec une culture tous les f mois a N = 12C / f positions. Une culture appartient à la position où elle est récoltée (« blé 2028 »). Les positions commencent en janvier (12 mois) ou en février (6 et 4 mois).
- **Climat visé.** La dernière année du cycle décide : dans les 10 ans de l'année d'utilisation → tendance NASA POWER (les 20 dernières années décalées jusqu'au milieu du cycle, la pluie n'est pas prolongée) ; au-delà → deltas mensuels de chaque modèle appliqués à NASA POWER 1985–2014, fenêtre de 20 ans centrée sur le cycle (centre arrondi comme `round()` de Python : 2036,5 → 2036).
- **Contraintes dures.** Calendrier et gel, culture d'hiver qui survit au minimum de janvier, enchaînements de cultures vendues observés chez les jumeaux (le dernier vers le premier compris), délais de retour minimum (avec l'historique et le cycle suivant), pas deux jachères de suite, fermeture du cycle, départ après la culture en place.
- **Note.** Moyenne pondérée des 9 critères connus × 100 ; poids = rank order centroid du classement, érosion × (1 + risque), eau × (1 + risque), fourrage × 0,3 sans bétail.
- **Garder ou changer.** On garde la chaîne en place (rotation du fermier au cycle 1, puis chaîne du cycle précédent) si elle respecte les délais, si ses cultures poussent encore chez les jumeaux et si elle est à 5 points ou moins de la meilleure.
- **Robustesse.** Chaque chaîne adoptée est rejouée dans les cycles suivants ; on garde sa pire note, ou « devient infaisable plus tard ».

## Écarts avec la référence

Ils sont volontaires, limités, et testés (`tests/algorithm/deviations.test.js`) :

| Écart                                                                                                                                           | Pourquoi                                                                                                    | Effet sur les scénarios de référence                                                                                             |
| ----------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| La maturité d'une culture d'été se calcule à partir du **mois de l'année** du semis, pas mise en cache à partir de la première date absolue vue | le résultat ne dépend plus de l'ordre des appels                                                            | mêmes chaînes et décisions ; récoltes décalées d'au plus 0,05 mois, notes de moins de 0,1 point (vérifié par le script d'export) |
| **Sans culture en place**, les enchaînements du critère rendement se lisent dans l'ordre (A → B, B → C…)                                        | la référence associait chaque culture à elle-même (`zip(seq, seq)`), ce qui rendait le critère neutre       | seule la parcelle libre du scénario `variant-sans-fourragere-libre` diffère (exclue du test de référence)                        |
| Une culture en place **hors des fiches** (pomme de terre…) entre quand même dans l'historique                                                   | la référence l'oubliait, donc ses délais de retour n'étaient pas contrôlés                                  | aucun (pas de tel cas dans les scénarios)                                                                                        |
| La réserve se compte par **semence** : le soya en double culture utilise des semences de soya                                                   | la référence demandait une semence « Soya 2e culture »                                                      | aucun (la double culture n'apparaît qu'après 2035, hors du cycle 1)                                                              |
| Un climat **sans gel** n'empêche aucune culture (dates de gel `null`)                                                                           | en Python, `max(s, nan)` ignore le gel mais `Math.max` renverrait `NaN`                                     | aucun                                                                                                                            |
| Une covariance **singulière** (un indicateur qui ne varie jamais) reçoit une petite crête au lieu d'arrêter le calcul                           | `numpy.linalg.solve` lève une erreur et arrête tout                                                         | aucun                                                                                                                            |
| Aucune chaîne faisable : le cycle est marqué `aucune` et les cycles suivants ne sont pas calculés                                               | la référence lève `RuntimeError` pour toute la ferme                                                        | aucun                                                                                                                            |
| L'historique se donne **année par année** (`{ year, crop }`)                                                                                    | plus clair pour le fermier que la liste « la plus récente en dernier » ; mêmes occupations que la référence | aucun                                                                                                                            |

## Points à revoir avec un agronome

Ils viennent de l'algorithme lui-même, pas du portage :

- La note favorise parfois la **jachère couverte de seigle** (bonnes notes eau et érosion) : P1 au cycle 1 en propose deux. C'est déjà signalé dans le PDF ; les fiches des cultures sont à revoir.
- Dans les critères eau, fourrage, azote et matière organique, une jachère compte pour **0 mois** : le temps de la jachère est attribué à la culture suivante (règle de `evaluer` dans la référence, gardée telle quelle).
- Les fiches, les tolérances de sol, les poids des risques et l'avance des récoltes (3 jours par °C) sont **indicatifs**.
- Les délais Fruchtfolge + SARE sont prudents : la rotation maïs-soya de 2 ans est toujours en alerte.

## Tests

| Fichier                              | Ce qu'il vérifie                                                                                                                                                                                                                                              |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tests/algorithm/climate.test.js`    | étapes 2 et 3 contre la référence, sur une météo synthétique identique en Python et en JS                                                                                                                                                                     |
| `tests/algorithm/steps.test.js`      | sigma de chaque case, choix des jumeaux, sol, rotations canoniques, verdure → précédent, jumeaux, diagnostic                                                                                                                                                  |
| `tests/algorithm/delays.test.js`     | minimum / recommandé des 24 cultures, violations, vigilances, critère ravageurs, cultures impossibles, historique, poids                                                                                                                                      |
| `tests/algorithm/reference.test.js`  | **17 plans de parcelles sur 9 scénarios** (4/12/12, 4/6/8, 3/12/9, 5/12/10, 2/12/6, 3/4/3, réserve stricte, bétail + maladie + irrigation, sans fourragère) : chaînes, dates, notes, critères, couverts, lacunes, semences, alertes, alternatives, robustesse |
| `tests/algorithm/deviations.test.js` | les écarts volontaires ci-dessus                                                                                                                                                                                                                              |
| `tests/contract.test.js`             | le moteur respecte le schéma du contrat 2.0 ; NASA POWER réel ou repli fictif                                                                                                                                                                                 |
| `tests/inputs.test.js`               | règles d'entrée (étape 1) et lecture du plan par les écrans                                                                                                                                                                                                   |

Les fichiers de référence sont dans [`tests/algorithm/fixtures/`](../tests/algorithm/fixtures/). Pour les régénérer après une nouvelle version de `field_shift.py` :

```bash
python tests/algorithm/fixtures/export_reference.py <chemin/vers/field_shift.py> tests/algorithm/fixtures
```

(Python 3 avec numpy, scipy, xarray et pandas.) Le script affiche, pour chaque scénario, si la maturité « canonique » laisse les chaînes et les décisions inchangées.

## Ajouter ou modifier…

| Je veux…                          | Où                                                                                                                                                                                |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| une culture                       | une fiche dans `CROP_SHEETS` et une ligne dans `CROPS` (`data/reference/crops.js`), ses délais dans `CROP_DELAYS` (`returnDelays.js`), une texture dans `frontend/ui/textures.js` |
| changer un seuil ou une tolérance | `backend/algorithm/config/` (et le dire dans ce document)                                                                                                                         |
| un critère de la note             | `data/reference/criteria.js`, son calcul dans `chain/ChainScorer.js`, une valeur dans chaque fiche                                                                                |
| une vraie source de données       | `backend/algorithm/sources/` (même interface que la source fictive), branchée dans `FieldShiftAlgorithm`                                                                          |
| un nouveau champ du plan          | `report/PlanSerializer.js`, puis le schéma (`backend/contract/field-shift.schema.json`) et `ALGO_CONTRACT.md`                                                                     |
