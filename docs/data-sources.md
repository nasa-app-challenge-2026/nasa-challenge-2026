# Sources de données

## Utilisées dans le MVP

### NASA POWER — Daily API (historique)

| | |
|---|---|
| Point d'accès | `https://power.larc.nasa.gov/api/temporal/daily/point` ([doc](https://power.larc.nasa.gov/docs/services/api/temporal/daily/)) |
| Paramètres | `T2M`, `T2M_MAX`, `T2M_MIN` (°C, air à 2 m ; min/max = extrêmes horaires du jour), `PRECTOTCORR` (mm/jour, précipitations MERRA-2 corrigées) — définitions officielles lues le 2026-11-10 |
| Communauté / temps | `AG` / `LST` (heure solaire locale, défaut de l'API) |
| Source amont | MERRA-2 (en-tête `sources: MERRA2, POWER`), API v2.10.3 |
| Résolution | 0,5° × 0,625°, valeurs de la cellule sans interpolation ; **vérifié empiriquement** (6 points autour de Sacré-Cœur) |
| Couverture | 1981-01-01 à quasi temps réel ; seules les années complètes sont analysées |
| Valeur manquante | `-999` (`header.fill_value`) → `None` |
| Limites d'usage | 20 paramètres par requête ; requêtes répétées au même endroit susceptibles d'être bloquées → cache par cellule |
| Licence | Données de missions NASA : **CC0** ([NASA Earthdata](https://www.earthdata.nasa.gov/engage/open-data-services-software-policies/data-use-guidance)) ; redistribution des instantanés autorisée, citation demandée |
| Citation | Texte demandé par POWER ([referencing](https://power.larc.nasa.gov/docs/referencing/)), généré avec version et date dans chaque réponse |

Représentativité : altitude moyenne de la cellule de Sacré-Cœur 245 m ; cellules voisines 149 m
(est) et 453 m (nord). Fonds de vallée, proximité du fjord et du fleuve, pentes : non représentés.

### Référentiel agronomique

Voir `data/reference/sources.yaml` (citation, URL, date de consultation, conditions). Les
documents protégés (FAO, OMAFRA, CRAAQ, MSU…) sont **cités**, jamais redistribués ; seules
quelques valeurs numériques en sont reprises avec leur référence.

### Feux près de la ferme (front)

Appelés directement par le navigateur (CORS ouvert, sans clé), vérifiés le 2026-11-14.

| Service | Point d'accès | Ce qu'on en tire | Limites |
|---|---|---|---|
| SCIFV / CWFIS (RNCan), WFS | `https://cwfis.cfs.nrcan.gc.ca/geoserver/public/wfs` | `public:hotspots` (points chauds MODIS/VIIRS de la NASA, avec le type de combustible), `public:nbac` (zones brûlées depuis 1972), `public:m3_polygons_current` (feux de la saison), `public:fdr_current_shp` (danger du jour : `GRIDCODE` 0 bas à 4 extrême) | Filtre `CQL_FILTER` en EPSG:4326 (`SRID=4326;POINT(lon lat)` pour un point) ; 2 000 points chauds au plus par requête |
| NASA HLS v2 sur Microsoft Planetary Computer | STAC `…/api/stac/v1/search`, statistiques `…/api/data/v1/item/statistics` | NBR médian par section : `(B8A-B12)/(B8A+B12)` (S30), `(B05-B07)/(B05+B07)` (L30) ; masque `Fmask` (bits 1 à 4 : nuage, voisin, ombre, neige) | Depuis 2020 ; une récolte fait aussi baisser le NBR, d'où des images au plus près du feu |
| Inventaire annuel des cultures (AAC), ArcGIS ImageServer | `https://www.agr.gc.ca/imagery-images/rest/services/annual_crop_inventory/<année>/ImageServer/getSamples` | Classe de culture par année, 5 points par section ; code 60 = zone brûlée | 2009 à 2025 (Québec : depuis 2011) ; table des codes : `aci_crop_classifications_iac_classifications_des_cultures.csv` |
| ISRIC SoilGrids v2 | `https://rest.isric.org/soilgrids/v2.0/properties/query` | Argile, sable, limon, carbone organique, pH (0–15 cm) | Lent et instable, quelques appels par minute : un appel par km², gardé pour la session ; aucune donnée en milieu bâti |

## Évaluées, non retenues pour le MVP

| Source | Constat | Décision |
|---|---|---|
| IMERG via POWER (`IMERG_PRECTOT`, 0,1°, depuis 1998) | Comparé à MERRA-2 pour juin–juillet 1999–2025 : ordres de grandeur proches ; 2024 n'est pas non plus exceptionnel (16e/27 pour les jours de pluie) | Candidat à la phase 2 pour la météo de fenaison (meilleure résolution, mais série plus courte) |
| POWER Projection API (NEX-GDDP-CMIP6, 0,25°, 2015–2100, `ssp126/245/370`, modèle `ensemble` par défaut ; modèles quotidiens disponibles : cesm2, ec_earth3, gfdl_esm4, giss_e2_1_g, ipsl_cm6a_lr, mpi_esm1_2_lr) | Testée : réponse `parameter → scénario → date`, `fill_value -999`, limite de 250 000 valeurs par requête JSON | Suffisante pour le jumeau climatique : pas de pipeline NetCDF nécessaire. Les projections seront marquées `model_projection`, jamais comme observations |
| SMAP L4 (humidité du sol, ~9 km, depuis 2015) | Série courte pour un stress test de 45 ans | Phase 2 : contexte de sécheresse récente |
| Sols | SoilGrids non supposé disponible ; pour le Québec, études pédologiques de l'IRDA et Pédo-paysages du Canada (AAC) **à évaluer** (non vérifiés) | MVP : texture déclarée, marquée comme déclaration |
