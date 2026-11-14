# Contrat entre le front end et l'algorithme · v2.0

Ce document dit **exactement** ce que l'interface envoie à l'algorithme et ce qu'elle reçoit. La version 2.0 suit l'algorithme _Field Shift — pipeline v5.1_ ; la version 1.0 (scores eau / sol / résilience / revenu, stress test, rotation éditée à la main) n'existe plus.

- **Source de vérité :** [`backend/contract/field-shift.schema.json`](../backend/contract/field-shift.schema.json) (JSON Schema, draft-07)
- **Exemples :** [`backend/contract/examples/`](../backend/contract/examples/) : une entrée par cas de référence (écrite à la main) et le plan que le serveur renvoie (avec la météo fictive, pour que les fichiers ne dépendent pas du réseau). `python -m field_shift.tools.make_examples`, dans `backend/server`, les régénère.
- **Qui l'implémente :** le serveur FastAPI [`backend/server`](../backend/server/) ([`ALGORITHME.md`](ALGORITHME.md)). Ses modèles Pydantic suivent ce schéma, et ses tests le vérifient.
- **Qui l'appelle :** [`backend/remoteEngine.js`](../backend/remoteEngine.js), le client HTTP du front.

## Les routes

| Route         | Entrée      | Sortie                             | Rôle                                                                                 |
| ------------- | ----------- | ---------------------------------- | ------------------------------------------------------------------------------------ |
| `POST /plan`  | `FarmInput` | `FarmPlan`                         | planifie toutes les sections de la ferme (côté front : `engine.planFarm(farmInput)`) |
| `GET /health` |             | `{ "status": "ok", "version", … }` | le serveur répond                                                                    |

Une entrée invalide est refusée avec un `422` : `{ "detail": [{ "loc": ["body", "farm", "time"], "msg": "…" }] }`. Le client du front en fait une phrase (« farm › time : Le cycle doit durer de 2 à 6 ans. »). Le serveur autorise le CORS pour les adresses de `FIELD_SHIFT_CORS_ORIGINS`.

Le tableau de bord, « Ma parcelle », « Mon champ », « Plan par cycle » et « Climat et jumeaux » lisent tous le même `FarmPlan`. Le plan est recalculé à chaque changement des entrées (250 ms après le dernier).

## Entrée : `FarmInput`

```json
{
  "version": "2.0",
  "today": "2026-11-13",
  "farm": {
    "type": "grandes-cultures",
    "location": { "lat": 45.6287, "lon": -72.94815, "label": "Saint-Hyacinthe, QC" },
    "boundary": [
      [45.6314, -72.952],
      [45.6314, -72.9443],
      [45.626, -72.9443],
      [45.626, -72.952]
    ],
    "time": { "cycleYears": 4, "frequencyMonths": 12, "horizonYears": 12 },
    "priorities": ["erosion", "rendement", "azote", "reserve", "matiere_org", "marche"],
    "livestock": false,
    "missingEquipment": [],
    "seeds": { "crops": ["mais", "soya", "ble-automne", "seigle"], "mode": "preferer" }
  },
  "sections": [
    {
      "id": "A",
      "areaHa": 12,
      "polygon": [
        [45.6314, -72.952],
        [45.6314, -72.94686],
        [45.6287, -72.94686],
        [45.6287, -72.952]
      ],
      "currentCrop": "mais",
      "currentHarvest": "2026-10",
      "history": [
        { "year": 2024, "crop": "mais" },
        { "year": 2025, "crop": "soya" }
      ],
      "currentRotation": ["mais", "soya"],
      "rotationPosition": 0,
      "diseases": [],
      "irrigated": false,
      "soilTest": null
    }
  ]
}
```

