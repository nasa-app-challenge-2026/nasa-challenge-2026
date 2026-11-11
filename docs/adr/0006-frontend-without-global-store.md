# ADR 0006 — Frontend sans store global ni routeur

**Décision** : une page, état local dans `App.tsx`, client `fetch` typé et validé par Zod,
Recharts pour les courbes, grille CSS pour le stress test, Leaflet pour la carte.
**Pourquoi** : un seul parcours ; validation des contrats à la frontière ; moins de dépendances.
**À revoir** si plusieurs vues apparaissent (jumeau climatique) : React Router.
