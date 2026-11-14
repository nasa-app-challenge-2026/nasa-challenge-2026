# Serveur de l'algorithme Field Shift

L'algorithme de rotations (_Field Shift — pipeline v5.1_) servi par **FastAPI**. Le front end lui envoie une ferme (`POST /plan`) et reçoit, pour chaque section, un plan cycle par cycle.

- Le fonctionnement de l'algorithme, étape par étape : [`docs/ALGORITHME.md`](../../docs/ALGORITHME.md)
- Le contrat avec le front end : [`docs/ALGO_CONTRACT.md`](../../docs/ALGO_CONTRACT.md) et [`../contract/field-shift.schema.json`](../contract/field-shift.schema.json)

## Lancer le serveur

Il faut Python 3.11 ou plus.

```bash
cd backend/server
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

## Réglages (variables d'environnement)

| Variable                   | Valeur                                                                                                                                | Par défaut                                          |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| `FIELD_SHIFT_WEATHER`      | `nasa` : météo réelle de NASA POWER ; `demo` : météo fictive, sans réseau                                                             | `nasa`                                              |
| `FIELD_SHIFT_CORS_ORIGINS` | adresses des sites autorisés à appeler le serveur, séparées par des virgules (ex. `https://equipe.github.io`)                           | les serveurs de développement du front (`localhost:5173` et `4173`) |

