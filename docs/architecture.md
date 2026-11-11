# Architecture

## 1. Synthèse des exigences

| Catégorie | Contenu |
|---|---|
| **Exigences du défi** | Combiner observations de la Terre NASA, sols, cultures et priorités de l'agriculteur ; comparer au moins 3 rotations dont l'actuelle ; expliquer pourquoi, données utilisées, bénéfices, risques, incertitudes ; ne pas se présenter comme un agronome automatisé. *Le texte officiel du défi (page rendue côté client) n'a pas pu être relu automatiquement : à revérifier par l'équipe, notamment la liste des ressources NASA suggérées.* |
| **Décisions de l'équipe** | Ferme de Sacré-Cœur comme profil principal ; MVP = profil, climat, comparaison, stress test historique, résultats ; jumeau climatique et économie en phase 2. |
| **Hypothèses** | Rotation actuelle interprétée comme avoine 1 an puis foin 2 ans ; position = centre de la municipalité ; priorités neutres faute de mesure ; un champ par phase de rotation. |
| **Choix techniques** | Monolithe modulaire ; FastAPI + Pydantic ; React + TypeScript ; NASA POWER Daily API ; fichiers versionnés plutôt qu'une base de données ; moteur déterministe à règles sourcées. |

## 2. Vue d'ensemble

```mermaid
flowchart LR
  subgraph Web["apps/web (React)"]
    UI[Features: profil, carte, climat, comparaison, stress test, sources]
    Client[api/client.ts + schémas Zod]
  end
  subgraph API["apps/api (FastAPI)"]
    Routes[api/routes + schemas Pydantic]
    App[application: ClimateAnalysisService, RotationComparisonService, ports]
    Domain[domain: climate, agronomy, simulation, provenance]
    Infra[infrastructure: nasa_power, reference_data, settings, logging]
  end
  NASA[(NASA POWER Daily API)]
  Files[(data/reference/*.yaml\ndata/snapshots/)]
  Cache[(.cache/ local)]
  UI --> Client -->|HTTP JSON| Routes --> App --> Domain
  Infra -. implémente les ports .-> App
  Infra --> NASA
  Infra --> Files
  Infra --> Cache
```

Règle de dépendance : `api → application → domain` ; `infrastructure` implémente les contrats
(`application/ports.py`) et n'est assemblée que dans `api/dependencies.py`. Le domaine n'importe
ni FastAPI, ni Pydantic, ni httpx, ni YAML : c'est **testé** (`tests/unit/test_architecture.py`).

## 3. Pipelines

### Acquisition NASA (étapes 1 à 12)

```mermaid
flowchart TD
  A[Position + période] --> B{Valide ? hémisphère nord, années complètes 1981..N-1}
  B -- non --> E422[422 problem+json]
  B -- oui --> C[Cellule MERRA-2 0,5° x 0,625°]
  C --> D{Cache local ?}
  D -- oui --> P
  D -- non --> F[GET POWER au centre de la cellule\ntimeout, 2 essais, 2 requêtes simultanées max]
  F -- ok --> G[Validation Pydantic + unités + valeur -999 -> manquant] --> H[Écriture cache + SHA-256] --> P
  F -- échec / 429 --> S{Instantané vérifié ?}
  S -- oui --> P2[Données + avertissement snapshot_fallback] --> P
  S -- non --> E503[503 problem+json]
  P[Série normalisée + provenance] --> Q[Années incomplètes écartées, rapport qualité] --> R[Indicateurs par année] --> T[Réponse documentée]
```

La ferme n'est jamais envoyée à la NASA : seul le centre de la cellule (~50 km) l'est.

### Comparaison de rotations et stress test historique

```mermaid
flowchart TD
  Y[Années complètes -> YearContext\nsaisons, gels, UTM, DJC, ETo] --> CR[Chaque culture x chaque année :\nchaleur pour mûrir ? gel au seuil de dommage ?]
  CR --> ST[Chaque rotation x chaque année :\npart des champs touchés]
  ST --> BL{Contraintes bloquantes :\nculture exclue, chaleur manquante > 1 an sur 2}
  BL -- écartée --> L[Liste « rotations considérées » avec raison]
  BL -- admissible --> SC[Scores 0..1 : climat, sol, eau, revenu\ncritère utilisé seulement s'il est complet pour toutes]
  SC --> SEL[Alt. 1 : poids égaux climat + sol\nAlt. 2 : priorités de l'agriculteur]
  SEL --> EX[Explications générées depuis les chiffres + sources]
```

### Jumeau climatique (phase 2, non implémenté)

```mermaid
flowchart TD
  F[Ferme] --> H[Climatologie de référence 1991-2020\nindicateurs annuels médians]
  F --> P[POWER Projection API, NEX-GDDP-CMIP6 0,25°\nscénario explicite ssp245, 2041-2060]
  P --> V[Même vecteur d'indicateurs : UTM, DJC0, saison sans gel, précipitations avr-oct, jours de gel]
  H --> V
  V --> Z[Normalisation par l'écart-type interannuel de référence]
  Z --> K[Distance euclidienne pondérée vers un catalogue PRÉCALCULÉ de régions de référence]
  K --> R[Analogues classés + distance + scénario + période + limites]
```

