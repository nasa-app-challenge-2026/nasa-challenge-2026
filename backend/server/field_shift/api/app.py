"""The FastAPI application: `POST /plan` plans a farm, `GET /health` says the server is up.

Run it from `backend/server`:   python -m uvicorn field_shift.api.main:app --port 8000
Interactive documentation:      http://localhost:8000/docs
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from field_shift import __version__
from field_shift.algorithm.field_shift_algorithm import ALGORITHM_VERSION
from field_shift.api.settings import Settings
from field_shift.contract.farm_input import FarmInput
from field_shift.contract.farm_plan import FarmPlan
from field_shift.data_access.weather_providers import DemoWeatherProvider, NasaPowerWeatherProvider
from field_shift.services.plan_service import PlanService

DESCRIPTION = """
Plans the crop rotations of a farm with the **climate twin** method (field_shift v5.1): for each
cycle, the climate the farm will have, the places that already had it, what grows there on the
same soil, and the best chain of crops for each section.

The contract (`FarmInput` → `FarmPlan`) is described in `docs/ALGO_CONTRACT.md`.
"""


def plan_service_for(settings: Settings) -> PlanService:
    """The service wired to the weather source the settings ask for."""
    weather = DemoWeatherProvider() if settings.weather == "demo" else NasaPowerWeatherProvider()
    return PlanService(weather)


def get_plan_service(request: Request) -> PlanService:
    return request.app.state.plan_service


def create_app(
    settings: Settings | None = None, plan_service: PlanService | None = None
) -> FastAPI:
    """Builds the application. `plan_service` lets the tests give their own weather."""
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
    return app
