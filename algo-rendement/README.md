# `algo-rendement` — Extraction régionale des paires ($A \to B$), Jumeaux Climatiques et optimisation du rendement

Ce module estime **dynamiquement** les écarts de vigueur associés à chaque succession de cultures ($A \to B$) pour une région donnée `(lat, lon)`, ainsi que leur **trajectoire future sous réchauffement climatique (CMIP6 + Jumeaux Climatiques)**, **sans aucun chiffre de transition codé en dur**.

La théorie des jumeaux est conservée : transfert progressif des effets locaux vers ceux d'une région actuellement plus chaude. Les valeurs calculées sont des anomalies relatives de vigueur, interprétées en rendement sous l'hypothèse explicite 1:1. La conversion NASS indique `empiricallyCalibrated: false` ; les observations satellites ne constituent pas une validation de rendement à la parcelle.

Les moyennes comptent toutes les années, y compris celles de luzerne. La culture actuelle remplace l'antécédent cyclique de la première année, sans bonus supplémentaire. Le poids annuel du jumeau dépend du climat de cette année et la confiance suit les sources effectivement utilisées.

Pour l'explication mathématique complète et les cas d'usage détaillés, voir **[`LOGIQUE_ALGO.md`](./LOGIQUE_ALGO.md)**.

Les entrées proviennent des services officiels et de leurs caches : observations et réanalyses historiques, cartes de cultures, et projections climatiques issues de modèles. Aucune donnée fictive ne remplace une source indisponible dans ce pipeline. Les gains calculés restent des estimations du modèle, pas des rendements mesurés. Les données simulées des tests sont isolées dans des dossiers temporaires.

Le front principal est un composant distinct : [`src/algo/index.js`](../src/algo/index.js) utilise encore le moteur de démonstration par défaut. Il faut configurer `VITE_ALGO_MODE=remote` et un serveur compatible avec le contrat pour afficher les résultats d'un moteur distant ; exécuter ce module ne branche pas automatiquement le front.

## 1. Sources de données officielles utilisées

| Couche                                      | Ressource du défi NASA Space Apps                                                                                                             | Rôle dans le calcul des paires                                                                                                                                                                         | Accès / Clé requise                                              |
| :------------------------------------------ | :-------------------------------------------------------------------------------------------------------------------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :--------------------------------------------------------------- |
| **Cartes annuelles des cultures (30 m)**    | **AAC Inventaire annuel des cultures (AAFC `ImageServer/exportImage`)** (Canada / Québec) & **USDA Cropland Data Layer (`usda-cdl`)** (É.-U.) | Télécharge en 1 requête par année la grille complète `64 × 64` (`4 096` pixels) des cultures, puis regroupe les pixels contigus en **champs physiques distincts** (`clusterPixelsIntoDistinctFields`). | **Aucune clé requise**                                           |
| **Vigueur végétale estivale (NDVI & EVI)**  | **NASA MODIS `MOD13Q1 v061` (250 m)** (tuiles `.npy` `64 × 64`)                                                                               | Mesure l'EVI et le NDVI d'un composite sélectionné entre le 15 juillet et le 10 août sur les `4 096` pixels de la boîte régionale `16 km × 16 km` à chaque année $t$.                                  | **Aucune clé requise** pour MODIS                                |
| **Météo & Humidité racinaire du sol**       | **NASA POWER Daily Agroclimatology API** (`T2M`, `PRECTOTCORR`, `GWETTOP`, `GWETROOT`, `ALLSKY_SFC_SW_DWN`)                                   | Corrige l'effet météo de l'année $t$ (régression Ridge $L_2$) et classe chaque année en `normal`, `sec` ou `chaud`.                                                                                    | **Aucune clé requise**                                           |
| **Projections climatiques futures (CMIP6)** | **NASA NEX-GDDP-CMIP6** via NASA POWER Projection API (`ssp126`, `ssp245`, `ssp370`)                                                          | Projette les degrés-jours ($\text{GDD}_{10}$), températures, jours $\ge 30\,^\circ\text{C}$ et pluies d'été de `2027` à `2050` pour identifier le **Jumeau Climatique** de la ferme.                   | **Aucune clé requise**                                           |
| **Rendements agricoles observés (É.-U.)**   | **USDA NASS QuickStats API**                                                                                                                  | Associe les rendements moyens d'un État américain (`inferUsStateFromLatLon`, désactivé au Canada) aux écarts relatifs de vigueur (`%`) par proportionnalité 1:1 (`linear_proportional_to_state_mean`). | Clé gratuite `USDA_NASS_API_KEY` (optionnelle, É.-U. uniquement) |

## 2. Architecture (JavaScript & portage Python 1:1)

L'algorithme est implémenté à l'identique en **JavaScript** ([`algo-rendement/`](./index.js)) et en **Python** ([`api/field_shift/algorithm/yield_model/`](../api/field_shift/algorithm/yield_model/__init__.py)), avec parité numérique bit-à-bit vérifiée contre [`api/tests/fixtures/yield_js_parity.json`](../api/tests/fixtures/yield_js_parity.json) :

