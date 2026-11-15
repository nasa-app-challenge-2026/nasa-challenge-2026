# `field_shift.algorithm.yield_model` — Modèle régional de rendement (Python)

Portage Python 1:1 de [`algo-rendement/`](../../../../algo-rendement/index.js), avec **parité numérique exacte** vérifiée contre [`api/tests/fixtures/yield_js_parity.json`](../../../tests/fixtures/yield_js_parity.json).

Pour la documentation mathématique et méthodologique complète (segmentation spatiale BFS des parcelles, correction météo log-Ridge $L_2$, référence unifiée symétrique, erreur-type clusterisée par année, Jumeaux Climatiques et projections NASA NEX-GDDP-CMIP6), consulter :
- **[`algo-rendement/LOGIQUE_ALGO.md`](../../../../algo-rendement/LOGIQUE_ALGO.md)**
- **[`algo-rendement/README.md`](../../../../algo-rendement/README.md)**

## Utilisation en Python

```python
from field_shift.algorithm.yield_model import run_regional_yield_pipeline

result = run_regional_yield_pipeline(
    lat=45.6,
    lon=-72.9,
    cycle_years=4,
    current_crop="mais",
    scenario="ssp245",
)
```

## Exécution des tests

```sh
api/.venv/Scripts/pytest api/tests/test_yield_model.py -v
```

