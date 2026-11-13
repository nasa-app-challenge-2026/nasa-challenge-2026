# Contrat entre le front end et l'algorithme · v1.0

Ce document dit **exactement** ce que l'interface envoie à l'algorithme et ce qu'elle attend en retour. Si l'algorithme respecte ce contrat, on le branche en changeant une seule variable, sans toucher aux écrans.

- **Source de vérité :** [`contract/field-shift.schema.json`](../contract/field-shift.schema.json) (JSON Schema, draft-07)
- **Exemples :** [`contract/examples/`](../contract/examples/) : une entrée par cas de référence, et la réponse du moteur de démo pour montrer la forme attendue
- **Vérification automatique :** `npm run check:algo -- http://localhost:8000`

## Qui calcule quoi

| Le front end calcule (déjà fait)                                                                                                                                      | L'algorithme calcule (à faire)                                                                                                                                            |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| La structure : calendrier année par année, durée des cycles, cycle coupé à la fin, délais de retour (cadenas), décalage des sections, mélange de cultures de la ferme | Tout ce qui demande des **données** ou des **études** : scores, rendements, revenus, comparaisons, stress test, suggestions, explications, données NASA de chaque section |
| Le compte des rôles pour la santé du sol (années avec azote, couverture…), à partir du catalogue des cultures                                                         | La **valeur** de ces rôles dans les scores                                                                                                                                |

Le catalogue des cultures (noms, délais de retour, rôles) est dans [`src/data/crops.js`](../src/data/crops.js). Les délais sont provisoires : s'ils changent côté algo, il faut les changer là aussi.

## Les trois opérations

Toutes sont des `POST` avec un corps JSON et une réponse JSON.

| Opération             | Route         | Entrée             | Sortie              | Utilisée par                                      |
| --------------------- | ------------- | ------------------ | ------------------- | ------------------------------------------------- |
| Évaluer la ferme      | `/evaluate`   | `FarmInput`        | `FarmPlan`          | Tableau de bord, Résultats, Explorer, Stress test |
| Proposer une rotation | `/propose`    | `ProposeRequest`   | `ProposeResponse`   | Bouton « Laisser l'appli proposer »               |
| Données d'une section | `/field-data` | `FieldDataRequest` | `FieldDataResponse` | Écran « Mon champ »                               |

Le serveur doit autoriser le CORS depuis l'adresse du site (GitHub Pages) avec l'en-tête `Content-Type`.

## Entrée : `FarmInput`

```json
{
  "version": "1.0",
  "farm": {
    "type": "grandes-cultures",
    "location": { "lat": 45.63, "lon": -72.95, "label": "Saint-Hyacinthe, QC" },
    "startYear": 2027,
    "horizonYears": 12,
    "priorities": ["revenu", "resilience", "sol", "eau", "travail"],
    "sensors": false,
    "seeds": { "crops": ["mais", "soya", "ble", "patate"], "covers": ["seigle", "trefle"] }
  },
  "options": { "stressYears": 1 },
  "sections": [
    {
      "id": "A",
      "areaHa": 12,
      "offset": 0,
      "currentCrop": "mais",
      "polygon": [
        [45.632, -72.952],
        [45.632, -72.948],
        [45.629, -72.948]
      ],
      "rotation": [
        { "crop": "soya", "years": 1, "cover": null },
        { "crop": "ble", "years": 1, "cover": "trefle" },
        { "crop": "mais", "years": 1, "cover": "seigle" },
        { "crop": "patate", "years": 1, "cover": null }
      ]
    }
  ]
}
```

Règles :

