# Contrats d'API (v1)

Base : `/api/v1`. JSON en `snake_case`. Documentation interactive générée : `/api/docs`
(OpenAPI : `/api/openapi.json`). Exemples complets réels : `apps/web/src/api/__fixtures__/`.

Erreurs au format *problem details* (RFC 9457, `application/problem+json`) :

| HTTP | `code` | Cause |
|---|---|---|
| 422 | `validation_error` | Champ manquant, hors bornes, champ inconnu (liste dans `errors`) |
| 422 | `invalid_request` | Période invalide (avant 1981, année incomplète), culture ou modèle inconnu, rotation invalide |
| 422 | `unsupported_location` | Hémisphère sud (non pris en charge) |
| 503 | `climate_data_unavailable` | NASA indisponible et aucun instantané vérifié ; hors ligne sans instantané |
| 503 | `climate_provider_rate_limited` | Limite NASA atteinte (en-tête `Retry-After`) |
| 500 | `internal_error` | Message générique ; détail uniquement dans les journaux (avec `X-Request-ID`) |

CORS : origines listées dans `FIELDSHIFT_CORS_ORIGINS`, méthodes GET/POST seulement.

## Lecture du référentiel

| Endpoint | Réponse |
|---|---|
| `GET /health` | `{status, version, climate_source, crops, rotation_templates}` |
| `GET /crops` | Cultures avec exigences et leur `basis` (sources, `documented`/`provisional`, note) |
| `GET /rotation-templates` | Modèles de rotation à explorer, avec justification et sources |
| `GET /sources` | Bibliographie (citation, URL, date de consultation, conditions d'utilisation) |
| `GET /demo-farms` | Profils de démonstration (format identique à `farm` ci-dessous) |

## `POST /climate/analyze` → `ClimateAnalysisService.analyze`

```json
{ "location": {"latitude": 48.23, "longitude": -69.8, "precision": "approximate"},
  "first_year": null, "last_year": null,
  "observations": [{"text": "Orages en juin-juillet 2024", "topic": "harvest_weather", "year": 2024, "crop_id": null}] }
```

Réponse (extrait réel, Sacré-Cœur) :

```json
{ "period": {"first_year": 1981, "last_year": 2025, "years_analysed": 45},
  "provenance": {"provider": "NASA POWER ...", "api_version": "v2.10.3", "origin": "verified_snapshot",
                 "nature": "reanalysis_estimate", "spatial_resolution": "0,5° de latitude × 0,625° de longitude (grille MERRA-2)",
                 "grid_cell": {"cell_id": "lat+048.000_lon-0070.000", "...": "..."}, "grid_cell_elevation_m": 244.82,
                 "content_sha256": "a276ce46…", "citation": "The data was obtained from ...", "license": "… CC0 …"},
  "quality": {"level": "complete", "years_excluded": [], "warnings": [{"code": "near_cell_boundary", "message_fr": "…"}]},
  "indicators": [{"id": "crop_heat_units", "label_fr": "Unités thermiques maïs (UTM)", "unit": "UTM",
                  "definition_fr": "…", "source_ids": ["bourgeois_2012"],
                  "values": [{"year": 1981, "value": 1907.3}, "…"],
                  "summary": {"median": 2193, "p20": 1928, "p80": 2372, "trend": {"slope_per_decade": 169.0, "p_value": 0.0001, "is_significant": true}}}],
  "monthly_normals": ["…"],
  "observation_checks": [{"status": "compared", "positions": [{"indicator_id": "wet_days_june_july", "value": 24, "median": 29, "years_higher": 34, "years_compared": 45}]}] }
```

## `POST /rotations/compare` → `RotationComparisonService.compare`

Fusionne les endpoints envisagés `rotations/compare` et `simulations/historical` : mêmes
entrées, même jeu de données, un seul téléchargement (ADR 0005).

```json
{ "farm": { "name": "…", "location": {"latitude": 48.23, "longitude": -69.8, "precision": "approximate"},
            "current_rotation": {"name_fr": "Rotation actuelle", "crop_ids": ["oat", "hay_mixed", "hay_mixed"]},
            "priorities": {"climate_resilience": 1, "soil_health": 1, "water_conservation": 1, "potential_income": 1},
            "soil_texture": "loam", "soil_information_source": "declared_by_farmer", "irrigation_available": true,
            "excluded_crop_ids": [], "observations": [] },
  "selected_template_ids": null }
```

Réponse : `strategies` (actuelle, alternative résilience/sol, alternative selon les priorités ;
chacune avec scores, profil sol/eau, stress test annuel, explication), `considered` (tous les
modèles évalués, admissibles ou non, avec raisons), `criteria_status`, `crop_records` (chaque
culture × chaque année), `provenance`, `quality`, `notes_fr`, `method_limits_fr`.

## `POST /climate-twins` (phase 2)

Prévu : `{location, scenario: "ssp245", horizon: [2041, 2060]}` → analogues classés avec
distance, indicateurs comparés, scénario, modèles, limites. Voir architecture § 3.
