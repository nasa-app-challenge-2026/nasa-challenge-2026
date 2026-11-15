"""The routes of the rotation ranking (no logic here: they call `RankingService`).

    POST /rotations/rank            the rotations of every section, ranked on the four measures
    POST /measures/protection-sol   one measure alone: erosion and infiltration      (computed)
    POST /measures/rendement        one measure alone: yield                        (501 for now)
    POST /measures/eau              one measure alone: water demand                 (501 for now)
    POST /measures/ravageurs        one measure alone: pests and diseases           (computed)
    GET  /measures                  the four measures and which ones are computed
    GET  /crops                     the crops a rotation can contain
    GET  /data-sources              the addresses of the data sources the server runs with

The five POST routes take the same request (`RankingInput`) and give the same answer
(`RotationRanking`); a `/measures/…` route ranks on its measure alone, whatever the priorities.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Request, status

from field_shift.contract.ranking_mapper import crops_out, public_url
from field_shift.contract.rotation_ranking import (
    CropOut,
    DataSourceOut,
    RankingInput,
    RotationRanking,
)
from field_shift.reference.measures import (
    MEASURE_IDS,
    MEASURE_NAMES,
    MEASURE_PESTS,
    MEASURE_SOIL_PROTECTION,
    MEASURE_UNITS,
    MEASURE_WATER,
    MEASURE_YIELD,
)
from field_shift.services.ranking_service import (
    RankingInputError,
    RankingService,
    SectionDataError,
)

#: Status of a request that is well formed but cannot be ranked (as the validation errors).
UNPROCESSABLE = 422
#: A data service the ranking needs failed.
BAD_GATEWAY = 502
DATA_ERROR_RESPONSE = {
    BAD_GATEWAY: {"description": "A data service failed: `detail` names the section and service."}
}

TAG_RANKING = "Classement des rotations"
TAG_MEASURES = "Mesures"
TAG_REFERENCE = "Référence et configuration"

#: Path of the route of each measure, under /measures/.
MEASURE_PATHS = {
    MEASURE_YIELD: "rendement",
    MEASURE_WATER: "eau",
    MEASURE_SOIL_PROTECTION: "protection-sol",
    MEASURE_PESTS: "ravageurs",
}


def get_ranking_service(request: Request) -> RankingService:
    return request.app.state.ranking_service


def _ranked(
    service: RankingService, ranking_input: RankingInput, only_measure: str | None = None
) -> RotationRanking:
    """The ranking; a 422 in the format of the validation errors when it cannot be done, a 502
    with every failed service when the data of a section could not be read."""
    try:
        return service.rank(ranking_input, only_measure)
    except RankingInputError as error:
        raise HTTPException(
            UNPROCESSABLE,
            detail=[{"loc": ["body"], "msg": str(error), "type": "value_error"}],
        ) from error
    except SectionDataError as error:
        raise HTTPException(
            BAD_GATEWAY,
            detail=[
                {"section": error.section_id, "source": failure.dataset, "msg": failure.reason}
                for failure in error.failures
            ],
        ) from error


def _measure_route(measure_id: str) -> Callable[..., RotationRanking]:
    """The handler of `POST /measures/<measure>`: 501 while the measure is not written."""

    def rank_on_one_measure(
        ranking_input: RankingInput, service: RankingService = Depends(get_ranking_service)
    ) -> RotationRanking:
        if measure_id not in service.implemented_measures:
            raise HTTPException(
                status.HTTP_501_NOT_IMPLEMENTED,
                detail=(
                    f"La mesure « {MEASURE_NAMES[measure_id]} » n’est pas encore calculée. "
                    f"Mesures disponibles : {', '.join(service.implemented_measures)}."
                ),
            )
        return _ranked(service, ranking_input, measure_id)

    rank_on_one_measure.__name__ = f"measure_{measure_id}"  # a distinct operation id in /docs
    return rank_on_one_measure


def ranking_router() -> APIRouter:
    """The router with every route of the module documentation."""
    router = APIRouter()

    @router.post(
        "/rotations/rank",
        response_model=RotationRanking,
        tags=[TAG_RANKING],
        summary="Rank the candidate rotations of every section",
        responses=DATA_ERROR_RESPONSE,
    )
    def rank_rotations(
        ranking_input: RankingInput, service: RankingService = Depends(get_ranking_service)
    ) -> RotationRanking:
        """For each section, every rotation gets a result per measure (yield, water demand, soil
        protection, pests); the results are added with the priorities as weights, and the
        rotations come back sorted, the best first, with their measures.

        Only the soil protection is computed today: the other measures are returned with
        `available: false` and do not count in the score.
        """
        return _ranked(service, ranking_input)

    for measure_id in MEASURE_IDS:
        router.add_api_route(
            f"/measures/{MEASURE_PATHS[measure_id]}",
            _measure_route(measure_id),
            methods=["POST"],
            response_model=RotationRanking,
            tags=[TAG_MEASURES],
            summary=f"{MEASURE_NAMES[measure_id]} : classer les rotations sur cette seule mesure",
            responses={
                501: {"description": "The logic of this measure is not written yet."},
                **DATA_ERROR_RESPONSE,
            },
        )

    @router.get("/measures", tags=[TAG_MEASURES], summary="The four measures of the ranking")
    def measures(service: RankingService = Depends(get_ranking_service)) -> list[dict]:
        return [
            {
                "id": measure_id,
                "name": MEASURE_NAMES[measure_id],
                "unit": MEASURE_UNITS[measure_id],
                "path": f"/measures/{MEASURE_PATHS[measure_id]}",
                "implemented": measure_id in service.implemented_measures,
            }
            for measure_id in MEASURE_IDS
        ]

    @router.get(
        "/crops",
        response_model=list[CropOut],
        tags=[TAG_REFERENCE],
        summary="The crops a rotation can contain, with their soil protection scores",
    )
    def crops() -> list[CropOut]:
        return crops_out()

    @router.get(
        "/data-sources",
        response_model=list[DataSourceOut],
        tags=[TAG_REFERENCE],
        summary="The data services and the addresses the server runs with",
    )
    def data_sources(request: Request) -> list[DataSourceOut]:
        """Addresses are shown without their query string (it may hold a key); headers are never
        shown."""
        config = request.app.state.settings.data_sources
        return [
            DataSourceOut(
                key=source.key,
                dataset=source.dataset,
                provides=source.provides,
                reference=source.reference,
                url=public_url(source.url),
            )
            for source in config.sources.values()
        ]

    return router
