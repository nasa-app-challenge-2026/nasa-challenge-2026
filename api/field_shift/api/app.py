"""The FastAPI application.

    POST /plan             plans a farm (field_shift v5.1)
    POST /rotations/rank   ranks candidate rotations on four measures (see `ranking_routes.py`,
                           which also holds /measures/…, /crops and /data-sources)
    GET  /health           says the server is up

Run it from `backend/server`:   python -m uvicorn field_shift.api.main:app --port 8000
Interactive documentation:      http://localhost:8000/docs
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from field_shift import __version__
from field_shift.algorithm.field_shift_algorithm import ALGORITHM_VERSION
from field_shift.api.ranking_routes import ranking_router
from field_shift.api.settings import Settings
from field_shift.contract.farm_input import FarmInput
from field_shift.contract.farm_plan import FarmPlan
from field_shift.data_access.nasa_power import NasaPowerClient
from field_shift.data_access.site_data import NoSiteData, RemoteSiteData
from field_shift.data_access.weather_providers import DemoWeatherProvider, NasaPowerWeatherProvider
from field_shift.services.plan_service import PlanService
from field_shift.services.ranking_service import RankingService

DESCRIPTION = """
Plans the crop rotations of a farm with the **climate twin** method (field_shift v5.1): for each
cycle, the climate the farm will have, the places that already had it, what grows there on the
same soil, and the best chain of crops for each section.

The contract (`FarmInput` → `FarmPlan`) is described in `docs/ALGO_CONTRACT.md`.

**Rotation ranking** (`POST /rotations/rank`): from a selection of crops or of rotations, the
duration of the simulation, the priorities and the sections of a field, each rotation gets four
measures (yield, water demand, soil protection, pests) added into one score with the priorities
as weights; the rotations come back ranked for every section. Only the soil protection (erosion
and infiltration: RPI, RUSLE, infiltration meta-analysis) is computed today.
"""


def plan_service_for(settings: Settings) -> PlanService:
    """The service wired to the weather source the settings ask for."""
    if settings.weather == "demo":
        return PlanService(DemoWeatherProvider())
    client = NasaPowerClient(url=settings.data_sources.power_daily_url)
    return PlanService(NasaPowerWeatherProvider(client))


def ranking_service_for(settings: Settings) -> RankingService:
    """The ranking service wired to the configured data sources (none in demo mode: the sections
    are then computed with what the request gives and the defaults of the model)."""
    if settings.weather == "demo":
        return RankingService(NoSiteData())
    return RankingService(RemoteSiteData(settings.data_sources))


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

    router = APIRouter()

    @router.get("/health", summary="Is the server up?")
    def health(request: Request) -> dict[str, str]:
        return {
            "status": "ok",
            "version": __version__,
            "algorithm": ALGORITHM_VERSION,
            "weather": request.app.state.settings.weather,
        }

    @router.post("/plan", response_model=FarmPlan, summary="Plan every section of a farm")
    def plan(farm_input: FarmInput, service: PlanService = Depends(get_plan_service)) -> FarmPlan:
        return service.plan_farm(farm_input)

    app.include_router(router)
    app.include_router(ranking_router())
    return app
