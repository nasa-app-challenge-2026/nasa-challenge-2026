"""The FastAPI application.

    POST /plan             plans a farm (field_shift v5.1)
    POST /rotations/rank   ranks candidate rotations on four measures (see `ranking_routes.py`,
                           which also holds /measures/…, /crops and /data-sources)
    GET  /health           says the server is up

Run it from `api/`:             python -m uvicorn field_shift.api.main:app --port 8000
Interactive documentation:      http://localhost:8000/docs

A data service that fails (NASA POWER, SoilGrids, Open-Meteo, MODIS) gives a 502 that names it:
there is no fictitious data to fall back on.

The sections of a farm are planned at the same time in worker processes (FIELD_SHIFT_WORKERS,
see `services/parallel_plan_service.py`), and the answers are compressed (a plan is ~250 kB of
JSON, ~25 kB once compressed).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from functools import partial
from typing import Protocol

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
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
from field_shift.services.parallel_plan_service import ParallelPlanService
from field_shift.services.plan_service import PlanService
from field_shift.services.ranking_service import RankingService

#: A data service the answer depends on failed.
BAD_GATEWAY = 502
#: Answers smaller than this are sent as they are (compressing them would not pay).
GZIP_MIN_BYTES = 1024


class AnswerUnexpectedErrors:
    """An error nobody planned for answers 500 with a message, inside the CORS middleware: the
    browser then reads the answer (with its CORS headers) instead of "cannot reach the server".
    Starlette's own 500 is outside CORS, without these headers. Written as a plain ASGI
    middleware (a few lines, no import beyond FastAPI's)."""

    def __init__(self, app) -> None:
        self._app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        started = False

        async def watched_send(message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self._app(scope, receive, watched_send)
        except Exception as error:  # the server stays up; the message says what failed
            if started:
                raise  # the answer is already on its way: nothing better to send
            body = json.dumps(
                {"detail": [{"msg": f"Erreur inattendue du serveur : {error}"}]},
                ensure_ascii=False,
            ).encode("utf-8")
            await send(
                {
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode("ascii")),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})


class FarmPlanner(Protocol):
    """What the route needs: `PlanService`, or the same in several processes."""

    def plan_farm(
        self, farm_input: FarmInput, generated_at: datetime | None = None
    ) -> FarmPlan: ...


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


def plan_service_for(settings: Settings) -> FarmPlanner:
    """The plan service of the server: in several processes when the settings give workers."""
    if settings.workers <= 0:
        return single_process_plan_service(settings)
    return ParallelPlanService(partial(single_process_plan_service, settings), settings.workers)


def single_process_plan_service(settings: Settings) -> PlanService:
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


def get_plan_service(request: Request) -> FarmPlanner:
    return request.app.state.plan_service


def create_app(
    settings: Settings | None = None,
    plan_service: FarmPlanner | None = None,
    ranking_service: RankingService | None = None,
) -> FastAPI:
    """Builds the application. `plan_service` and `ranking_service` let the tests give their own
    weather and data sources."""
    settings = settings or Settings.from_environment()
    planner = plan_service or plan_service_for(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        if isinstance(planner, ParallelPlanService):
            planner.close()  # the worker processes stop with the server

    app = FastAPI(
        title="Field Shift", version=__version__, description=DESCRIPTION, lifespan=lifespan
    )
    app.add_middleware(GZipMiddleware, minimum_size=GZIP_MIN_BYTES)
    app.add_middleware(AnswerUnexpectedErrors)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_origin_regex=settings.cors_origin_regex,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.state.settings = settings
    app.state.plan_service = planner
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
    def plan(farm_input: FarmInput, service: FarmPlanner = Depends(get_plan_service)) -> FarmPlan:
        return service.plan_farm(farm_input)

    app.include_router(router)
    app.include_router(ranking_router())
    return app