- **Cultures :** `mais`, `soya`, `ble`, `orge`, `patate`, `luzerne`. **Couvertures :** `seigle`, `trefle`, `radis`, ou `null`.
- **`years`** = nombre d'années qu'occupe une plantation (la luzerne occupe 3 ans). La durée du cycle est la somme des `years`.
- **`horizonYears`** = durée d'analyse **commune à toute la ferme**. Chaque section répète son cycle pour la remplir ; si ça ne tombe pas juste, le dernier cycle est coupé.
- **`offset`** = position dans le cycle la première année. C'est ce qui décale les sections entre elles (assolement).
- **`priorities`** = de la plus importante à la moins importante. Le front leur donne les poids 35, 25, 18, 13 et 9 % ; l'algo peut faire autrement.
- **`options.stressYears`** = durée d'un choc du stress test (1 ou 3 ans). La question est encore ouverte dans l'équipe.
- **`farm.seeds`** (optionnel) = la réserve de semences du fermier : les cultures (`crops`) et couvertures (`covers`) qu'il peut semer. Absent = tout le catalogue. Le front l'envoie toujours.
- **`section.currentCrop`** (optionnel, `null` possible) = ce qui pousse sur la section **maintenant**, la saison avant `startYear`. La culture de la première année analysée (position `offset` dans le cycle) ne doit pas répéter une culture d'un an (tous les délais de retour sont d'au moins 2 ans) ; un bloc de luzerne ne peut pas commencer en son milieu, sauf si la section est déjà en luzerne. Le front vérifie la même règle (`currentCropConflict` dans `src/lib/rotation.js`).
- Le front n'envoie **jamais** une rotation avec une année vide. Le fermier peut choisir à la main une culture hors de sa réserve : c'est permis, l'interface le signale.

## Sortie : `FarmPlan`

Un résultat par section, **dans le même ordre et avec le même `id`** que l'entrée.

```json
{
  "version": "1.0",
  "meta": { "engine": "nom-de-votre-algo", "demo": false, "generatedAt": "2026-11-14T12:00:00Z" },
  "farm": { "score": 74, "revenuePerYear": 38868 },
  "sections": [
    {
      "id": "A",
      "scores": { "eau": 72, "sol": 81, "resilience": 76, "revenu": 68 },
      "confidence": "elevee",
      "comparisons": {
        "mais-continu": {
          "yieldGainPct": [6, 9],
          "revenueDeltaPerHaYear": 84,
          "scores": { "eau": 58, "sol": 52, "resilience": 48, "revenu": 64 }
        },
        "mais-soya": {
          "yieldGainPct": [2, 4],
          "revenueDeltaPerHaYear": 31,
          "scores": { "eau": 64, "sol": 62, "resilience": 60, "revenu": 67 }
        }
      },
      "revenue": {
        "perHaYear": 1015,
        "series": [{ "year": 2027, "value": 980, "low": 900, "high": 1050 }],
        "baselines": {
          "mais-continu": [{ "year": 2027, "value": 968 }],
          "mais-soya": [{ "year": 2027, "value": 990 }]
        }
      },
      "workload": "moyenne",
      "stress": {
        "normal": {
          "yieldPct": [0, 0],
          "baselineYieldPct": [0, 0],
          "scores": { "eau": 72, "sol": 81, "resilience": 76, "revenu": 68 }
        },
        "sec": {
          "yieldPct": [-9, -14],
          "baselineYieldPct": [-22, -30],
          "scores": { "eau": 54, "sol": 75, "resilience": 67, "revenu": 54 }
        },
        "chaud": {
          "yieldPct": [-7, -11],
          "baselineYieldPct": [-14, -19],
          "scores": { "eau": 60, "sol": 77, "resilience": 68, "revenu": 57 }
        },
        "ravageurs": {
          "yieldPct": [-4, -7],
          "baselineYieldPct": [-15, -24],
          "scores": { "eau": 72, "sol": 78, "resilience": 71, "revenu": 61 }
        }
      },
      "suggestions": [
        {
          "code": "ADD_DEEP_ROOTS",
          "message": "Aucune racine profonde : un radis fourrager l'hiver casserait le sol tassé."
        },
        {
          "code": "SWAP_MAIS_ORGE",
          "scenario": "sec",
          "message": "De l'orge à la place du maïs réduirait la perte des années sèches.",
          "yieldPctAfter": [-6, -10]
        }
      ],
      "explanations": [
        {
          "code": "soya>ble",
          "message": "Le blé après le soya profite de l'azote laissé par le soya."
        }
      ],
      "warnings": []
    }
  ]
}
```

Règles :

