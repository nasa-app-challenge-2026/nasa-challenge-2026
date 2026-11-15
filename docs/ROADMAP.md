# Feuille de route

## Avant et pendant le hackathon

- [x] **Coder l'algorithme** _Field Shift v5.1_ en serveur Python FastAPI (`api/`), vérifié contre `field_shift.py` (`api/tests/`)
- [x] Adapter l'interface à l'algorithme : entrées par parcelle, réserve sans quantités, cycle / fréquence / horizon, 9 critères, plan par cycle, jumeaux climatiques
- [x] **4 priorités** (rendement, utilisation de l'eau, protection du sol, ravageurs) dans l'interface et dans la note du plan, à la place des 9 critères de la référence
- [ ] Brancher dans le plan les algorithmes de l'équipe pour le rendement (`yield_model`), la protection du sol (indice RPI, RUSLE, infiltration) et les ravageurs (branche `feature/ravageurs`) ; l'eau (`water_use`) l'est déjà
- [x] Météo réelle de la ferme : NASA POWER, lue par le serveur (une requête par lieu, gardée sur disque)
- [x] **Vraie carte** dans Localisation et Tracer : Leaflet (satellite Esri + plan OSM)
- [x] Recherche d'adresse réelle (Nominatim ; 1 requête par seconde, pas d'usage massif)
- [ ] **Héberger le serveur** de l'algorithme (HTTPS) et renseigner `VITE_ALGO_URL` pour le site GitHub Pages (voir `api/README.md`)
- [ ] Relire les fiches des cultures avec un agronome (valeurs des critères, calendrier) ; revoir la préférence pour la jachère couverte
- [ ] Relire les réponses de RotaAI avec l'équipe algo
- [ ] Captures et parcours de la vidéo

## Données réelles (voir docs/ALGORITHME.md, « D'où viennent les données »)

- [x] Grille de climats observés 2011–2024 : NASA POWER regional, 10° × 10° autour de la ferme, gardée sur disque
- [x] Modèles climatiques : NASA NEX-GDDP-CMIP6 (ensemble, 3 scénarios) par le service de projections de NASA POWER
- [x] Champs des jumeaux : Inventaire annuel des cultures d'AAC et USDA Cropland Data Layer, filtrés par SoilGrids
- [ ] Valeurs de précédent à partir de NASA HLS (étape 7) : aujourd'hui inconnues (priorité rendement neutre, lacunes listées)
- [x] Mesures de la parcelle : Copernicus DEM, NASA POWER (fortes pluies), MODIS (sol nu), SoilGrids au point de la section
- [ ] Modèles NEX-GDDP-CMIP6 un par un (le service de NASA POWER ne sert que leur ensemble)
- [ ] GPM IMERG à la place de NASA POWER pour les jours de forte pluie (maille plus fine)

## Après

- [ ] Vraie authentification (aujourd'hui : compte de démo dans le navigateur)
- [ ] Interface en anglais (la soumission est en anglais)
- [ ] Les autres types de ferme : maraîchage, cultures et élevage, pâturage tournant, vergers et vignes
- [ ] Corriger les dates de gel avec celles que le fermier connaît (la grille NASA POWER lisse les gels locaux)
- [ ] Vraie 3D (Three.js) à la place de la vue isométrique