| Champ                     | Étape du PDF | Règle                                                                                                                                                                                                                |
| ------------------------- | ------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `today`                   | 1            | facultatif ; date d'utilisation (limite des 10 ans du cas 1). Par défaut : la date du jour.                                                                                                                          |
| `farm.location`           | 3, 4         | point de la météo NASA POWER et centre de la recherche des jumeaux.                                                                                                                                                  |
| `farm.time`               | 1 bloc C     | `cycleYears` 2 à 6 ; `frequencyMonths` 12, 6 ou 4 (doit diviser 12 × C) ; `horizonYears` multiple de C, jusqu'en 2060. Règles dans `application/rules/timeSettings.js`.                                              |
| `farm.priorities`         | 1 bloc D     | critères classés, du plus important au moins important, parmi `rendement`, `eau`, `fourrage`, `azote`, `erosion`, `matiere_org`, `marche`, `ravageurs`, `reserve`. Un critère absent garde 25 % du plus petit poids. |
| `farm.livestock`          | 1 bloc D     | sans bétail, le poids du fourrage est multiplié par 0,3.                                                                                                                                                             |
| `farm.missingEquipment`   | 1 bloc D     | `fourragere` absente → plus de luzerne ni de foin.                                                                                                                                                                   |
| `farm.seeds`              | 1 bloc B     | semences possédées, **sans quantités** (ids de `SEED_IDS`) ; `mode` `preferer` (la réserve compte dans la note) ou `uniquement` (seules ces semences, plus la jachère).                                              |
| `section.currentCrop`     | 1 bloc A     | une fiche (`mais`, `luzerne-3`…) ou une autre culture (`pomme-de-terre`…), `null` = parcelle libre.                                                                                                                  |
| `section.currentHarvest`  | 1 bloc A     | `"AAAA-MM"`, mois de récolte (ou de fin pour une pérenne) ; lu comme le milieu du mois. Obligatoire si une culture est en place.                                                                                     |
| `section.history`         | 1 bloc A     | cultures des années **avant** la culture en place, une par année. Le plan dit combien d'années demander (`historyYears`).                                                                                            |
| `section.currentRotation` | 1 bloc A, 10 | la rotation que suit le fermier (fiches) ; `rotationPosition` = indice de la culture en place. Elle sert de **référence** ; vide = la culture en place répétée.                                                      |
| `section.diseases`        | partie B     | maladies du sol connues (ids de `SOIL_DISEASES`) : leur délai le plus long devient obligatoire.                                                                                                                      |
| `section.irrigated`       | 8            | parcelle irriguée : le risque eau est multiplié par 0,4.                                                                                                                                                             |
| `section.soilTest`        | 5            | `{ clayPct, sandPct, organicCarbon (g/kg), ph }` ou `null` (SoilGrids).                                                                                                                                              |

## Sortie : `FarmPlan`

Un plan par section, **dans le même ordre et avec le même `id`** que l'entrée.

```json
{
  "version": "2.0",
  "meta": {
    "engine": "field-shift-js",
    "algorithm": "field_shift v5.1",
    "demo": true,
    "generatedAt": "2026-11-13T00:00:00.000Z",
    "sources": {
      "farmWeather": {
        "real": true,
        "label": "NASA POWER, météo quotidienne 1985–2024 au point de la ferme"
      },
      "climateModels": {
        "real": false,
        "label": "3 modèles climatiques fictifs (à la place de NEX-GDDP-CMIP6)"
      }
    }
  },
  "settings": {
    "cycleYears": 4,
    "frequencyMonths": 12,
    "positionsPerCycle": 4,
    "horizonYears": 12,
    "currentYear": 2026,
    "priorities": ["erosion", "rendement", "azote", "reserve", "matiere_org", "marche"]
  },
  "weights": { "erosion": 0.408, "rendement": 0.242, "...": 0 },
  "sections": [
    {
      "id": "A",
      "freeAt": "2026-10-16",
      "firstYear": 2027,
      "lastYear": 2038,
      "repeatsCurrentCrop": false,
      "historyYears": 4,
      "history": [
        { "crop": "soya", "from": 2023, "to": 2023 },
        { "crop": "mais", "from": 2026, "to": 2026 }
      ],
      "field": {
        "measures": {
          "slopePct": 4.9,
          "heavyRainDays": 6,
          "bareSoilDays": 140,
          "summerStressIndex": 0.62,
          "rootZoneDrought": 0.32,
          "groundwaterTrendCmPerYear": -0.7
        },
        "soil": {
          "clayPct": 28,
          "sandPct": 33,
          "organicCarbon": 25.1,
          "ph": 6.4,
          "source": "SoilGrids 2.0 (fictif)"
        },
        "risksToday": { "erosion": 0.72, "water": 0.31 }
      },
      "cycles": [
        {
          "index": 1,
          "years": [2027, 2030],
          "decision": "changer",
          "climate": {
            "method": "tendance",
            "source": "tendance NASA POWER",
            "models": [],
            "lastSpringFrost": { "month": 4, "day": 26 },
            "firstFallFrost": { "month": 10, "day": 10 },
            "januaryMinimumC": -14.6,
            "warmingC": 0.46,
            "summerRainChangePct": 0,
            "harvestAdvanceDays": 1
          },
          "twins": {
            "sigmaMean": 0.01,
            "reliable": true,
            "cells": [{ "lat": 45.1, "lon": -74.4, "sigma": 0.003, "sources": ["NASA POWER"] }],
            "crops": ["mais", "soya", "canola"]
          },
          "risks": { "erosion": 0.72, "water": 0.31 },
          "weights": { "erosion": 0.7, "...": 0 },
          "chosen": {
            "score": 60.86,
            "criteria": {
              "rendement": 0.66,
              "erosion": 0.58,
              "eau": 0.6,
              "fourrage": 0.2,
              "azote": 0.44,
              "matiere_org": 0.46,
              "marche": 0.75,
              "ravageurs": 1,
              "reserve": 1
            },
            "label": "(seigle) → Jachère → Soya (+ seigle) → Jachère → Blé d’automne",
            "sheets": ["jachere", "soya", "jachere", "ble-automne"],
            "steps": [
              {
                "sheet": "jachere",
                "crop": "jachere",
                "kind": "jachere",
                "sowing": null,
                "harvest": null,
                "positions": [1, 1]
              },
              {
                "sheet": "seigle-couvert",
                "crop": "seigle",
                "kind": "couvert",
                "sowing": "2026-10-24",
                "harvest": "2027-05-08",
                "positions": null
              },
              {
                "sheet": "soya",
                "crop": "soya",
                "kind": "culture",
                "sowing": "2028-05-16",
                "harvest": "2028-08-29",
                "positions": [2, 2]
              }
            ],
            "gaps": [],
            "seedsToBuy": [],
            "warnings": []
          },
          "reference": {
            "score": 45.79,
            "label": "Soya → Maïs → Soya → Maïs",
            "...": "même forme que chosen"
          },
          "referenceAlerts": [
            {
              "reason": { "kind": "meme-culture", "previous": "soya", "next": "soya" },
              "yearsWithout": 1,
              "minimum": 2,
              "from": { "year": 2025, "source": "historique" },
              "to": { "year": 2027, "source": "chaîne" },
              "message": "Soya après Soya : 2025 puis 2027, 1 an(s) sans, minimum 2"
            }
          ],
          "alternatives": [
            {
              "score": 60.8,
              "label": "Jachère → Luzerne ×2 [2 pos.] → Maïs",
              "...": "même forme que chosen"
            }
          ],
          "removed": [
            {
              "sheet": "luzerne-3",
              "required": 2,
              "possible": 1,
              "occupiedYears": 3,
              "message": "Luzerne ×3 demande 2 an(s) sans luzerne entre deux peuplements ; un cycle de 4 ans n’en laisse que 1. Il faudrait un cycle d’au moins 5 ans."
            }
          ],
          "robustness": 58.5,
          "becomesInfeasibleLater": false
        }
      ]
    }
  ]
}
```

