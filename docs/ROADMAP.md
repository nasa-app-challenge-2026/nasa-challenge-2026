# Feuille de route

## Avant et pendant le hackathon

- [x] **Coder l'algorithme** _Field Shift v5.1_ en serveur Python FastAPI (`api/`), vérifié contre `field_shift.py` (`api/tests/`)
- [x] Adapter l'interface à l'algorithme : entrées par parcelle, réserve sans quantités, cycle / fréquence / horizon, plan par cycle, jumeaux climatiques
- [x] **4 priorités** (rendement, utilisation de l'eau, protection du sol, ravageurs) dans l'interface et dans la note du plan, à la place des 9 critères de la référence
- [x] **Eau** : le module `water_use` (bilan d'eau du sol jour par jour, FAO-56) donne la note eau de chaque suite de cultures et la pression sur l'eau de la ferme ; le plan et « Mon champ » affichent ses chiffres (demande, manque, irrigation, pluie gardée)
- [x] **Classement des rotations** (`POST /rotations/rank`) avec les mesures protection du sol (indice RPI, RUSLE, infiltration) et ravageurs
- [x] **Ravageurs** : la branche `feature/ravageurs` est fusionnée ; son modèle (pression des maladies, nématodes et insectes du sol) est la priorité ravageurs du plan, avec l'historique et les maladies déclarées de la parcelle, et l'écran du plan affiche les cultures les plus exposées
- [x] **Rendement** : le modèle régional de rendement (`yield_model`) donne la valeur de chaque précédent dans le plan (vigueur MODIS 2018–2024 et cartes AAC / USDA autour de la ferme) ; une succession non mesurée compte la pénalité du modèle
- [ ] Brancher la protection du sol de l'équipe (indice RPI, RUSLE, infiltration) dans le plan, à la place de la part du temps où le sol est couvert : il faut d'abord décider du facteur P (voir les décisions plus bas)
- [ ] Écrire les mesures `rendement` et `eau` du classement (leurs routes répondent `501`) : voir les décisions plus bas
- [x] Météo réelle de la ferme : NASA POWER, lue par le serveur (une requête par lieu, gardée sur disque)
- [x] **Vraie carte** dans Localisation et Tracer : Leaflet (satellite Esri + plan OSM)
- [x] Recherche d'adresse réelle (Nominatim ; 1 requête par seconde, pas d'usage massif)
- [ ] **Héberger le serveur** de l'algorithme (HTTPS) et renseigner `VITE_ALGO_URL` pour le site GitHub Pages (voir `api/README.md`) ; mettre un compte NASA Earthdata dans ses secrets pour SMAP et ECOSTRESS
- [ ] Relire les fiches des cultures avec un agronome (calendrier, fiches eau de `water_use` marquées « à vérifier », notes de protection du sol) ; revoir la préférence pour la jachère couverte
- [x] **3 rotations proposées** par cycle, côte à côte (roue de cultures, 4 priorités), et le détail de celle qu'on touche
- [x] **Rota** explique tout : plus de texte d'explication dans les écrans, un bouton « Demander à Rota » à la place ; ce qui est hors du MVP le dit quand on le touche (aucun « bientôt »)
- [x] Plan plus rapide sans toucher à l'algorithme : sections calculées en parallèle sur le serveur, dernier plan gardé dans le navigateur
- [ ] Relire les réponses de Rota avec l'équipe algo
- [ ] Parcours de la vidéo (les captures de `docs/screenshots/` sont celles de l'interface du 15 novembre 2026, avec les vraies données)

## Données réelles (voir docs/ALGORITHME.md, « D'où viennent les données »)

- [x] Grille de climats observés 2011–2024 : NASA POWER regional, 10° × 10° autour de la ferme, gardée sur disque
- [x] Modèles climatiques : NASA NEX-GDDP-CMIP6 (ensemble, 3 scénarios) par le service de projections de NASA POWER
- [x] Champs des jumeaux : Inventaire annuel des cultures d'AAC et USDA Cropland Data Layer, filtrés par SoilGrids
- [x] Valeurs de précédent (étape 7) : modèle régional de rendement, NDVI MODIS des champs de la région corrigé de la météo NASA POWER
- [ ] Valeurs de précédent des jumeaux à partir de NASA HLS (le climat futur de la ferme, pas seulement sa région aujourd'hui) ; aujourd'hui elles restent inconnues et le modèle régional les remplace
- [x] Mesures de la parcelle : Copernicus DEM, NASA POWER (fortes pluies), MODIS (sol nu), SoilGrids au point de la section
- [x] Eau : météo complète de NASA POWER (ET0 de Penman-Monteith), sol SSURGO ou SoilGrids, pente SRTM, puits USGS ; SMAP et ECOSTRESS avec un compte Earthdata, sinon MERRA-2
- [x] SMAP et ECOSTRESS vérifiés de bout en bout (15 novembre 2026, Saint-Hyacinthe) : SMAP percentile 71,5, anomalie ESI −0,23 ; le nom du CSV d'ECOSTRESS était mal cherché, corrigé dans `water_use/earthdata.py`
- [ ] Nappes hors États-Unis (au Québec : Réseau de suivi des eaux souterraines du Québec) ; aujourd'hui la composante est « non mesurée »
- [ ] Modèles NEX-GDDP-CMIP6 un par un (le service de NASA POWER ne sert que leur ensemble)
- [ ] GPM IMERG à la place de NASA POWER pour les jours de forte pluie (maille plus fine)

## À corriger

- [x] Pression sur l'eau des cycles lointains : la baisse de la pluie d'été est maintenant celle de la météo récente de la ferme pour tous les cycles ; l'aridité reste celle du climat du cycle
- [x] Note eau calculée sur toutes les années de la météo du cycle : sa première année, rejouée une fois avant, remplit le sol

## Décisions d'équipe en attente

- [ ] Irrigation comptée deux fois : le risque eau d'une parcelle irriguée est multiplié par 0,4, et l'irrigation compte déjà dans la note eau (sous-note B)
- [ ] Eau bue par les couverts : comptée comme perdue dans la note eau (sous-note C)
- [ ] Travail du sol : ce n'est pas une entrée, toutes les suites sont notées en travail conventionnel
- [ ] Foin : noté avec la fiche « prairie » de `water_use`
- [ ] Analyse de sol du fermier : elle remplace SoilGrids pour les jumeaux, pas encore pour la note eau
- [ ] Plans de référence : les tests gardent l'eau de `field_shift.py` v5.1 comme modèle de test (`api/tests/helpers/reference_water.py`), ou on les régénère
- [ ] Successions non mesurées : elles comptent la pénalité du modèle de rendement (premier quartile des effets de la région, −1,5 % au moins) pour que le foin, le canola et le sarrasin, absents des cartes, ne gagnent pas parce qu'ils sont inconnus ; à confirmer avec l'auteure du modèle
- [ ] Facteur P de la protection du sol dans le plan : aucune base ne connaît les pratiques de conservation (courbes de niveau, bandes, terrasses). Le demander au fermier pour chaque section, ou compter P = 1 (aucune pratique) tant qu'il ne l'a pas donné ?
- [ ] Mesures `rendement` et `eau` du classement : ses rotations n'ont pas de dates de semis (une culture seule part du début de l'année). Il faut une règle de calendrier pour l'eau, et une unité pour le rendement (le modèle donne un écart de vigueur en %, pas des kg/ha)

## Après

- [ ] Vraie authentification (aujourd'hui : compte de démo dans le navigateur)
- [ ] Interface en anglais (la soumission est en anglais)
- [ ] Les autres types de ferme : maraîchage, cultures et élevage, pâturage tournant, vergers et vignes
- [ ] Corriger les dates de gel avec celles que le fermier connaît (la grille NASA POWER lisse les gels locaux)
- [ ] Vraie 3D (Three.js) à la place de la vue isométrique
