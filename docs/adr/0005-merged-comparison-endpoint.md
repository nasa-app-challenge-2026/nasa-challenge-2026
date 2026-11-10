# ADR 0005 — Comparaison et simulation historique dans un même endpoint

**Décision** : `POST /rotations/compare` renvoie la comparaison **et** le stress test ;
`POST /climate/analyze` reste séparé pour l'exploration climatique.
**Pourquoi** : mêmes entrées, même jeu de données, cohérence garantie de la période ; un seul
appel pour l'interface. Les endpoints sont synchrones (calcul en pool de threads) : plus simple
pour l'équipe, suffisant pour ~45 ans × 10 cultures.
