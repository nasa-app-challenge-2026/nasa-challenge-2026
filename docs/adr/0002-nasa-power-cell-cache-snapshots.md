# ADR 0002 — NASA POWER par cellule, cache local et instantanés vérifiés

**Décision** : interroger la Daily API au **centre de la cellule MERRA-2** ; mettre en cache par
cellule + période ; versionner des instantanés (réponse brute + SHA-256) pour la démo et le
repli en cas d'échec, signalé à l'utilisateur.
**Pourquoi** : même donnée pour toute la cellule (vérifié), clé de cache stable, position de la
ferme jamais transmise, démo possible hors ligne, reproductibilité. Données CC0 → redistribuables.
**Écartés** : téléchargement de fichiers globaux (inutile au MVP) ; Redis (aucun besoin).
