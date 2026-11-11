# Feuille de route, équipe, risques

## État (fin de l'étape 4)

| Étape | État |
|---|---|
| 1. Architecture minimale, CI, docs | ✅ |
| 2. Intégration NASA (adaptateur, cache, instantanés, indicateurs, graphique) | ✅ |
| 3. Moteur de rotations (catalogue sourcé, 3 stratégies, explications) | ✅ |
| 4. Stress test historique 45 ans + visualisation | ✅ |
| 5. Démonstration et stabilisation | 🔶 reste : E2E navigateur, relecture agronomique, répétition de la démo |

## Prochaines tâches (ordonnées par dépendances, complexité S/M/L)

| # | Tâche | Cplx | Rôle |
|---|---|---|---|
| 1 | Revalider avec l'agriculteur : rotation exacte, composition du foin, priorités, position de la ferme | S | Recherche agro |
| 2 | Sourcer le besoin en eau et la survie hivernale des prairies (fléole, trèfle) → active le critère « eau » | M | Recherche agro |
| 3 | 2–3 tests Playwright (charger la démo, analyser, voir les 3 stratégies) | M | Intégration |
| 4 | Ajout/édition des observations dans le formulaire ; choix des alternatives (`selected_template_ids`) dans l'UI | M | Frontend |
| 5 | Mode fixtures du frontend (`__fixtures__`) pour développer sans API | S | Frontend |
| 6 | Accessibilité : alternative textuelle au tableau du stress test, contraste, navigation clavier sur la carte | S | Frontend |
| 7 | Jumeau climatique : catalogue de régions précalculé + endpoint `/climate-twins` | L | Données + backend |
| 8 | Module économique conditionnel (fourchettes, jamais de montant sans données) | L | Backend + agro |

## Répartition possible (frontières = dossiers, peu de conflits)

| Rôle | Périmètre |
|---|---|
| Frontend / UX | `apps/web/src/features/*` |
| Backend / contrats | `apps/api/src/fieldshift/api`, `application` ; fixtures du frontend |
| Données NASA | `infrastructure/nasa_power`, `scripts/`, `data/snapshots` |
| Simulation / règles | `domain/climate`, `domain/simulation` |
| Recherche agronomique | `data/reference/*.yaml` (aucun code nécessaire) |
| Intégration / présentation | CI, tests E2E, scénario de démo, README |

Branches courtes `feat/…`, PR relue par une autre personne, CI verte obligatoire.

## Risques et simplifications si le temps manque

| Risque | Parade / ce qu'on retire |
|---|---|
| API NASA lente ou bloquée pendant la démo | Mode `snapshot_only` |
| Seuils agronomiques contestés | Seuils dans YAML, marqués provisoires, sources affichées |
| Résultats « plats » (céréales jamais exposées) | C'est un résultat honnête ; l'expliquer pendant la démo |
| Manque de temps | Retirer dans l'ordre : jumeau climatique, économie, édition des observations, tableau « rotations considérées » ; garder carte, climat, 3 stratégies, sources |
