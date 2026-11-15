# Serveur de l'algorithme Field Shift

L'algorithme de rotations (_Field Shift — pipeline v5.1_) servi par **FastAPI**. Le front end lui envoie une ferme (`POST /plan`) et reçoit, pour chaque section, un plan cycle par cycle.

- Le fonctionnement de l'algorithme, étape par étape : [`docs/ALGORITHME.md`](../docs/ALGORITHME.md)
- Le contrat avec le front end : [`docs/ALGO_CONTRACT.md`](../docs/ALGO_CONTRACT.md) et [`backend/contract/field-shift.schema.json`](../backend/contract/field-shift.schema.json)

## Lancer le serveur

Il faut Python 3.11 ou plus.

```bash
cd api
python -m venv .venv
.venv\Scripts\activate          # Windows ; sous Linux et macOS : source .venv/bin/activate
pip install -e ".[dev]"
python -m uvicorn field_shift.api.main:app --port 8000
```

- Documentation interactive de l'API : <http://localhost:8000/docs>
- Test rapide : <http://localhost:8000/health>
- `--reload` relance le serveur à chaque modification du code.

Le serveur fait deux choses : le **plan des rotations** par jumeau climatique (`POST /plan`, décrit dans `docs/ALGORITHME.md`) et le **classement de rotations candidates** sur quatre mesures (`POST /rotations/rank`, décrit [plus bas](#classement-des-rotations)).

Le front lit son adresse dans `VITE_ALGO_URL` (par défaut `http://localhost:8000` avec `npm run dev`).

## Premier calcul d'un lieu

Le premier plan d'un nouveau lieu lit toutes ses données réelles : la météo NASA POWER (une seule requête pour le plan et le bilan d'eau), la grille NASA POWER des jumeaux (42 requêtes en parallèle), les projections NEX-GDDP-CMIP6, les cartes de cultures des jumeaux candidats, SoilGrids, le relief et le NDVI des sections. Mesuré le 15 novembre 2026 sur la ferme de démo : **65 s** à froid, **0,7 s** ensuite, **11 s** après un redémarrage du serveur (tout est relu depuis le disque). Le classement (`/rotations/rank`) : 65 s à froid (MODIS de l'ORNL DAAC prend jusqu'à une minute par requête ; s'il ne répond pas, le ratio annuel MOD16A3GF de Planetary Computer le remplace et la lecture le dit), 0,1 s ensuite.

## Réglages (variables d'environnement)

| Variable                   | Valeur                                                                                                                  | Par défaut                                                          |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| `FIELD_SHIFT_CORS_ORIGINS` | adresses des sites autorisés à appeler le serveur, séparées par des virgules (ex. `https://equipe.github.io`)           | les serveurs de développement du front (`localhost:5173` et `4173`) |
| `FIELD_SHIFT_DATA_SOURCES` | chemin du fichier JSON des adresses des services de données (voir [Sources de données](#sources-de-données))           | `data_sources.json` s'il existe dans le dossier de lancement        |
| `FIELD_SHIFT_CACHE_DIR`    | dossier où le serveur garde les réponses des services de données (une requête n'est faite qu'une fois, même après un redémarrage ; un échec n'est jamais gardé) | `api/.cache_field_shift/` (exclu de git)                           |
| `FIELD_SHIFT_URL_<SOURCE>` | adresse d'un service de données ; l'emporte sur le fichier                                                              | voir `GET /data-sources`                                            |
| `FIELD_SHIFT_WORKERS` | nombre de processus qui calculent les sections d'une ferme en même temps ; `0` : une section après l'autre | un par autre processeur, 3 au plus |

**Il n'y a pas de mode démo ni de valeur de repli.** Le serveur lit toujours les données réelles. Quand un service ne répond pas (NASA POWER pour `POST /plan` ; SoilGrids, Open-Meteo, NASA POWER ou MODIS pour le classement), la demande échoue avec un **`502`** dont le `detail` nomme la section et le service en cause ; le service est retenté à la demande suivante (un échec n'est jamais gardé en mémoire).

## Les routes

| Route          | Rôle                                                                                              |
| -------------- | ------------------------------------------------------------------------------------------------- |
| `POST /plan`   | `FarmInput` → `FarmPlan` : planifie toutes les sections de la ferme. Une entrée invalide donne un `422` qui dit quel champ est faux. |
| `GET /health`  | `{ "status": "ok", … }` : le serveur répond.                                                      |

| `POST /rotations/rank` | `RankingInput` → `RotationRanking` : classe les rotations candidates de chaque section sur les quatre mesures. |
| `POST /measures/protection-sol` · `/measures/ravageurs` | la même demande, classée sur la seule protection du sol (érosion et infiltration) ou sur les seuls ravageurs. **Calculées.** |
| `POST /measures/rendement` · `/measures/eau` | la même demande, sur une seule mesure. **Routes prêtes, logique à écrire : elles répondent `501`.** |
| `GET /measures` | les quatre mesures, et lesquelles sont calculées. |
| `GET /crops` | les cultures qu'une rotation peut contenir, avec leurs notes de protection du sol. |
| `GET /data-sources` | les services de données, leur jeu de données, leur publication de référence et leur adresse. |

Un plan de 4 sections sur 12 ans prend environ 12 s avec les vraies données déjà sur disque (mesuré le 15 novembre 2026, 30 s quand les sections sont calculées l'une après l'autre) : presque tout ce temps est la simulation de l'eau du sol des meilleures chaînes. Le même plan redemandé prend 0,3 s. Le premier plan d'un lieu attend en plus la lecture de ses données réelles, gardées ensuite sur disque.

### Ce qui rend le plan rapide (sans toucher à l'algorithme)

- **Les sections sont calculées en même temps**, chacune dans son processus (`services/parallel_plan_service.py`). Une section ne dépend jamais des autres : le plan est exactement celui d'un seul processus (`tests/test_parallel_plan_service.py`). Le serveur calcule la première section, un processus par autre section calcule les suivantes ; la même section retourne toujours au même processus, qui retrouve les notes d'eau qu'il a déjà simulées. `FIELD_SHIFT_WORKERS=0` revient à un seul processus, pour une machine qui a peu de mémoire : chaque processus garde sa copie du lieu.
- **Le lieu est construit une fois** par le serveur avant de partager les sections : ce que répondent ses services de données est alors sur disque, et les autres processus le lisent là.
- **Les réponses sont compressées** (gzip) : un plan fait environ 250 ko de JSON, 25 ko une fois compressé.
- Côté navigateur, le dernier plan est gardé avec la ferme pour laquelle il a été calculé : à la visite suivante il s'affiche tout de suite pendant que le serveur le recalcule, et un réglage déjà calculé pendant la visite n'est pas redemandé (`application/app.js`).

## Organisation du code

```
field_shift/
  api/             l'application FastAPI : routes, réglages (aucune logique métier)
  contract/        le format d'échange : modèles Pydantic de FarmInput et FarmPlan (camelCase sur le fil),
                   et les deux traducteurs : entrée → objets de l'algorithme, résultats → plan
                   rotation_ranking.py et ranking_mapper.py : la même chose pour le classement
  services/        RankingService : réunit les conditions de chaque section, lance le classement
                   ParallelPlanService : les sections d'une ferme calculées en même temps, dans plusieurs processus
                   PlanService : lit la requête, obtient la météo, lance l'algorithme, garde les lieux en mémoire
  data_access/     l'accès au réseau (aucune valeur de repli : un service en panne est une erreur)
                     data_source_config.py  TOUTES les adresses des services, au même endroit
                     nasa_power.py          la météo quotidienne de la ferme (POST /plan)
                     field_shift_eau.py     L'ADAPTATEUR EAU : le seul fichier qui connaît water_use
                     yield_precrops.py      valeur du précédent : le modèle régional de rendement
                                            (note_eau, pression_eau, WaterUseModel)
                     site_readers.py        un lecteur par service : SoilGrids, Open-Meteo, NASA POWER, MODIS
                     site_data.py           appelle en parallèle les services dont une section a besoin
  algorithm/       L'ALGORITHME, sans aucun code web (voir docs/ALGORITHME.md)
    config/          toutes les constantes, nommées et commentées
    timeline/        les dates (mois décimaux depuis janvier 2000)
    weather/         une série météo quotidienne
    numerics/        deux petits outils numériques (borner entre 0 et 1, variation en pourcents)
    climate/         étapes 2 et 3 : les 5 indicateurs, le climat visé de chaque cycle
    twins/           étapes 4 à 7 : jumeaux climatiques, sol, rotations observées, valeur du précédent
    diagnostic/      étape 8 : risques d'érosion et d'eau
    water/           l'interface du modèle d'eau que voit le planificateur (note d'une chaîne, pression)
    pests/           la pression des ravageurs du sol : priorité ravageurs du plan et mesure du classement
    yield_model/     le modèle régional de rendement (vigueur MODIS, cartes de cultures, CMIP6)
    delays/          délais de retour (contraintes dures, vigilances)
    chain/           étape 9b : candidates, placement, couverts, note sur les 4 priorités, recherche en faisceau
    planning/        étape 10 : entrées du fermier, plan cycle par cycle, robustesse
    report/          les messages en français et le libellé des chaînes
    sources/         d'où viennent les données (aujourd'hui des données d'exemple, voir ALGORITHME.md)
    rotation/        classement : une rotation candidate, ses phases mois par mois
    soil_protection/ classement : la mesure protection du sol (indice RPI, érosion RUSLE, infiltration),
                     les modèles publiés (Ksat de Saxton et Rawls, K d'EPIC, R de Renard et Freimund),
                     les statistiques de pluie et de saison (forcing.py)
    terrain/         classement : le contour d'une section (surface, centre), sa pente et sa longueur de pente
    ranking/         classement : les quatre mesures, les poids des priorités, le tri
  reference/       les données fixes : fiches des cultures, délais de retour et maladies, priorités, limites
                   notes de protection du sol des cultures (soil_protection.py), les quatre mesures
water_use/         LE MODULE EAU, autonome : bilan d'eau du sol jour par jour (FAO-56, FAO-33, NRCS)
                   python -m water_use cultures | evaluer | connexions | valider
exemples/          rotations d'exemple de water_use
tests/             pytest : l'algorithme contre sa référence Python, l'API, le contrat, les couches
tests/water_use/   les tests de water_use (11 interrogent les vraies bases : WATER_USE_RESEAU=1)
```

Une règle : **`algorithm/` n'importe ni FastAPI ni Pydantic**. Il reçoit et rend des objets Python ordinaires ; c'est `contract/` qui les traduit vers et depuis le JSON.

Plus généralement, les paquets ne s'importent que dans un sens : `api → services → contract, data_access → algorithm → reference`. `tests/test_architecture.py` le vérifie, et vérifie aussi les bibliothèques que chaque paquet a le droit d'utiliser (`algorithm/` : numpy et scipy seulement) : un import dans le mauvais sens fait échouer les tests.

## L'eau : `water_use`

Le critère **eau** d'une chaîne et le **risque eau** d'une parcelle viennent du module [`water_use/`](water_use/), par un seul fichier : [`field_shift/data_access/field_shift_eau.py`](field_shift/data_access/field_shift_eau.py).

- `note_eau(chaine, meteo_cycle, lat, lon, irrigue, debut, fin)` : la note eau (0 à 1) d'une chaîne, ses sous-notes A, B, C, D, ses alertes et ses chiffres lisibles (demande, manque, irrigation en mm par an, pluie gardée, eau au semis).
- `pression_eau(meteo, et0, debut, fin, nappes_percentile, esi, secheresse_sol)` : la pression sur l'eau de la ferme (0 à 1).
- `WaterUseModel.from_data_bases(lat, lon)` : le modèle d'un lieu, donné au planificateur. Il lit une fois le sol (SSURGO, sinon SoilGrids), la pente (SRTM), la météo complète de NASA POWER (humidité, vent, rayonnement : ET0 de Penman-Monteith) et ce qui mesure la pression (puits USGS ; SMAP et ECOSTRESS avec un compte Earthdata, sinon MERRA-2).

Seul le sol est obligatoire : s'il ne peut pas être lu, `POST /plan` répond **502**. Toute autre base qui ne répond pas est laissée de côté et nommée dans `waterPressure.sources`.

Identifiants (facultatifs) : copier [`.env.exemple`](.env.exemple) en `api/.env` et remplir `EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD` (ou variables d'environnement, ou `~/.netrc`). `.env`, `.cache_donnees/` (réponses des bases) et `resultats/` sont exclus de git. Les tâches SMAP / ECOSTRESS prennent des minutes côté NASA : le serveur n'attend pas, il utilise MERRA-2 et lira le résultat à un prochain plan.

```bash
python -m water_use cultures                                                    # les codes des cultures
python -m water_use evaluer --demo sec --rotations "exemples/*.json"            # sans réseau
python -m water_use evaluer --lat 45.55 --lon -72.98 --rotations "exemples/*.json"
```

Une culture du plan sans code `water_use` (table `WATER_USE_CODES`) est refusée avec un message clair, jamais remplacée. Les formules de `water_use/` ne se modifient pas ici.

## Tests et qualité

```bash
pytest                   # plus de 360 tests, environ 2 min, sans réseau (services simulés)
ruff check .             # lint
ruff format --check .    # formatage
```

Les tests les plus importants comparent le code à la **référence Python de l'équipe** (`field_shift.py` v5.1) : mêmes chaînes, mêmes décisions, mêmes notes sur 17 plans de parcelles, et la chaîne complète de la météo au plan (`tests/test_reference_plans.py`, `tests/test_end_to_end_reference.py`). Les fichiers de référence sont dans `tests/fixtures/` ; pour les régénérer après une nouvelle version de `field_shift.py` (il faut aussi xarray et pandas) :

```bash
python tests/fixtures/export_reference.py <chemin/vers/field_shift.py> tests/fixtures
```

Après un changement de l'algorithme ou du contrat, régénérez les plans d'exemple (le test `test_plans_are_what_the_server_returns_now` le rappelle) :

```bash
python -m tests.helpers.example_plans
```

## Classement des rotations

`POST /rotations/rank` reçoit les sections du champ (chacune avec son contour), la durée de la simulation, les priorités, et les rotations à comparer. Pour chaque section, chaque rotation reçoit **quatre mesures** ; elles sont additionnées avec les priorités comme poids, et les rotations reviennent classées, la meilleure d'abord, avec leurs mesures.

| Mesure (`id`)    | Ce qu'elle mesure                | État                          |
| ---------------- | -------------------------------- | ----------------------------- |
| `rendement`      | rendement, en kg/ha              | route prête, logique à écrire |
| `eau`            | demande en eau                   | route prête, logique à écrire |
| `protection_sol` | érosion et infiltration de l'eau | **calculée**                  |
| `ravageurs`      | ravageurs et maladies du sol     | **calculée** (`algorithm/pests`) |

```
score d'une rotation = 100 × Σ poids(m) × note(m) / Σ poids(m)      sur les mesures m disponibles
```

Une mesure pas encore calculée revient avec `available: false` et reste hors du score ; le poids des autres est remis à l'échelle. Tant que le rendement et l'eau ne sont pas écrits, le score ne compte donc que la protection du sol et les ravageurs.

### Une demande

```json
{
  "simulationYears": 6,
  "priorities": { "protection_sol": 2, "rendement": 1, "eau": 1, "ravageurs": 1 },
  "rotations": [
    { "id": "actuelle", "phases": ["mais", "soya"] },
    { "id": "couvert", "phases": ["mais", { "crop": "seigle", "months": 6 }, "soya"] },
    { "id": "prairie", "phases": ["luzerne-3", "mais", "ble-automne"] }
  ],
  "sections": [
    {
      "id": "A",
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[-73.002, 45.499], [-72.998, 45.499], [-72.998, 45.5015], [-73.002, 45.5015], [-73.002, 45.499]]]
      },
      "site": { "supportPracticeFactor": 1 }
    },
    {
      "id": "B",
      "geometry": { "type": "Polygon", "coordinates": [[[-73.01, 45.51], [-73.005, 45.51], [-73.005, 45.513], [-73.01, 45.51]]] },
      "site": { "supportPracticeFactor": 0.75, "slopePct": 9, "sandPct": 20, "clayPct": 15 }
    }
  ]
}
```

- **`sections[].geometry`** (obligatoire) : le contour de la section, un `Polygon` GeoJSON (RFC 7946) en `[longitude, latitude]` WGS84, fermé (la dernière position répète la première), sans trou, sans croisement, 500 sommets au plus. Le serveur en tire la **surface** et le **centre** (rendus dans `areaHa` et `centroid`), la **pente** (plan ajusté sur les altitudes de la section) et la **longueur de pente** (longueur de la section dans le sens de la pente). Le sol, la pluie et les mesures satellites sont lus au centre.
- **`sections[].site.supportPracticeFactor`** (obligatoire) : le facteur `P` de RUSLE (1 sans pratique de conservation ; plus bas avec courbes de niveau, bandes ou terrasses). Aucun service ne connaît les pratiques d'une ferme.
- **`sections[].site`, le reste** : ce qu'on sait déjà de la section (pente, texture, Ksat, NDVI…). Ce qui est donné l'emporte ; le reste est lu dans les services, et **seuls les services nécessaires sont appelés**. Ksat, K et R sont calculés par un modèle publié s'ils ne sont pas donnés.
- **`priorities`** : des poids (`{mesure: nombre}`, seules les proportions comptent) ou un classement (`["protection_sol", "rendement"]`, la plus importante d'abord). Absent : poids égaux.
- **`rotations`** : chaque phase est une culture seule (`"mais"` : elle prend sa saison habituelle, puis le sol reste nu jusqu'à la fin de l'année) ou une culture avec sa durée (`{"crop": "seigle", "months": 6}` ; `"crop": null` pour un sol nu). Le cycle se répète pendant toute la simulation. Les identifiants de cultures sont ceux de `GET /crops` ; les fiches du plan (`luzerne-3`) sont acceptées.
- **Sans `rotations`** : donnez `crops` (la sélection de cultures) et `cycleYears` ; le serveur construit toutes les rotations d'une culture par an (200 au plus, sinon `422`).

La réponse dit, pour chaque section et chaque valeur, d'où elle vient (`site[].origin` : `section`, le jeu de données, ou `calcul : <modèle>`) et comment elle a été calculée (`site[].method`). `sections[].notes` reprend, en phrases, toutes les valeurs qui ne sont pas lues telles quelles : conversions, statistiques et modèles, avec leurs entrées.

La documentation interactive (<http://localhost:8000/docs>) décrit chaque champ de la demande et de la réponse.

### La mesure « protection du sol »

Le code est dans `field_shift/algorithm/soil_protection/`, les constantes (toutes nommées et sourcées) dans `algorithm/config/soil_protection.py`, les notes des cultures dans `reference/soil_protection.py`. Trois résultats, puis une note :

1. **Indice de protection de la rotation (RPI)**, de 1 à 5. Chaque culture a trois notes de 1 à 5 (racines → infiltration, résidus → érosion, durée de la canopée → couverture) ; `SC` est leur moyenne, pondérée par les mois d'occupation ; le sol nu compte pour 1. Moins de 2,5 : risque élevé ; de 2,5 à 3,9 : protection modérée ; 4 et plus : excellente. Le RPI _ajusté_ ramène les notes de couverture et d'infiltration à la vigueur réelle (NDVI MODIS, ET / ET potentielle MODIS).
2. **Perte de sol** `A = R × K × LS × C × P` (structure de RUSLE, en t/ha/an) : `LS` vient de la pente, `K` de la texture et de la matière organique, `R` de la pluie, et `C` de la rotation (canopée, résidus qui restent au sol après la récolte et se décomposent, sol non travaillé sous les pérennes). Note d'érosion : `1 / (1 + A / T)`, avec `T` = 11,2 t/ha/an, la perte tolérable.
3. **Infiltration effective** : Ksat du sol × effet de la rotation (+59,2 % sous une pérenne, +34,8 % sous un couvert, d'après la méta-analyse de Basche et DeLonge, 2019) × humidité du sol (GWETTOP de NASA POWER), comparée à l'intensité de l'averse de référence.

```
note = 0,3 × (RPI ajusté − 1) / 4  +  0,4 × note d'érosion  +  0,3 × part de l'averse infiltrée
```

**Limites à connaître.** Les notes des cultures sont indicatives (les exemples de la matrice sont repris tels quels, les autres cultures sont classées par analogie) : un agronome doit les vérifier. La perte de sol sert à _comparer_ des rotations sur un champ, pas à prédire des tonnes : `C` est pondéré par le temps et non par la répartition de l'érosivité dans l'année, `K` ne varie pas avec les saisons, la rugosité et les billons sont ignorés, et les paramètres de `C` (couverture par les résidus, canopée, demi-vie des résidus) ne sont pas calés sur des mesures. `R` est estimé à partir de la pluie annuelle (Renard et Freimund, 1994, calé sur les États-Unis) s'il n'est pas donné. La pluie horaire de MERRA-2 est une moyenne sur une maille d'environ 50 km : elle sous-estime les averses locales, donc l'intensité de l'averse de référence. La pente vient d'un modèle d'altitudes à 90 m arrondies au mètre : sur un terrain très plat, une pente de moins de 0,3 % n'est pas vue. Les parts 0,3 / 0,4 / 0,3 de la note sont un choix à valider par l'équipe.

### Écrire une des trois autres mesures

Tout est déjà branché (routes, contrat, poids, classement). Il reste à remplir la méthode `evaluate` de la classe de la mesure dans `field_shift/algorithm/ranking/measures.py` (`YieldMeasure`, `WaterDemandMeasure`, `PestsMeasure`) : elle reçoit la rotation et le contexte de la section, et rend un `MeasureResult` avec une note de 0 à 1 et sa valeur (kg/ha pour le rendement). Puis passer `implemented = True` : la route `/measures/…` cesse de répondre `501` et la mesure entre dans le score.

## Sources de données

Toutes les sources sont des **API publiques, documentées, sans clé**, et chaque jeu de données est décrit par une publication. Les adresses sont **au même endroit** : `field_shift/data_access/data_source_config.py`.

| Clé (`GET /data-sources`) | Service et jeu de données | Ce que le serveur en tire | Référence |
| --- | --- | --- | --- |
| `power_daily` | NASA POWER, API quotidienne (MERRA-2) | météo quotidienne de la ferme (`POST /plan`) | [docs NASA POWER](https://power.larc.nasa.gov/docs/) |
| `power_climatology` | NASA POWER, climatologie (MERRA-2) | pluie annuelle (`PRECTOTCORR` × 365,25) ; humidité relative du sol de surface (`GWETTOP`, moyenne de la saison de croissance) | Gelaro et al., *J. Climate* 30(14), 2017 |
| `power_hourly` | NASA POWER, API horaire (MERRA-2) | intensité de l'averse de référence : moyenne des maxima annuels de la pluie horaire des 10 dernières années complètes | Gelaro et al., 2017 |
| `soilgrids` | SoilGrids 2.0 (ISRIC) | sable, argile, carbone organique, moyenne 0–15 cm ; matière organique = carbone × 1,724 | Poggio et al., *SOIL* 7, 217–240, 2021 |
| `elevation` | Copernicus DEM GLO-90 via Open-Meteo | 81 altitudes sur la section : pente (plan des moindres carrés) et longueur de pente | ESA, doi:10.5270/ESA-c5d3d65 |
| `modis` | MODIS, service de sous-ensembles de l'ORNL DAAC (NASA) | NDVI de la saison de croissance (MOD13Q1, 250 m) ; ET / ET potentielle (MOD16A2, 500 m) | Didan, doi:10.5067/MODIS/MOD13Q1.061 ; Running et al., doi:10.5067/MODIS/MOD16A2.061 ; Mu et al., *Remote Sens. Environ.* 115, 2011 |

Trois valeurs sont **calculées par un modèle publié** quand la section ne les donne pas : Ksat (Saxton et Rawls, *Soil Sci. Soc. Am. J.* 70(5), 2006, matière organique bornée à 8 %), K (EPIC, Williams, 1995) et R (Renard et Freimund, *J. Hydrol.* 157, 1994).

Deux substitutions, faute d'API synchrone : **SMAP** est remplacé par `GWETTOP` de NASA POWER et **ECOSTRESS** par le rapport ET / ET potentielle de MODIS MOD16A2. SMAP et ECOSTRESS ne sont servis au point que par AppEEARS, dont les tâches prennent plusieurs minutes.

Les **notes de protection du sol des cultures** (`reference/soil_protection.py`) ne viennent d'aucune API : il n'existe pas d'API évaluée par des pairs qui les fournisse. La base de cultures de RUSLE2 (USDA NRCS) s'exporte depuis les outils du NRCS mais ne se consulte pas en REST.

Pour changer une adresse (un miroir, un proxy) ou ajouter des en-têtes (un jeton), sans toucher au code : copier `data_sources.example.json` en `data_sources.json` dans `api/` (ignoré par git, car il peut contenir des jetons), ou définir `FIELD_SHIFT_URL_<CLÉ>` (par exemple `FIELD_SHIFT_URL_SOILGRIDS`), qui l'emporte sur le fichier. Un service ne peut pas être coupé : une adresse vide est refusée au démarrage.

## Héberger le serveur

Le front publié sur GitHub Pages appelle le serveur depuis le navigateur de chaque visiteur : le serveur doit donc être en ligne, joignable en HTTPS, et autoriser l'adresse du site :

```bash
FIELD_SHIFT_CORS_ORIGINS=https://<compte>.github.io python -m uvicorn field_shift.api.main:app --host 0.0.0.0 --port 8000
```

Puis, dans les variables du dépôt GitHub (_Settings → Secrets and variables → Actions → Variables_), `VITE_ALGO_URL` = l'adresse publique du serveur. Aucun secret n'est nécessaire : tous les services sont publics.