| `FIELD_SHIFT_DATA_SOURCES` | chemin du fichier JSON des adresses des sources de données (voir [Sources de données](#sources-de-données-nasa-et-partenaires)) | `data_sources.json` s'il existe dans le dossier de lancement |
| `FIELD_SHIFT_URL_<SOURCE>` | adresse d'une source de données ; l'emporte sur le fichier | voir `GET /data-sources` |

Si NASA POWER ne répond pas, le serveur utilise la météo fictive et le plan le dit (`meta.sources.farmWeather`). Il retente NASA POWER à la requête suivante.

## Les routes

| Route          | Rôle                                                                                              |
| -------------- | ------------------------------------------------------------------------------------------------- |
| `POST /plan`   | `FarmInput` → `FarmPlan` : planifie toutes les sections de la ferme. Une entrée invalide donne un `422` qui dit quel champ est faux. |
| `GET /health`  | `{ "status": "ok", … }` : le serveur répond.                                                      |

| `POST /rotations/rank` | `RankingInput` → `RotationRanking` : classe les rotations candidates de chaque section sur les quatre mesures. |
| `POST /measures/protection-sol` | la même demande, classée sur la seule protection du sol (érosion et infiltration). **Calculée.** |
| `POST /measures/rendement` · `/measures/eau` · `/measures/ravageurs` | la même demande, sur une seule mesure. **Routes prêtes, logique à écrire : elles répondent `501`.** |
| `GET /measures` | les quatre mesures, et lesquelles sont calculées. |
| `GET /crops` | les cultures qu'une rotation peut contenir, avec leurs notes de protection du sol. |
| `GET /data-sources` | les sources de données et les adresses avec lesquelles le serveur tourne. |

Un plan de 4 sections sur 12 ans prend environ 0,3 s (plus le premier téléchargement de la météo d'un lieu, une fois : 0,7 Mo, gardé en mémoire).

## Organisation du code

```
field_shift/
  api/             l'application FastAPI : routes, réglages (aucune logique métier)
  contract/        le format d'échange : modèles Pydantic de FarmInput et FarmPlan (camelCase sur le fil),
                   et les deux traducteurs : entrée → objets de l'algorithme, résultats → plan
                   rotation_ranking.py et ranking_mapper.py : la même chose pour le classement
  services/        RankingService : réunit les conditions de chaque section, lance le classement
                   PlanService : lit la requête, obtient la météo, lance l'algorithme, garde les lieux en mémoire
  data_access/     l'accès au réseau : NASA POWER et les sources de météo (réelle, fictive, repli)
                     data_source_config.py  TOUTES les adresses des sources, au même endroit
                     site_data.py           pente, sol, pluie, mesures satellites d'une section
  algorithm/       L'ALGORITHME, sans aucun code web (voir docs/ALGORITHME.md)
    config/          toutes les constantes, nommées et commentées
    timeline/        les dates (mois décimaux depuis janvier 2000)
    weather/         une série météo quotidienne
    numerics/        deux petits outils numériques (borner entre 0 et 1, variation en pourcents)
    climate/         étapes 2 et 3 : les 5 indicateurs, le climat visé de chaque cycle
    twins/           étapes 4 à 7 : jumeaux climatiques, sol, rotations observées, valeur du précédent
    diagnostic/      étape 8 : risques d'érosion et d'eau
    delays/          délais de retour (contraintes dures, critère ravageurs, vigilances)
    chain/           étape 9b : candidates, placement, couverts, note sur 9 critères, recherche en faisceau
    planning/        étape 10 : entrées du fermier, plan cycle par cycle, robustesse
    report/          les messages en français et le libellé des chaînes
    sources/         d'où viennent les données (aujourd'hui des données d'exemple, voir ALGORITHME.md)
    rotation/        classement : une rotation candidate, ses phases mois par mois
    soil_protection/ classement : la mesure protection du sol (indice RPI, érosion RUSLE, infiltration)
    ranking/         classement : les quatre mesures, les poids des priorités, le tri
  reference/       les données fixes : fiches des cultures, délais de retour et maladies, critères, limites
                   notes de protection du sol des cultures (soil_protection.py), les quatre mesures
  tools/           make_examples : régénère les plans d'exemple du contrat
tests/             pytest : l'algorithme contre sa référence Python, l'API, le contrat, les couches
```

Une règle : **`algorithm/` n'importe ni FastAPI ni Pydantic**. Il reçoit et rend des objets Python ordinaires ; c'est `contract/` qui les traduit vers et depuis le JSON.

Plus généralement, les paquets ne s'importent que dans un sens : `api → services → contract, data_access → algorithm → reference`. `tests/test_architecture.py` le vérifie, et vérifie aussi les bibliothèques que chaque paquet a le droit d'utiliser (`algorithm/` : numpy et scipy seulement) : un import dans le mauvais sens fait échouer les tests.

## Tests et qualité

```bash
pytest                   # plus de 230 tests, environ 15 s, sans réseau
ruff check .             # lint
ruff format --check .    # formatage
```

Les tests les plus importants comparent le code à la **référence Python de l'équipe** (`field_shift.py` v5.1) : mêmes chaînes, mêmes décisions, mêmes notes sur 17 plans de parcelles, et la chaîne complète de la météo au plan (`tests/test_reference_plans.py`, `tests/test_end_to_end_reference.py`). Les fichiers de référence sont dans `tests/fixtures/` ; pour les régénérer après une nouvelle version de `field_shift.py` (il faut aussi xarray et pandas) :

```bash
python tests/fixtures/export_reference.py <chemin/vers/field_shift.py> tests/fixtures
```

Après un changement de l'algorithme ou du contrat, régénérez les plans d'exemple (le test `test_plans_are_what_the_server_returns_now` le rappelle) :

```bash
python -m field_shift.tools.make_examples
```

## Classement des rotations

`POST /rotations/rank` reçoit le lieu du champ et ses sections, la durée de la simulation, les priorités, et les rotations à comparer. Pour chaque section, chaque rotation reçoit **quatre mesures** ; elles sont additionnées avec les priorités comme poids, et les rotations reviennent classées, la meilleure d'abord, avec leurs mesures.

| Mesure (`id`)    | Ce qu'elle mesure                | État                          |
| ---------------- | -------------------------------- | ----------------------------- |
| `rendement`      | rendement, en kg/ha              | route prête, logique à écrire |
| `eau`            | demande en eau                   | route prête, logique à écrire |
| `protection_sol` | érosion et infiltration de l'eau | **calculée**                  |
| `ravageurs`      | ravageurs et maladies            | route prête, logique à écrire |

```
score d'une rotation = 100 × Σ poids(m) × note(m) / Σ poids(m)      sur les mesures m disponibles
```

Une mesure pas encore calculée revient avec `available: false` et reste hors du score ; le poids des autres est remis à l'échelle. Tant que seule la protection du sol existe, le score est donc la note de protection du sol, quelles que soient les priorités.

### Une demande

```json
{
  "location": { "lat": 45.5, "lon": -73.0 },
  "simulationYears": 6,
  "priorities": { "protection_sol": 2, "rendement": 1, "eau": 1, "ravageurs": 1 },
  "rotations": [
    { "id": "actuelle", "phases": ["mais", "soya"] },
    { "id": "couvert", "phases": ["mais", { "crop": "seigle", "months": 6 }, "soya"] },
    { "id": "prairie", "phases": ["luzerne-3", "mais", "ble-automne"] }
  ],
  "sections": [
    { "id": "A", "areaHa": 12, "site": { "slopePct": 2 } },
    { "id": "B", "site": { "slopePct": 9, "sandPct": 20, "clayPct": 15 } }
  ]
}
```

- **`priorities`** : des poids (`{mesure: nombre}`, seules les proportions comptent) ou un classement (`["protection_sol", "rendement"]`, la plus importante d'abord). Absent : poids égaux.
- **`rotations`** : chaque phase est une culture seule (`"mais"` : elle prend sa saison habituelle, puis le sol reste nu jusqu'à la fin de l'année) ou une culture avec sa durée (`{"crop": "seigle", "months": 6}` ; `"crop": null` pour un sol nu). Le cycle se répète pendant toute la simulation. Les identifiants de cultures sont ceux de `GET /crops` ; les fiches du plan (`luzerne-3`) sont acceptées.
- **Sans `rotations`** : donnez `crops` (la sélection de cultures) et `cycleYears` ; le serveur construit toutes les rotations d'une culture par an (200 au plus, sinon `422`).
- **`sections[].site`** : ce qu'on sait de la section (pente, texture, Ksat, NDVI…). Tout est facultatif : ce qui manque est lu dans les sources de données configurées, sinon prend la valeur par défaut. La réponse dit, valeur par valeur, d'où elle vient (`site[].origin`).

La documentation interactive (<http://localhost:8000/docs>) décrit chaque champ de la demande et de la réponse.

### La mesure « protection du sol »

Le code est dans `field_shift/algorithm/soil_protection/`, les constantes (toutes nommées et sourcées) dans `algorithm/config/soil_protection.py`, les notes des cultures dans `reference/soil_protection.py`. Trois résultats, puis une note :

1. **Indice de protection de la rotation (RPI)**, de 1 à 5. Chaque culture a trois notes de 1 à 5 (racines → infiltration, résidus → érosion, durée de la canopée → couverture) ; `SC` est leur moyenne, pondérée par les mois d'occupation ; le sol nu compte pour 1. Moins de 2,5 : risque élevé ; de 2,5 à 3,9 : protection modérée ; 4 et plus : excellente. Le RPI _ajusté_ ramène les notes de couverture et d'infiltration à la vigueur réelle (NDVI, ECOSTRESS) quand elle est connue.
2. **Perte de sol** `A = R × K × LS × C × P` (structure de RUSLE, en t/ha/an) : `LS` vient de la pente, `K` de la texture et de la matière organique, `R` de la pluie, et `C` de la rotation (canopée, résidus qui restent au sol après la récolte et se décomposent, sol non travaillé sous les pérennes). Note d'érosion : `1 / (1 + A / T)`, avec `T` = 11,2 t/ha/an, la perte tolérable.
3. **Infiltration effective** : Ksat du sol × effet de la rotation (+59,2 % sous une pérenne, +34,8 % sous un couvert, d'après la méta-analyse de Basche et DeLonge, 2019) × humidité du sol (SMAP), comparée à l'intensité d'une forte averse.

```
note = 0,3 × (RPI ajusté − 1) / 4  +  0,4 × note d'érosion  +  0,3 × part de l'averse infiltrée
```

**Limites à connaître.** Les notes des cultures sont indicatives (les exemples de la matrice sont repris tels quels, les autres cultures sont classées par analogie) : un agronome doit les vérifier. La perte de sol sert à _comparer_ des rotations sur un champ, pas à prédire des tonnes : `C` est pondéré par le temps et non par la répartition de l'érosivité dans l'année, `K` ne varie pas avec les saisons, la rugosité et les billons sont ignorés, et les paramètres de `C` (couverture par les résidus, canopée, demi-vie des résidus) ne sont pas calés sur des mesures. Sans source GPM IMERG, `R` est estimé à partir de la pluie annuelle (Renard et Freimund, 1994, calé sur les États-Unis). Les parts 0,3 / 0,4 / 0,3 de la note sont un choix à valider par l'équipe.

### Écrire une des trois autres mesures

Tout est déjà branché (routes, contrat, poids, classement). Il reste à remplir la méthode `evaluate` de la classe de la mesure dans `field_shift/algorithm/ranking/measures.py` (`YieldMeasure`, `WaterDemandMeasure`, `PestsMeasure`) : elle reçoit la rotation et le contexte de la section, et rend un `MeasureResult` avec une note de 0 à 1 et sa valeur (kg/ha pour le rendement). Puis passer `implemented = True` : la route `/measures/…` cesse de répondre `501` et la mesure entre dans le score.

## Sources de données (NASA et partenaires)

**Toutes les adresses sont au même endroit** : `field_shift/data_access/data_source_config.py`. Pour en donner ou en changer une, sans toucher au code :

1. copier `data_sources.example.json` en `data_sources.json` (dans `backend/server` ; ignoré par git, car il peut contenir des jetons) et y coller les adresses ;
2. ou définir une variable d'environnement `FIELD_SHIFT_URL_<SOURCE>`, par exemple `FIELD_SHIFT_URL_SLOPE_PCT` (elle l'emporte sur le fichier ; `FIELD_SHIFT_JSON_PATH_<SOURCE>` et `FIELD_SHIFT_SCALE_<SOURCE>` existent aussi).

```json
{
  "slope_pct": { "url": "https://…/pente?lat={lat}&lon={lon}", "jsonPath": "data.slope" },
  "soil_saturation": {
    "url": "https://…/smap?lat={lat}&lon={lon}",
    "jsonPath": "value",
    "scale": 0.01,
    "headers": { "Authorization": "Bearer <jeton>" }
  }
}
```

Une source est une adresse HTTP GET où `{lat}` et `{lon}` sont remplacés par le point de la section et qui répond en JSON ; `jsonPath` est le chemin du nombre dans la réponse (`resultats.0.valeur`), `scale` le convertit dans l'unité attendue. Si une source demande un autre format (fichier raster, requête SQL SSURGO…), il faut lui écrire un lecteur dans `data_access/`, sur le modèle de `nasa_power.py`.

| Clé                                          | Jeu de données             | Valeur attendue                                   | Sans adresse                       |
| -------------------------------------------- | -------------------------- | ------------------------------------------------- | ---------------------------------- |
| `power_daily`                                | NASA POWER                 | météo quotidienne de la ferme (pour `POST /plan`) | configurée : l'API publique        |
| `annual_rain_mm`                             | NASA POWER                 | pluie annuelle, mm                                | configurée : l'API publique        |
| `slope_pct`, `slope_length_m`                | SRTM                       | pente en %, longueur de pente en m                | 3 %, 60 m                          |
| `sand_pct`, `clay_pct`, `organic_matter_pct` | USDA SSURGO                | texture et matière organique, %                   | un limon : 40 / 20 / 3             |
| `ksat_mm_h`                                  | USDA SSURGO                | conductivité hydraulique à saturation, mm/h       | 10                                 |
| `k_factor`                                   | USDA SSURGO                | érodibilité K, unités SI                          | estimée à partir de la texture     |
| `ndvi`                                       | Landsat 8/9, MODIS / VIIRS | NDVI moyen de la saison de croissance             | pleine vigueur (notes théoriques)  |
| `root_activity`                              | ECOSTRESS                  | ET réelle / ET potentielle, 0 à 1                 | pleine activité (notes théoriques) |
| `r_factor`                                   | GPM IMERG                  | érosivité R, MJ·mm/(ha·h·an)                      | estimée à partir de la pluie       |
| `storm_intensity_mm_h`                       | GPM IMERG                  | intensité d'une forte averse, mm/h                | 25                                 |
| `soil_saturation`                            | SMAP                       | saturation du sol en surface, 0 à 1               | sol non saturé                     |

Une source absente, en panne ou qui rend une valeur hors limites ne fait jamais échouer une demande : le modèle prend sa valeur par défaut et la réponse le dit. `GET /data-sources` montre la configuration en cours (sans les paramètres des adresses ni les en-têtes, qui peuvent contenir une clé). En mode `FIELD_SHIFT_WEATHER=demo`, aucune source n'est lue.

## Héberger le serveur

Le front publié sur GitHub Pages appelle le serveur depuis le navigateur de chaque visiteur : le serveur doit donc être en ligne, joignable en HTTPS, et autoriser l'adresse du site :

```bash
FIELD_SHIFT_CORS_ORIGINS=https://<compte>.github.io python -m uvicorn field_shift.api.main:app --host 0.0.0.0 --port 8000
```

Puis, dans les variables du dépôt GitHub (_Settings → Secrets and variables → Actions → Variables_), `VITE_ALGO_URL` = l'adresse publique du serveur. Aucun secret n'est nécessaire : NASA POWER est public.