Règles :

- **`settings.priorities` et `weights`** : le classement dont les poids (rank order centroid) ont été calculés, et ces poids. L'écran des priorités affiche les parts de chaque critère seulement quand `settings.priorities` est le classement en cours : le front ne recalcule aucun poids.
- **Notes** : de 0 à 100 (décimales gardées, les écrans arrondissent). **Critères** : de 0 à 1, `null` = inconnu (laissé de côté dans la moyenne).
- **`decision`** : `garder`, `changer`, ou `aucune` quand aucune chaîne ne respecte les contraintes ; dans ce cas `chosen` vaut `null` et les cycles suivants ne sont pas renvoyés.
- **`steps`** : les cultures de la chaîne et les couverts (`kind: "couvert"`, sans position) dans l'ordre du calendrier ; dates ISO ; positions comptées à partir de 1. Une jachère n'a ni semis ni récolte.
- **`robustness`** : pire note de la chaîne adoptée dans les cycles suivants ; `null` pour une chaîne gardée du cycle précédent ou qui devient infaisable (`becomesInfeasibleLater`).
- **`twins.reliable`** : σ moyen ≤ 2. Sinon, l'écran prévient que la recommandation est moins fiable.
- **`meta.demo`** : `true` tant qu'une source est fictive (badge « Données d'exemple ») ; `meta.sources` dit lesquelles (`farmWeather`, `climateModels`, `twins`, `fieldMeasures`).
- **Valeurs manquantes** : toujours un `null` explicite, jamais une clé absente (`robustness`, `sowing`, `positions`, `sigma`…). Un nombre que JSON ne sait pas écrire (infini) devient `null`.
- **Messages** : en français, prêts à afficher, **sans nom d'étude** (règle de l'équipe ; les études sont seulement dans la page Sources).

## Lancer le serveur et le brancher

1. `cd api`, installer (`pip install -e ".[dev]"`) puis `python -m uvicorn field_shift.api.main:app --port 8000` : voir [`api/README.md`](../api/README.md).
2. `npm run check:algo -- http://localhost:8000` doit afficher « Tout respecte le contrat ».
3. `npm run dev` : le front appelle `http://localhost:8000` par défaut. Ailleurs, `VITE_ALGO_URL` donne l'adresse du serveur (dans `.env.local`, ou dans les variables du dépôt GitHub pour le site publié).

Le serveur n'a pas de mode démo : il lit toujours NASA POWER, et répond `502` (avec la source en cause) quand elle ne répond pas.

Un autre serveur (dans un autre langage) peut remplacer celui-ci : il lui suffit de répondre à `POST /plan` selon ce schéma.
