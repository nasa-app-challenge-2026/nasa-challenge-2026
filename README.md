# Field Shift — rotations de cultures et climat (NASA Space Apps 2026)

Outil d'aide à la décision pour le défi *Field Shift: Adapting Farms with NASA Data*. Il compare la
rotation actuelle d'une ferme à deux alternatives et les soumet à un **stress test climatique
rétrospectif** sur 45 années de données quotidiennes NASA POWER (1981–2025), en expliquant
chaque résultat : pourquoi, avec quelles données, bénéfices, compromis, incertitudes, et ce qui
reste à valider localement.

> Outil d'exploration : il ne remplace pas un agronome et ne garantit aucun rendement.

Profil de démonstration : ferme d'avoine et de foin de **Sacré-Cœur (Québec)**, issu d'une entrevue.

## Démarrage rapide

Prérequis : Python 3.12, [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`), Node.js 22.

```bash
# API (http://127.0.0.1:8000, documentation interactive sur /api/docs)
cd apps/api
uv sync --frozen
uv run uvicorn --factory fieldshift.api.app:create_app --reload --port 8000

# Interface (http://localhost:5173, les appels /api sont relayés vers l'API)
cd apps/web
npm ci
npm run dev
```

### Mode démonstration hors ligne

```bash
FIELDSHIFT_CLIMATE_SOURCE=snapshot_only uv run uvicorn --factory fieldshift.api.app:create_app --port 8000
```

Seuls les instantanés versionnés dans `data/snapshots/` sont utilisés (réponses NASA réelles,
vérifiées par SHA-256). En mode `live` (défaut), l'instantané n'est utilisé que si l'API NASA
échoue, et l'interface le signale.

## Tests et qualité

```bash
cd apps/api && uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run pytest
cd apps/web && npm run format:check && npm run lint && npm run typecheck && npm test && npm run build
```

Les tests n'appellent jamais l'API NASA. La CI (`.github/workflows/ci.yml`) exécute tout cela à
chaque push et vérifie que les réponses d'exemple du frontend correspondent à l'API.

## Variables d'environnement

Voir [.env.example](.env.example) (préfixe `FIELDSHIFT_`). Aucune clé n'est nécessaire.

## Scripts

| Commande (depuis `apps/api`) | Rôle |
|---|---|
| `uv run python ../../scripts/refresh_snapshot.py 2025` | Re-télécharge les instantanés NASA des fermes de démo |
| `uv run python ../../scripts/export_api_fixtures.py` | Régénère les réponses réelles utilisées par les tests du frontend |

## Structure

```
apps/api/      API FastAPI + noyau métier Python (domain / application / infrastructure / api)
apps/web/      Interface React + TypeScript (Vite, Leaflet, Recharts, Zod)
data/          Référentiel versionné (cultures, rotations, sources, fermes de démo) et instantanés NASA
docs/          Architecture, API, méthodologie, sources, ADR, feuille de route, usage de l'IA
scripts/       Opérations reproductibles
```

Documentation : [architecture](docs/architecture.md) · [API](docs/api.md) ·
[méthodologie](docs/methodology.md) · [sources de données](docs/data-sources.md) ·
[feuille de route et équipe](docs/roadmap.md) · [ADR](docs/adr/) · [usage de l'IA](docs/ai-usage.md)

## Données

Données climatiques : NASA POWER (MERRA-2), licence CC0. *The data was obtained from the
National Aeronautics and Space Administration (NASA) Langley Research Center (LaRC) Prediction
Of Worldwide Energy Resources (POWER) project funded through the NASA Earth Science Division.*