| Rôle | Module JavaScript (`algo-rendement/`) | Module Python (`api/field_shift/algorithm/yield_model/`) |
| :--- | :--- | :--- |
| **Point d'entrée (`runRegionalYieldPipeline` / `run_regional_yield_pipeline`)** | [`index.js`](./index.js) | [`__init__.py`](../api/field_shift/algorithm/yield_model/__init__.py) |
| **Configuration, taxonomie & arrondi IEEE-754 (`js_round`)** | [`config.js`](./config.js) | [`config.py`](../api/field_shift/algorithm/yield_model/config.py) & [`settings.json`](../api/field_shift/algorithm/yield_model/settings.json) |
| **Règles de rotation & délais de retour sanitaires** | [`../src/lib/rotation.js`](../src/lib/rotation.js) | [`rotation.py`](../api/field_shift/algorithm/yield_model/rotation.py) |
| **Validation physique ($\ge -100\,\%$), ratios & confiance** | [`engine/modelUtils.js`](./engine/modelUtils.js) | [`model_utils.py`](../api/field_shift/algorithm/yield_model/model_utils.py) |
| **Segmentation en champs, Ridge $\ln(\text{vigueur})$ & matrice $(A \to B)$** | [`engine/pairTransitions.js`](./engine/pairTransitions.js) | [`pair_transitions.py`](../api/field_shift/algorithm/yield_model/pair_transitions.py) |
| **Jumeaux Climatiques & prévision future $\alpha(y)$** | [`engine/climateTwins.js`](./engine/climateTwins.js) | [`climate_twins.py`](../api/field_shift/algorithm/yield_model/climate_twins.py) |
| **Optimiseur combinatoire de rotations (2 à 6 ans)** | [`engine/yieldOptimizer.js`](./engine/yieldOptimizer.js) | [`yield_optimizer.py`](../api/field_shift/algorithm/yield_model/yield_optimizer.py) |
| **Cache atomique, bornes HTTP (10 Mo) & validation de schéma** | [`sources/cache.js`](./sources/cache.js) | [`sources/cache.py`](../api/field_shift/algorithm/yield_model/sources/cache.py) |
| **Validation calendaire des saisons (153 jours consécutifs)** | [`sources/climateValidation.js`](./sources/climateValidation.js) | [`sources/climate_validation.py`](../api/field_shift/algorithm/yield_model/sources/climate_validation.py) |
| **Séries historiques NASA POWER (`MERRA-2` / `GLDAS`)** | [`sources/nasaPower.js`](./sources/nasaPower.js) | [`sources/nasa_power.py`](../api/field_shift/algorithm/yield_model/sources/nasa_power.py) |
| **Tuiles satellites 64×64 MODIS `MOD13Q1` (`.npy`) & HLS 30 m** | [`sources/nasaModisNdvi.js`](./sources/nasaModisNdvi.js) | [`sources/nasa_modis_ndvi.py`](../api/field_shift/algorithm/yield_model/sources/nasa_modis_ndvi.py) |
| **Cartes de cultures AAFC (GeoTIFF) / USDA CDL (`.npy`) & frontière** | [`sources/cropHistory.js`](./sources/cropHistory.js) | [`sources/crop_history.py`](../api/field_shift/algorithm/yield_model/sources/crop_history.py) |
| **Projections futures NASA POWER (`NEX-GDDP-CMIP6`)** | [`sources/nasaCmip6Projection.js`](./sources/nasaCmip6Projection.js) | [`sources/nasa_cmip6_projection.py`](../api/field_shift/algorithm/yield_model/sources/nasa_cmip6_projection.py) |
| **Calibration conditionnelle USDA NASS (`SURVEY / YEAR`)** | [`sources/nassQuickStats.js`](./sources/nassQuickStats.js) | [`sources/nass_quick_stats.py`](../api/field_shift/algorithm/yield_model/sources/nass_quick_stats.py) |
| **Décodeurs binaires `.npy` et GeoTIFF U8** | [`sources/rasterParser.js`](./sources/rasterParser.js) | [`sources/raster_parser.py`](../api/field_shift/algorithm/yield_model/sources/raster_parser.py) |
| **Suites de tests et de parité** | [`test.js`](./test.js) & [`regression.mjs`](./regression.mjs) | [`api/tests/test_yield_model.py`](../api/tests/test_yield_model.py) |

Les projections utilisent les scénarios POWER `ssp126`, `ssp245` et `ssp370`. Une année climatique manquante, un scénario absent ou des grilles désalignées sont refusés. Une référence monoculture manquante produit un gain de comparaison `null`.

La classe canadienne AAFC `122` (« pâturages/fourrages ») est exclue des estimations propres à la luzerne : elle ne permet pas d'identifier cette espèce. Le code USDA `36` reste reconnu comme luzerne. Les anciens caches contenant une luzerne d'origine ambiguë sont refusés et doivent être téléchargés de nouveau ; les nouveaux portent `cropMappingVersion: 2`.

Les propositions respectent le délai de retour depuis la culture actuelle, y compris au-delà de la première année. La correction météo travaille sur le logarithme de la vigueur pour conserver une valeur ajustée positive. Un effet non fini ou inférieur à −100 % est refusé explicitement, y compris après modulation climatique ; seules les bornes d'incertitude sont tronquées au domaine physique.

HLS est interrogé pour ses métadonnées de scènes disponibles ; les indices de vigueur utilisés par le moteur proviennent de MODIS.
