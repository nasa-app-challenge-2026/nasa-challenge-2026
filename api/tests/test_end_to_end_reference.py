"""The whole pipeline against the reference, from the weather to the plan.

The demo weather is generated exactly like field_shift.py does (same numpy random numbers), so
steps 2 to 10 run for real: climate of each cycle, climate models, twin search, planning. The
plans must be the ones of the reference, and so must the climate calendar of every cycle. The
water is the one of the reference (`tests/helpers/reference_water.py`).
"""

from __future__ import annotations

import pytest

from field_shift.algorithm.climate.target_climate_projector import TargetClimateProjector
from field_shift.algorithm.planning.parcel_planner import ParcelPlanner
from field_shift.algorithm.sources.cycle_data_provider import CycleDataProvider
from field_shift.algorithm.twins.climate_twin_finder import ClimateTwinFinder
from tests.helpers.demo_climate_models import demo_climate_models
from tests.helpers.demo_farm_weather import demo_farm_weather
from tests.helpers.demo_twin_atlas import demo_twin_atlas
from tests.helpers.demo_twin_crops import demo_twin_evidence
from tests.helpers.example_plans import example_water_model
from tests.helpers.reference_names import fixture
from tests.helpers.reference_plan import inputs_of
from tests.helpers.reference_water import WithReferenceWater
from tests.test_climate import assert_climate_close
from tests.test_reference_plans import SCENARIOS, assert_cycle

CURRENT_YEAR = 2026  # ANNEE_ACTUELLE of the reference
FARM = (45.63, -72.95)

WEATHER = demo_farm_weather()
DATA = CycleDataProvider(
    projector=TargetClimateProjector(WEATHER, CURRENT_YEAR, demo_climate_models(WEATHER)),
    twin_finder=ClimateTwinFinder(demo_twin_atlas(*FARM, WEATHER)),
    evidence_for=lambda first, last, twins, soil: demo_twin_evidence(first, last, twins),
    water=example_water_model(*FARM),
)


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_the_climate_of_every_cycle_is_the_reference_one(scenario):
    reference = fixture(f"plan-{scenario}.json")
    for window, expected in reference["windows"].items():
        first_year, last_year = (int(y) for y in window.split("-"))
        assert_climate_close(DATA.cycle_data(first_year, last_year).climate, expected["climate"])


@pytest.mark.parametrize("scenario", [s for s in SCENARIOS if s != "variant-sans-fourragere-libre"])
def test_the_demo_plans_are_the_reference_ones(scenario):
    reference = fixture(f"plan-{scenario}.json")
    inputs = inputs_of(reference)
    data = WithReferenceWater(DATA, reference["mesures"])
    planner = ParcelPlanner(inputs.time, inputs.farmer, data, inputs.today)
    for parcel, expected in zip(inputs.parcels, reference["parcels"], strict=True):
        plan = planner.plan(parcel)
        assert len(plan.cycles) == len(expected["cycles"])
        for cycle, expected_cycle in zip(plan.cycles, expected["cycles"], strict=True):
            assert_cycle(cycle, expected_cycle)