Distance proposée : `d(f, r) = sqrt(Σ_i w_i ((x_i^f,2050 − x_i^r,actuel) / σ_i^r)²)`, avec `σ_i`
l'écart-type interannuel observé de l'indicateur `i` (unités comparables, « en années typiques
d'écart »), poids égaux par défaut. Le catalogue de régions est préparé hors ligne par un script
(jamais de téléchargement massif pendant une requête). Aucune affirmation de réussite des cultures
dans la région analogue sans données agricoles supplémentaires.

## 4. Arborescence

```
apps/api/src/fieldshift/
  domain/                      noyau métier pur, sans I/O
    geo.py                     GeoPoint, GridCell
    provenance.py              DatasetProvenance, DataQualityReport, origines et natures des données
    references.py              Reference (bibliographie)
    observation_checks.py      année signalée par l'agriculteur vs données
    climate/                   série quotidienne, formules (UTM, DJC, Ra, Hargreaves), saisons,
                               précipitations, statistiques (centiles, Mann-Kendall, Theil-Sen),
                               YearContext, registre d'indicateurs
    agronomy/                  Crop + exigences sourcées, FarmProfile, CropRotation, priorités,
                               validation, suitability (contrôles culture x année)
    simulation/                stress_test, assessment (contraintes, critères), explanations,
                               comparison (sélection des stratégies)
  application/                 cas d'usage + ports (Protocol) + erreurs applicatives
  infrastructure/              nasa_power (grid, client, parser, store, provider), reference_data,
                               settings, logging
  api/                         app (factory), dependencies (composition), errors, routes, schemas
apps/api/tests/                unit/ (formules, saisons, comparaison, architecture), integration/
                               (parseur sur réponse enregistrée, client simulé, cache/snapshot, API)
apps/web/src/
  api/                         client typé + schémas Zod + test de contrat sur réponses réelles
  features/                    farm-profile, climate-dashboard, rotation-comparison,
                               historical-simulation, data-sources
  components/ utils/           composants et formatage partagés
data/reference/                crops.yaml, rotation_templates.yaml, sources.yaml, demo_farms.yaml
data/snapshots/nasa-power/     réponses NASA brutes + .meta.json (URL, date, SHA-256)
```

## 5. Modèle de domaine

| Entité | Rôle et invariants |
|---|---|
| `FarmProfile` | Position + précision (exacte/approximative), rotation actuelle, priorités 0–3, sol/irrigation **optionnels** (`None` = inconnu), cultures exclues, observations verbatim. |
| `Crop` | Catégorie (annuelle, fourragère pérenne, pérenne ligneuse), familles, fixation d'azote (`None` = inconnu), modèle de saison ; exigences de chaleur, gel, eau **avec `Basis`** (sources, `documented`/`provisional`). Une valeur documentée sans source est refusée. |
| `CropRotation` | 1 à 8 années ; une pérenne ligneuse y est refusée. |
| `ClimateSeries` / `YearData` | Jours strictement croissants ; seules les années sans aucune valeur manquante sont analysées. |
| `YearContext` | Tout ce qui dérive d'une année (saisons, gels, cumuls), calculé une fois et partagé. |
| `IndicatorDefinition` | Identifiant, unité, définition en français, sources, fonction pure. |
| `CropYearOutcome`, `RotationStressTest` | Résultat de chaque règle par année ; distribution de l'exposition par rotation. |
| `EvaluatedRotation`, `CriterionScore` | Admissibilité, scores 0..1 et couverture des données. |
| `RecommendationExplanation` / `Statement` | Phrases typées (bénéfice, compromis, incertitude, à valider) liées à un critère et à des sources. |
| `DatasetProvenance`, `DataQualityReport` | Source, produit, version, période, date d'obtention, résolution, cellule, unités, origine (live/cache/instantané), nature (réanalyse ≠ projection), SHA-256, avertissements. |

Les schémas HTTP (`api/schemas`) sont distincts des entités et convertis explicitement.

## 6. Stratégie de données

- **Référentiel** : YAML versionnés, validés strictement au démarrage (clés inconnues, sources
  citées inexistantes, cultures inconnues → l'API refuse de démarrer).
- **Cache** : `.cache/nasa-power/`, clé = cellule + période + paramètres ; une réponse invalide
  n'est jamais mise en cache ; verrou par clé pour éviter les téléchargements concurrents.
- **Instantanés** : `data/snapshots/`, produits par le pipeline de production
  (`scripts/refresh_snapshot.py`), vérifiés par SHA-256 à chaque lecture.
- **Reproductibilité** : même instantané → mêmes chiffres (test d'API sur UTM 2024 = 2886 à
  Sacré-Cœur) ; lockfiles `uv.lock` et `package-lock.json` ; dépendances antérieures au 27/10/2026.
- **Persistance** : pas de base de données au MVP (voir ADR 0004).

## 7. Tests et CI

Pyramide : unitaires sur le noyau (valeurs publiées : matrice UTM d'OMAFRA, exemple 8 de la
FAO-56 ; années synthétiques aux résultats connus ; règles de sélection) → intégration (réponse
NASA enregistrée, client HTTP simulé, cache, repli sur instantané, falsification détectée, API de
bout en bout sur l'instantané réel) → frontend (contrat Zod sur réponses réelles, formatage).
E2E navigateur : à ajouter (Playwright, 2–3 parcours) — voir la feuille de route.
