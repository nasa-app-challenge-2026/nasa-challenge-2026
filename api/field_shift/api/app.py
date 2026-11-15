"""The FastAPI application.

    POST /plan             plans a farm (field_shift v5.1)
    POST /rotations/rank   ranks candidate rotations on four measures (see `ranking_routes.py`,
                           which also holds /measures/…, /crops and /data-sources)
    GET  /health           says the server is up

Run it from `api/`:             python -m uvicorn field_shift.api.main:app --port 8000
Interactive documentation:      http://localhost:8000/docs

A data service that fails (NASA POWER, SoilGrids, Open-Meteo, MODIS) gives a 502 that names it:
there is no fictitious data to fall back on.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from field_shift import __version__
from field_shift.algorithm.field_shift_algorithm import ALGORITHM_VERSION
from field_shift.algorithm.sources.field_data import FieldDataUnavailableError
from field_shift.api.ranking_routes import ranking_router
from field_shift.api.settings import Settings
from field_shift.contract.farm_input import FarmInput
from field_shift.contract.farm_plan import FarmPlan
from field_shift.data_access.data_source_config import SOILGRIDS
from field_shift.data_access.disk_cache import DataCache
from field_shift.data_access.field_measures import RemoteFieldData
from field_shift.data_access.field_shift_eau import (
    WaterDataUnavailableError,
    water_models,
)
from field_shift.data_access.nasa_power import NasaPowerClient, WeatherUnavailableError
from field_shift.data_access.place_data import RemotePlaceData
from field_shift.data_access.power_grid import GridUnavailableError
from field_shift.data_access.power_projection import ProjectionUnavailableError
from field_shift.data_access.site_data import RemoteSiteData
from field_shift.data_access.soilgrids import SoilGridsClient
from field_shift.data_access.twin_crops import CropMapsUnavailableError
from field_shift.data_access.weather_providers import NasaPowerWeatherProvider
from field_shift.services.plan_service import PlanService
from field_shift.services.ranking_service import RankingService

#: A data service the answer depends on failed.
BAD_GATEWAY = 502

DESCRIPTION = """
Plans the crop rotations of a farm with the **climate twin** method (field_shift v5.1): for each
cycle, the climate the farm will have, the places that already had it, what grows there on the
same soil, and the best chain of crops for each section.

The contract (`FarmInput` → `FarmPlan`) is described in `docs/ALGO_CONTRACT.md`.

**Rotation ranking** (`POST /rotations/rank`): from a selection of crops or of rotations, the
duration of the simulation, the priorities and the sections of a field (each with its outline,
a GeoJSON polygon), each rotation gets four measures (yield, water demand, soil protection, pests)
added into one score with the priorities as weights; the rotations come back ranked for every
section. Only the soil protection (erosion and infiltration: RPI, RUSLE, infiltration
meta-analysis) is computed today. Its data are read from SoilGrids, Copernicus DEM, NASA POWER
and MODIS; a service that fails gives a **502** naming it.
"""


def plan_service_for(settings: Settings) -> PlanService:
    """The plan service on the real data services, their answers kept on disk."""
    cache = DataCache.default()
    sources = settings.data_sources
    client = NasaPowerClient(url=sources.power_daily_url, cache=cache)
    return PlanService(
        NasaPowerWeatherProvider(client),
        water_models(SoilGridsClient(sources[SOILGRIDS], cache=cache)),
        RemotePlaceData(sources, cache=cache),
        RemoteFieldData(sources, cache=cache),
    )


def ranking_service_for(settings: Settings) -> RankingService:
    """The ranking service on the configured data services."""
    return RankingService(RemoteSiteData(settings.data_sources, cache=DataCache.default()))


#: Failures of a data service, the service they name (each answered 502).
SERVICE_FAILURES = (
    (WeatherUnavailableError, "NASA POWER (MERRA-2)"),
    (WaterDataUnavailableError, "Sol (SSURGO / SoilGrids)"),
    (ProjectionUnavailableError, "NASA NEX-GDDP-CMIP6 (NASA POWER)"),
    (GridUnavailableError, "NASA POWER (grille régionale)"),
    (CropMapsUnavailableError, "Cartes de cultures (AAC / USDA CDL)"),
    (FieldDataUnavailableError, "Mesures de la section"),
)


def get_plan_service(request: Request) -> PlanService:
    return request.app.state.plan_service


def create_app(
    settings: Settings | None = None,
    plan_service: PlanService | None = None,
    ranking_service: RankingService | None = None,
) -> FastAPI:
    """Builds the application. `plan_service` and `ranking_service` let the tests give their own
    weather and data sources."""
    settings = settings or Settings.from_environment()
    app = FastAPI(title="Field Shift", version=__version__, description=DESCRIPTION)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.state.settings = settings
    app.state.plan_service = plan_service or plan_service_for(settings)
    app.state.ranking_service = ranking_service or ranking_service_for(settings)

    def answer_bad_gateway(source: str):
        def handler(request: Request, error: Exception) -> JSONResponse:
            return JSONResponse(
                status_code=BAD_GATEWAY,
                content={"detail": [{"source": source, "msg": str(error)}]},
            )

        return handler

    for failure, source in SERVICE_FAILURES:
        app.add_exception_handler(failure, answer_bad_gateway(source))

    router = APIRouter()

    @router.get("/health", summary="Is the server up?")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__, "algorithm": ALGORITHM_VERSION}

    @router.post(
        "/plan",
        response_model=FarmPlan,
        summary="Plan every section of a farm",
        responses={BAD_GATEWAY: {"description": "A data service could not be read (named)."}},
    )
    def plan(farm_input: FarmInput, service: PlanService = Depends(get_plan_service)) -> FarmPlan:
        return service.plan_farm(farm_input)

    app.include_router(router)
    app.include_router(ranking_router())
    return app