- **Scores :** entiers de 0 à 100. Plus haut = mieux, pour les quatre.
- **Fourchettes (`yieldGainPct`, `yieldPct`…) :** `[bas, haut]` en pourcentage. Pour les pertes, des nombres négatifs.
- **`series`** : une valeur par année de l'horizon, en $ net par hectare.
- **`confidence`** : `elevee`, `moyenne` ou `faible`. Règle de l'équipe : un niveau de moins à partir de 15 ans.
- **`workload`** : `faible`, `moyenne` ou `elevee`.
- **`meta.demo`** : `true` affiche le badge « Données d'exemple ». Le vrai algo renvoie `false`.
- **Règle de l'équipe : aucun nom d'étude** dans `message`. Les études sont seulement dans la page Sources.
- **Codes de suggestion** connus par l'interface : `SWAP_MAIS_ORGE` (bouton « Essayer ce changement » dans le stress test), `ADD_DEEP_ROOTS`, `ADD_COVER`. Un autre code s'affiche aussi, mais sans bouton d'action.

## `/propose`

Entrée : `{ "farm": FarmInput, "sectionId": "A", "cycleYears": 4 }`.
Sortie : `{ "rotation": [RotationEntry…], "reasons": ["…"], "missingSeeds": ["…"] }`.

- La rotation dure exactement `cycleYears` ans et respecte les délais de retour.
- Elle n'utilise **que** les cultures et couvertures de `farm.seeds`. Si c'est impossible (ex. une seule culture et 3 ans), elle peut en ajouter, mais doit les lister dans `missingSeeds` : l'interface propose alors de les ajouter à la réserve.
- Sa première année (position `offset` de la section) respecte `currentCrop` (voir plus haut).
- Elle suit l'ordre des `priorities`.
- `reasons` : 2 à 5 phrases courtes, affichées telles quelles sous la rotation (« Pourquoi cette rotation »). Pas de nom d'étude.
- Le bouton « Proposer avec mes semences » de l'étape « Mes cultures » appelle `/propose` pour chaque section l'une après l'autre (chaque appel voit les rotations déjà choisies), avec `cycleYears` = la somme des durées des semences (entre 2 et 6), puis le front décale les sections.

## `/field-data`

Entrée : `{ "farm": FarmInput, "sectionId": "A" }`.
Sortie : `{ "sectionId": "A", "demo": false, "metrics": [ … ] }`, une carte par métrique :

```json
{
  "id": "soilMoisture",
  "label": "Humidité du sol",
  "value": 0.28,
  "unit": "m³/m³",
  "source": "NASA SMAP · estimation",
  "fromSensors": false,
  "series": [0.26, 0.27, 0.29],
  "explain": "La part d'eau dans le sol en surface…"
}
```

Métriques attendues par l'écran : `rain` (GPM IMERG), `soilMoisture` (SMAP, ou capteurs si `farm.sensors`), `temperature` (POWER), `et` (ECOSTRESS), `ndvi` (HLS), `soil` (SoilGrids, valeur texte).

## Les trois cas de référence

Les entrées sont dans `contract/examples/` :

| Fichier                      | Ce qu'il teste                                                    |
| ---------------------------- | ----------------------------------------------------------------- |
| `cas1-meme-rotation-decalee` | Même rotation de 4 ans, sections décalées : assolement parfait    |
| `cas2-durees-differentes`    | A, B, C en 4 ans, D en 3 ans : années déséquilibrées              |
| `cas3-luzerne-cycle-coupe`   | D fait maïs, soya, luzerne 3 ans = 5 ans : cycle coupé sur 12 ans |
| `ferme-demo`                 | La ferme de démo de l'appli, avec des couvertures                 |

## Brancher l'algo

1. L'algo tourne quelque part (en local : `http://localhost:8000`).
2. `npm run check:algo -- http://localhost:8000` doit afficher « Tout respecte le contrat ». Il vérifie aussi que `/propose` reste dans la réserve de semences et respecte la culture actuelle de chaque section.
3. Dans `.env.local` : `VITE_ALGO_MODE=remote` et `VITE_ALGO_URL=http://localhost:8000`, puis `npm run dev`.
4. En ligne : les mêmes valeurs dans les variables du dépôt GitHub (Settings → Secrets and variables → Actions → Variables).

L'algo peut aussi être écrit en JavaScript et appelé directement : il suffit d'un objet avec `evaluateFarm`, `proposeRotation` et `getFieldData` (voir `src/algo/mockEngine.js`), branché dans `src/algo/index.js`.
