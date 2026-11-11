# ADR 0004 — Fichiers versionnés plutôt qu'une base de données au MVP

**Décision** : référentiel en YAML, instantanés et cache en fichiers. Aucune donnée utilisateur
n'est stockée côté serveur (le profil vit dans le navigateur).
**Migration** : SQLite (puis PostgreSQL) quand il faudra enregistrer des fermes, des comptes ou
le réseau d'agriculteurs (phase 3), avec migrations versionnées à ce moment-là.
