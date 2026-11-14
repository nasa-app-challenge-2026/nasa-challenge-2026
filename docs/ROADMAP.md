# Feuille de route

## Avant et pendant le hackathon

- [x] **Coder l'algorithme** _Field Shift v5.1_ dans l'appli (`backend/algorithm/`), vérifié contre `field_shift.py` (`tests/algorithm/`)
- [x] Adapter l'interface à l'algorithme : entrées par parcelle, réserve sans quantités, cycle / fréquence / horizon, 9 critères, plan par cycle, jumeaux climatiques
- [x] Météo réelle de la ferme : NASA POWER, lue dans le navigateur
- [x] **Vraie carte** dans Localisation et Tracer : Leaflet (satellite Esri + plan OSM)
- [x] Recherche d'adresse réelle (Nominatim ; 1 requête par seconde, pas d'usage massif)
- [ ] Relire les fiches des cultures avec un agronome (valeurs des critères, calendrier) ; revoir la préférence pour la jachère couverte
- [ ] Relire les réponses de RotaAI avec l'équipe algo
- [ ] Captures et parcours de la vidéo

## Données réelles à brancher (voir docs/ALGORITHME.md, « Brancher une vraie source »)

- [ ] Grille de climats observés 2011–2024 (NASA POWER, cases cultivées de l'est de l'Amérique du Nord), pré-calculée
- [ ] Modèles NEX-GDDP-CMIP6 (3 à 5), deltas mensuels pré-calculés par fenêtre de 20 ans
- [ ] Champs des jumeaux : USDA Crop Sequence Boundaries et Inventaire annuel des cultures d'AAC, filtrés par SoilGrids
- [ ] Valeurs de précédent à partir de NASA HLS (étape 7)
- [ ] Mesures de la parcelle : SRTM / NASADEM, GPM IMERG, MODIS, ECOSTRESS, SMAP L4, GRACE-FO ; SoilGrids au point de la section

## Après

- [ ] Vraie authentification (aujourd'hui : compte de démo dans le navigateur)
- [ ] Interface en anglais (la soumission est en anglais)
- [ ] Les autres types de ferme : maraîchage, cultures et élevage, pâturage tournant, vergers et vignes
- [ ] Corriger les dates de gel avec celles que le fermier connaît (la grille NASA POWER lisse les gels locaux)
- [ ] Vraie 3D (Three.js) à la place de la vue isométrique
