# L'algorithme Field Shift dans le code

Ce document explique comment l'algorithme de rotations (_Field Shift — pipeline v5.1_, référence `field_shift.py`) est codé dans ce dépôt, où trouver chaque étape et comment le faire évoluer.

- **Où :** [`api/field_shift/algorithm/`](../api/field_shift/algorithm/), servi par un serveur **FastAPI** ([`api/`](../api/)).
- **Langage :** Python 3.11+, avec numpy et scipy pour le calcul. L'algorithme n'importe ni FastAPI ni Pydantic : il reçoit et rend des objets Python ordinaires.
- **Fidélité :** sur les mêmes entrées, il donne les mêmes chaînes, décisions et notes que `field_shift.py` (à 10⁻⁹ près). 17 plans de parcelles, sur 9 scénarios, sont vérifiés à chaque `pytest`, et la chaîne complète de la météo au plan aussi (voir [Tests](#tests)).

## L'idée en une phrase

Pour chaque cycle de rotation, l'algorithme calcule le climat que la ferme aura, cherche les endroits qui ont déjà vécu ce climat (ses jumeaux climatiques), regarde ce qu'on y cultive et avec quel succès, puis construit la meilleure suite de cultures pour la parcelle en respectant le calendrier, le climat, les délais de retour et les priorités du fermier.

## Le parcours d'une requête

```
front end (navigateur)
   │  POST /plan   FarmInput 2.0 (JSON camelCase)
   ▼
api/app.py ─────────► services/plan_service.py                 PlanService.plan_farm
                         │ 1. météo de la ferme               data_access/weather_providers.py
                         │    (NASA POWER : une requête par lieu, gardée sur disque)
                         │ 2. un FieldShiftAlgorithm par lieu, gardé en mémoire (8 lieux)
                         │ 3. entrée → objets de l'algorithme  contract/input_mapper.py
                         │ 4. pour chaque section :            algorithm/field_shift_algorithm.py
                         │      pour chaque cycle : étapes 3 à 10   algorithm/planning/parcel_planner.py
                         │ 5. résultats → plan                 contract/plan_mapper.py
                         ▼
                  FarmPlan 2.0 (JSON) ──► front end
```

Un plan complet (4 sections, 3 cycles, une culture par an) prend environ 0,3 s. Le premier calcul d'un lieu attend en plus le téléchargement de la météo NASA POWER (≈ 0,7 Mo, une fois par lieu tant que le serveur tourne).

## Les étapes et leurs fichiers

Chemins relatifs à `api/field_shift/`.

| Étape du PDF                    | Ce qu'elle fait                                                                                                  | Fichiers                                                                                                                                                                              |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1** Entrées du fermier        | parcelles, réserve, cycle / fréquence / horizon, 4 priorités → poids (rank order centroid)                         | `contract/farm_input.py` (validation), `contract/input_mapper.py`, `algorithm/planning/` : `time_settings.py`, `priorities.py`, `farmer_profile.py`, `parcel.py`                      |
| **2** Climat en 5 chiffres      | degrés-jours, pluie d'été, saison sans gel, jours > 30 °C, minimum de janvier, année par année                   | `algorithm/climate/indicator_table.py`                                                                                                                                                |
| **3** Climat visé par cycle     | cas 1 : tendance des 40 ans de NASA POWER ; cas 2 : modèles climatiques (deltas)                                 | `algorithm/climate/` : `target_climate_projector.py`, `temperature_trend.py`, `delta_method.py`, `cycle_climate_builder.py`, `cycle_climate.py`                                       |
| **4** Jumeaux climatiques       | distance sigma (Mahalanobis → percentile chi), 10 cases par climat visé, réunion des modèles                     | `algorithm/twins/sigma_dissimilarity.py`, `algorithm/twins/climate_twin_finder.py`                                                                                                    |
| **5** Filtre sol                | distance de sol, élargissement de 25 % sous 200 champs                                                           | `algorithm/twins/soil_comparison.py`                                                                                                                                                  |
| **6** Rotations observées       | séquence de 8 ans → rotation canonique ; poids d'un champ = surface × (1 − σ/2)                                  | `algorithm/twins/rotation_pattern.py`, `algorithm/twins/twin_evidence_builder.py`                                                                                                     |
| **7** Valeur du précédent       | verdure → écart de rendement → valeur de A avant B (min. 20 champs)                                              | `algorithm/twins/precrop_value.py`, `algorithm/twins/twin_evidence.py`                                                                                                                |
| **8** Diagnostic de la parcelle | risque érosion ; risque eau = pression sur l'eau du cycle (`water_use`) ; poids ajustés                          | `algorithm/diagnostic/parcel_diagnostic.py`, `algorithm/planning/criteria_weights.py`                                                                                                 |
| **Délais de retour** (partie B) | minimum et recommandé par culture, familles, maladies déclarées, vigilances                                      | `algorithm/delays/` : `return_delay_catalog.py`, `return_delay_rules.py`, `return_delay_checker.py`, `occupation.py`, `field_history.py`                                              |
| **Eau** (étapes 8 et 9b)        | note eau d'une chaîne et pression sur l'eau de la ferme : bilan d'eau du sol jour par jour sur la météo du cycle | `algorithm/water/water_model.py` (interface), `data_access/field_shift_eau.py` (adaptateur), `api/water_use/` (le module)                                                             |
| **9b** Meilleure chaîne         | candidates, placement (calendrier, gel), couverts, note sur 4 priorités, recherche en faisceau                    | `algorithm/chain/` : `candidate_sheets.py`, `crop_placer.py`, `cover_crop_planner.py`, `chain_scorer.py`, `chain_search.py`, `chain_replayer.py`, `cycle_context.py`, `chain_step.py` |
| **10** Plan par cycle           | référence, garder ou changer (≤ 5 points), raccord entre cycles, robustesse                                      | `algorithm/planning/` : `parcel_planner.py`, `robustness_analyzer.py`, `cycle_plan.py`                                                                                                |
| Sortie                          | résultats → JSON du contrat, messages en français, libellé des chaînes                                           | `contract/plan_mapper.py`, `contract/farm_plan.py`, `algorithm/report/messages.py`, `algorithm/report/chain_label.py`                                                                 |

Autres dossiers de `algorithm/` :

- `config/` : **toutes les constantes** (seuils, tolérances, pas de temps, poids des risques). Aucun nombre « magique » dans le reste du code : chaque valeur a un nom et un commentaire qui dit d'où elle vient.
- `timeline/month_time.py` : les dates de la construction des chaînes sont des **mois décimaux depuis janvier 2000** (321,6 ≈ 19 octobre 2026), comme dans la référence.
- `weather/daily_weather.py` : une série météo quotidienne (tmax, tmin, pluie), en tableaux numpy.
- `numerics/ratios.py` : deux petits outils (borner entre 0 et 1, variation en pourcents).
- `sources/` : d'où viennent les données (voir la section suivante).
- `field_shift_algorithm.py` : la façade. Elle se construit une fois par lieu et planifie autant de parcelles qu'on veut.

Les données fixes sont dans `reference/` : [`crops.py`](../api/field_shift/reference/crops.py) (cultures et **fiches** : fenêtre de semis, degrés-jours, date de récolte fixe, années de production, minimum de janvier, équipement, valeurs des critères), [`return_delays.py`](../api/field_shift/reference/return_delays.py) (table Fruchtfolge + SARE et les 20 maladies du sol), `criteria.py` (les 9 critères), `planning.py` (cycle 2 à 6 ans, fréquences 12 / 6 / 4 mois, 2060, modes de la réserve).

## Les classes principales

| Classe / fonction                | Rôle                                                                                                                           |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `PlanService` (`services/`)      | `plan_farm(farm_input)` : la requête entière ; garde en mémoire l'algorithme de chaque lieu                                    |
| `FieldShiftAlgorithm`            | façade : construit les sources de données d'un lieu, puis `plan_parcel(parcel, time, farmer, today)` → `ParcelPlan`            |
| `ParcelPlanner`                  | `plan(parcel)` : la boucle des cycles d'une parcelle (étape 10)                                                                |
| `CycleContext`                   | tout ce qu'un cycle sait : positions, point de départ, climat, jumeaux, poids, réserve, historique, candidates                 |
| `best_chains(ctx)`               | recherche en faisceau (400 chaînes partielles gardées à chaque position) → les 3 meilleures chaînes complètes                  |
| `score_chain(chain, ctx)`        | les 4 priorités et la note sur 100 ; trouve aussi les couverts, les lacunes, les semences à acheter, les vigilances             |
| `place_crop(sheet, position, …)` | une culture entre-t-elle dans une position ? dates de semis et de récolte                                                      |
| `ReturnDelayChecker`             | contraintes dures (violations), priorité ravageurs, vigilances des maladies partagées                                           |
| `TargetClimateProjector`         | `project(première année, dernière année)` : climats visés (un par modèle après 10 ans) et calendrier du cycle                  |
| `ClimateTwinFinder`              | `twins_of(climats visés)` : les cases jumelles, réunies sur tous les modèles (calcul de sigma vectorisé sur toute la grille)   |
| `CycleClimate`                   | calendrier d'un cycle : chaleur de chaque mois, gels, minimum de janvier, avance des récoltes, `maturity(semis, degrés-jours)` |
| `TwinEvidence`                   | ce que les étapes 4 à 7 donnent à l'étape 9b : cultures pratiquées, enchaînements observés, valeurs de précédent, σ moyen      |
| `CycleDataProvider`              | `cycle_data(a0, a1)` : enchaîne les étapes 3 à 7 pour un cycle (avec cache)                                                    |

## D'où viennent les données

L'algorithme reçoit ses données par **injection** : `ParcelPlanner` ne connaît que `data.cycle_data(a0, a1)`, et chaque parcelle porte son diagnostic. Changer de source ne touche pas au cœur.

| Donnée                                    | Source (toutes réelles, lues en direct puis gardées sur disque)                                                                                                                                                                                                                  | Fichier                                               |
| ----------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| Météo de la ferme 1985–2024 (étapes 2–3)  | **NASA POWER** au point de la ferme, une seule requête par lieu pour le plan et pour le bilan d'eau (température, pluie, humidité, vent, rayonnement, humidité racinaire MERRA-2, 1984–2024)                                                                                       | `data_access/nasa_power.py`, `weather_providers.py`   |
| Modèles climatiques (cas 2)               | **NASA NEX-GDDP-CMIP6** par le service de projections de NASA POWER : l'ensemble des modèles, 3 scénarios (SSP1-2.6, SSP2-4.5, SSP3-7.0) cherchés comme 3 modèles. Deltas mensuels mesurés depuis 2015–2034 (le service n'a pas les runs historiques), ajoutés à la météo récente avancée par la tendance jusqu'à 2015–2034 | `data_access/power_projection.py`                     |
| Climat observé de la grille (étape 4)     | **NASA POWER regional** : les ~350 cases de 0,5° × 0,625° d'une boîte de 10° × 10° autour de la ferme, leurs 5 indicateurs de 2011 à 2024 (42 requêtes en parallèle, une fois par région)                                                                                         | `data_access/power_grid.py`                           |
| Cases cultivées, cultures et enchaînements des jumeaux (4–6) | **AAC, Inventaire annuel des cultures** (Canada, 2017–2024) et **USDA Cropland Data Layer** (États-Unis, Planetary Computer, 2014–2021) : 4 096 points par case, lus seulement pour les cases candidates ; sol des jumeaux : **SoilGrids 2.0** | `data_access/twin_crops.py`                           |
| Valeur du précédent (étape 7)             | **pas encore calculée** (verdure NASA HLS) : laissée inconnue, le critère rendement est neutre et le plan liste les lacunes ; aucun chiffre d'exemple                                                                                                                              | —                                                     |
| Mesures et sol des sections (étapes 5 et 8) | pente **Copernicus DEM** (Open-Meteo) sur le contour, jours de forte pluie **NASA POWER**, jours de sol nu **NDVI MODIS** (Planetary Computer, une requête par an), sol **SoilGrids 2.0** 0–30 cm au centre ; l'analyse de sol du fermier remplace SoilGrids                       | `data_access/field_measures.py`, `soilgrids.py`, `modis_ndvi.py` |
Le plan dit toujours d'où viennent ses chiffres (`meta.sources`, affiché en haut des écrans). `meta.demo` vaut `false` avec le serveur ; seuls les tests utilisent encore les données fictives de la référence `field_shift.py` (`tests/helpers/`, jamais le serveur), pour vérifier que l'algorithme donne les mêmes plans qu'elle.

### Les sources d'un lieu

L'algorithme ne lit aucun service lui-même : `PlanService` lui donne la météo de la ferme, le modèle d'eau du lieu et ses `PlaceSources` (modèles climatiques, grille de climats observés, vérification des cases cultivées, preuves des jumeaux), lues par `data_access/place_data.py`. Les tests lui donnent celles de la référence (`tests/helpers/reference_place.py`).

Tout ce que répondent les services est gardé sur disque (`data_access/disk_cache.py`, dossier `api/.cache_field_shift/`, exclu de git) : une requête n'est faite qu'une fois, même après un redémarrage du serveur ; un échec n'est jamais gardé.

## Les règles importantes, en bref

- **Positions.** Un cycle de C ans avec une culture tous les f mois a N = 12C / f positions. Une culture appartient à la position où elle est récoltée (« blé 2028 »). Les positions commencent en janvier (12 mois) ou en février (6 et 4 mois).
- **Climat visé.** La dernière année du cycle décide : dans les 10 ans de l'année d'utilisation → tendance NASA POWER (les 20 dernières années décalées jusqu'au milieu du cycle, la pluie n'est pas prolongée) ; au-delà → deltas mensuels de chaque modèle appliqués à NASA POWER 1985–2014, fenêtre de 20 ans centrée sur le cycle.
- **Contraintes dures.** Calendrier et gel, culture d'hiver qui survit au minimum de janvier, enchaînements de cultures vendues observés chez les jumeaux (le dernier vers le premier compris), délais de retour minimum (avec l'historique et le cycle suivant), pas deux jachères de suite, fermeture du cycle, départ après la culture en place.
- **Priorités et note.** Le fermier classe **4 priorités**, les mêmes que les mesures du classement des rotations : `rendement` (valeurs de précédent chez les jumeaux), `eau` (note de `water_use`), `protection_sol` (part du temps où le sol est couvert par une culture vivante, couverts compris) et `ravageurs` (délais de retour). Note = moyenne pondérée des priorités connues × 100 ; poids = rank order centroid du classement (52 / 27 / 15 / 6 % ; une priorité absente garde 25 % du plus petit poids), protection du sol × (1 + risque d'érosion), eau × (1 + risque eau). Les cinq autres critères de la référence (fourrage, azote, matière organique, marché, réserve) ne sont plus classés ni notés ; le bétail ne sert plus. Le scoreur sait encore les calculer quand un profil les demande (`V51_CRITERIA_IDS`) : c'est ce que font les tests de parité avec `field_shift.py`.
- **Eau.** Le critère eau n'est plus une valeur fixe par culture : c'est la note de `water_use` pour la **chaîne entière** (dates de semis et de récolte, couverts compris), simulée sur la météo quotidienne du cycle avec le sol et la pente du lieu. Avec plusieurs modèles climatiques, une note par modèle : la moyenne est le critère, la pire est gardée à côté. Le risque eau de l'étape 8 est la **pression sur l'eau** de la ferme sur la même météo (aridité, baisse de la pluie d'été, nappes, stress mesuré) ; une parcelle irriguée en garde 40 %. Une chaîne partielle n'a pas de note eau (critère inconnu, laissé hors de la moyenne) ; parmi les chaînes complètes, la simulation n'est lancée que pour celles qui peuvent encore entrer dans les 3 meilleures (borne : note eau de 1), ce qui donne le même résultat que de toutes les simuler.
- **Garder ou changer.** On garde la chaîne en place (rotation du fermier au cycle 1, puis chaîne du cycle précédent) si elle respecte les délais, si ses cultures poussent encore chez les jumeaux et si elle est à 5 points ou moins de la meilleure.
- **Robustesse.** Chaque chaîne adoptée est rejouée dans les cycles suivants ; on garde sa pire note, ou « devient infaisable plus tard ».

## Écarts avec la référence

Ils sont volontaires, limités, et testés (`tests/test_algorithm_units.py` et `tests/test_twins_and_diagnostic.py`) :

| Écart                                                                                                                                           | Pourquoi                                                                                                              | Effet sur les scénarios de référence                                                                                                                        |
| ----------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| La maturité d'une culture d'été se calcule à partir du **mois de l'année** du semis, pas mise en cache à partir de la première date absolue vue | le résultat ne dépend plus de l'ordre des appels                                                                      | mêmes chaînes et décisions ; récoltes décalées d'au plus 0,05 mois, notes de moins de 0,1 point (le script d'export applique le même calcul à la référence) |
| Sigma est lu sur la **queue haute** de la loi du χ (`isf(sf(d))`) au lieu de `ppf(cdf(d))`                                                      | `cdf` arrondit à 1 dès que d dépasse ~8 : toutes les cases lointaines deviennent `inf` et on ne peut plus les classer | identique jusqu'à ~5σ ; au-delà, de l'ordre de 10⁻⁴ en valeur relative (la référence perd des chiffres)                                                     |
| **Sans culture en place**, les enchaînements du critère rendement se lisent dans l'ordre (A → B, B → C…)                                        | la référence associait chaque culture à elle-même (`zip(seq, seq)`), ce qui rendait le critère neutre                 | seule la parcelle libre du scénario `variant-sans-fourragere-libre` diffère (exclue du test de référence)                                                   |
| Une culture en place **hors des fiches** (pomme de terre…) entre quand même dans l'historique                                                   | la référence l'oubliait, donc ses délais de retour n'étaient pas contrôlés                                            | aucun                                                                                                                                                       |
| La réserve se compte par **semence** : le soya en double culture utilise des semences de soya                                                   | la référence demandait une semence « Soya 2e culture »                                                                | aucun (la double culture n'apparaît qu'après 2035, hors du cycle 1)                                                                                         |
| Un climat **sans gel** n'empêche aucune culture (dates de gel `None`)                                                                           | en Python, une moyenne sur zéro année donne `nan`, qui se comporte de façon surprenante dans les comparaisons         | aucun                                                                                                                                                       |
| Une covariance **singulière** (un indicateur qui ne varie jamais) reçoit une petite crête sur la diagonale au lieu d'arrêter le calcul          | `numpy.linalg.solve` lève une erreur et arrête tout                                                                   | aucun                                                                                                                                                       |
| Aucune chaîne faisable : le cycle est marqué `aucune` et les cycles suivants ne sont pas calculés                                               | la référence lève `RuntimeError` pour toute la ferme                                                                  | aucun                                                                                                                                                       |
| L'historique se donne **année par année** (`{ year, crop }`)                                                                                    | plus clair pour le fermier que la liste « la plus récente en dernier » ; mêmes occupations que la référence           | aucun                                                                                                                                                       |

## Points à revoir avec un agronome

Ils viennent de l'algorithme lui-même, pas du portage :

- La note favorise parfois la **jachère couverte de seigle** (bonne note d'érosion) : c'est déjà signalé dans le PDF ; les fiches des cultures sont à revoir.
- **Eau, décisions d'équipe en attente :** la division par 2,5 du risque eau d'une parcelle irriguée est gardée, alors que l'irrigation compte déjà dans la note eau (sous-note B) ; l'eau bue par les couverts est comptée comme perdue dans la sous-note C ; le travail du sol n'est pas une entrée (toutes les chaînes sont notées en travail conventionnel) ; le foin est noté avec la fiche « prairie » de `water_use`.
- **Eau, baisse de pluie prévue :** l'ancien risque comptait la baisse de pluie d'été prévue pour le cycle. La pression sur l'eau compare les deux moitiés de la météo du cycle, ce qui ne voit pas un changement appliqué à toutes les années par un modèle climatique : cette baisse ne passe plus que par l'aridité.
- Les fiches, les tolérances de sol, les poids des risques et l'avance des récoltes (3 jours par °C) sont **indicatifs**.
- Les délais Fruchtfolge + SARE sont prudents : la rotation maïs-soya de 2 ans est toujours en alerte.

## Tests

`pytest`, dans [`api/tests/`](../api/tests/) :

| Fichier                        | Ce qu'il vérifie                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| ------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `test_climate.py`              | étapes 2 et 3 contre la référence, sur une météo synthétique (un générateur à entiers, identique dans le script d'export de la référence et dans les tests)                                                                                                                                                                                                                                                                                           |
| `test_twins_and_diagnostic.py` | sigma de chaque case, choix des jumeaux, sol, rotations canoniques, verdure → précédent, jumeaux, diagnostic                                                                                                                                                                                                                                                                                                                                          |
| `test_return_delays.py`        | minimum / recommandé des 24 cultures, violations, vigilances, critère ravageurs, cultures impossibles, historique, poids                                                                                                                                                                                                                                                                                                                              |
| `test_reference_plans.py`      | **17 plans de parcelles sur 9 scénarios** (4/12/12, 4/6/8, 3/12/9, 5/12/10, 2/12/6, 3/4/3, réserve stricte, bétail + maladie + irrigation, sans fourragère) : chaînes, dates, notes, critères, couverts, lacunes, semences, alertes, alternatives, robustesse, libellé. L'eau y est celle de la référence (valeur fixe par culture, risque à quatre mesures), donnée au planificateur comme modèle d'eau de test (`tests/helpers/reference_water.py`) |
| `test_end_to_end_reference.py` | **toute la chaîne** : la météo fictive de la référence (mêmes nombres aléatoires), les modèles, la recherche de jumeaux et la planification redonnent les calendriers de climat et les plans de la référence                                                                                                                                                                                                                                          |
| `test_algorithm_units.py`      | les écarts volontaires ci-dessus, les dates, le temps, les sources de démonstration, la mémoire des lieux                                                                                                                                                                                                                                                                                                                                             |
| `test_field_shift_eau.py`      | l'adaptateur `water_use` sans réseau : note entre 0 et 1, deux chaînes différentes → deux notes, sorgho–blé d'hiver > maïs continu en climat sec, pression plus forte en climat sec, mêmes notes que `water_use` appelé directement, chaîne → rotation, une note par modèle climatique, sources facultatives, plan complet                                                                                                                            |
| `tests/water_use/`             | les tests du module `water_use` lui-même (66, plus 11 sur les vraies bases avec `WATER_USE_RESEAU=1`)                                                                                                                                                                                                                                                                                                                                                 |
| `test_api.py`                  | l'API : plans valides pour le schéma, entrées refusées (422), CORS, météo NASA POWER lue une fois par lieu, repli sur la météo fictive                                                                                                                                                                                                                                                                                                                |
| `test_contract.py`             | les identifiants du schéma sont ceux du serveur, les exemples respectent le schéma et sont à jour                                                                                                                                                                                                                                                                                                                                                     |
| `test_architecture.py`         | les couches du serveur : chaque paquet n'importe que ceux en dessous de lui, et `algorithm/` n'utilise que numpy et scipy (ni FastAPI ni Pydantic)                                                                                                                                                                                                                                                                                                    |

Côté front end, `tests/contract.test.js` vérifie que les écrans connaissent les mêmes identifiants que le schéma et que le client HTTP lit bien les réponses et les refus du serveur.

Les fichiers de référence sont dans `tests/fixtures/`. Pour les régénérer après une nouvelle version de `field_shift.py` :

```bash
python tests/fixtures/export_reference.py <chemin/vers/field_shift.py> tests/fixtures
```

(Python 3 avec numpy, scipy, xarray et pandas.) Le script affiche, pour chaque scénario, si la maturité « canonique » laisse les chaînes et les décisions inchangées.

## Ajouter ou modifier…

| Je veux…                          | Où                                                                                                                                                                                                                                        |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| une culture                       | une fiche dans `reference/crops.py` (`CROP_SHEETS`, `CROP_NAMES`) et ses délais dans `reference/return_delays.py` ; côté écrans : `data/reference/crops.js`, une texture dans `frontend/ui/textures.js` ; le schéma (`SheetId`, `CropId`) |
| changer un seuil ou une tolérance | `algorithm/config/` (et le dire dans ce document)                                                                                                                                                                                         |
| une priorité de la note           | `reference/criteria.py` et `reference/measures.py`, son calcul dans `chain/chain_scorer.py`, `data/reference/criteria.js` pour les écrans, le schéma (`CriterionId`)                                                                      |
| une vraie source de données       | `algorithm/sources/` ou `data_access/` (même interface que la source fictive), branchée dans `FieldShiftAlgorithm` ou `PlanService`                                                                                                       |
| un nouveau champ du plan          | `contract/farm_plan.py` et `contract/plan_mapper.py`, puis le schéma (`backend/contract/field-shift.schema.json`), `ALGO_CONTRACT.md`, et `make_examples`                                                                                 |
