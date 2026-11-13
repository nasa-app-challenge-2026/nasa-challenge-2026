# Feuille de route

## Avant et pendant le hackathon

- [ ] **Brancher l'algo** de Nour et Yanis (`VITE_ALGO_MODE=remote`, voir ALGO_CONTRACT.md)
- [x] **Vraie carte** dans Localisation et Tracer : Leaflet (satellite Esri + plan OSM). Le contour de la ferme (`farm.boundary`) et les sections (`section.polygon`) se dessinent à la main et sont repris dans la vue 3D du tableau et la carte de section.
- [x] Recherche d'adresse réelle (Nominatim, `src/lib/geocode.js` ; conditions d'usage : 1 requête par seconde, pas d'usage massif)
- [x] Superficie calculée à partir du polygone dessiné (`src/lib/geo.js`)
- [ ] Relire les réponses de RotaAI avec l'équipe algo
- [ ] Confirmer les délais de retour et les rôles des cultures (`src/data/crops.js`)
- [ ] Décider la durée d'un choc du stress test (1 an ou 3 ans)
- [ ] Captures et parcours de la vidéo

## Après

- [ ] Vraie authentification (aujourd'hui : compte de démo dans le navigateur)
- [ ] Interface en anglais (la soumission est en anglais)
- [ ] Les autres types de ferme : maraîchage, cultures et élevage, pâturage tournant, vergers et vignes
- [ ] Coût des semences dans le revenu, option « je garde ma semence »
- [ ] Vraie 3D (Three.js) à la place de la vue isométrique
