# ADR 0003 — Moteur déterministe à règles sourcées, pas d'apprentissage automatique

**Décision** : seuils et formules publiés, dans des fichiers YAML avec source et niveau de
confiance ; scores transparents ; explications générées depuis les chiffres.
**Pourquoi** : aucune donnée de rendement locale pour entraîner un modèle ; exigence
d'explicabilité ; un agriculteur et un agronome doivent pouvoir vérifier chaque chiffre.
**Conséquence** : le moteur dit « contrainte documentée atteinte ou non », jamais « rendement ».
