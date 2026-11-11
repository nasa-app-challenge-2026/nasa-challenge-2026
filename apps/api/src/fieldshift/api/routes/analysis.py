from __future__ import annotations

from fastapi import APIRouter

from fieldshift.api.dependencies import ContainerDep
from fieldshift.api.schemas.catalog import observation_to_domain
from fieldshift.api.schemas.climate import (
    ClimateAnalysisOut,
    ClimateAnalyzeRequest,
    climate_analysis_out,
)
from fieldshift.api.schemas.rotations import (
    RotationCompareRequest,
    RotationComparisonOut,
    comparison_out,
)
from fieldshift.application.climate_analysis import ClimateAnalysisRequest

router = APIRouter(tags=["analyse"])
ERRORS: dict[int | str, dict[str, str]] = {
    422: {"description": "Requête invalide (problem+json)"},
    503: {"description": "Données NASA indisponibles et aucun instantané vérifié"},
}


@router.post("/climate/analyze", responses=ERRORS)
def analyze_climate(body: ClimateAnalyzeRequest, container: ContainerDep) -> ClimateAnalysisOut:
    analysis = container.climate.analyze(
        ClimateAnalysisRequest(
            location=body.location.to_point(),
            location_precision=body.location.precision,
            first_year=body.first_year,
            last_year=body.last_year,
            observations=tuple(observation_to_domain(o) for o in body.observations),
        )
    )
    return climate_analysis_out(analysis)


@router.post("/rotations/compare", responses=ERRORS)
def compare_rotations(
    body: RotationCompareRequest, container: ContainerDep
) -> RotationComparisonOut:
    farm = body.farm.to_domain()
    result = container.comparison.compare(
        farm, body.first_year, body.last_year, body.selected_template_ids
    )
    return comparison_out(result, farm.priorities)
