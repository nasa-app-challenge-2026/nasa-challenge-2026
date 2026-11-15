"""The sections of a farm planned at the same time, in worker processes
(`services/parallel_plan_service.py`): the plan is exactly the one of `PlanService`, only sooner.
"""

from __future__ import annotations

import pickle
from datetime import UTC, datetime

import pytest

from field_shift.api.app import SERVICE_FAILURES
from field_shift.contract.farm_input import FarmInput
from field_shift.services.parallel_plan_service import (
    DEFAULT_MAX_WORKERS,
    WORKERS_ENV,
    ParallelPlanService,
    workers_from_environment,
)
from tests.helpers.example_plans import example_plan_service

GENERATED_AT = datetime(2026, 11, 13, tzinfo=UTC)
#: The example with the shortest plan (two crops a year, two cycles).
EXAMPLE = "deux-cultures-par-an"


@pytest.fixture(scope="module")
def parallel():
    service = ParallelPlanService(example_plan_service, workers=3)
    yield service
    service.close()


def test_the_plan_is_the_one_of_a_single_process(parallel, plan_service, example_inputs):
    farm = FarmInput.model_validate(example_inputs[EXAMPLE])
    expected = plan_service.plan_farm(farm, GENERATED_AT)
    plan = parallel.plan_farm(farm, GENERATED_AT)
    assert [section.id for section in plan.sections] == [s.id for s in farm.sections]
    assert plan.model_dump(mode="json", by_alias=True) == expected.model_dump(
        mode="json", by_alias=True
    )


def test_fewer_workers_than_sections_still_plan_every_section(plan_service, example_inputs):
    farm = FarmInput.model_validate(example_inputs[EXAMPLE])
    service = ParallelPlanService(example_plan_service, workers=1)
    try:
        plan = service.plan_farm(farm, GENERATED_AT)
    finally:
        service.close()
    assert plan == plan_service.plan_farm(farm, GENERATED_AT)


def test_one_section_or_no_worker_is_planned_in_the_server_process(example_inputs):
    raw = example_inputs[EXAMPLE]
    one_section = FarmInput.model_validate({**raw, "sections": raw["sections"][:1]})
    without_workers = ParallelPlanService(example_plan_service, workers=0)
    with_workers = ParallelPlanService(example_plan_service, workers=2)
    try:
        assert len(without_workers.plan_farm(one_section, GENERATED_AT).sections) == 1
        assert len(with_workers.plan_farm(one_section, GENERATED_AT).sections) == 1
        # No section was sent to a worker: none was started.
        assert all(not slot._processes for slot in with_workers._slots)
    finally:
        without_workers.close()
        with_workers.close()


def test_the_number_of_workers_comes_from_the_environment():
    assert workers_from_environment({WORKERS_ENV: "0"}) == 0
    assert workers_from_environment({WORKERS_ENV: " 2 "}) == 2
    assert workers_from_environment({WORKERS_ENV: "-4"}) == 0
    assert 0 <= workers_from_environment({}) <= DEFAULT_MAX_WORKERS
    with pytest.raises(ValueError, match=WORKERS_ENV):
        workers_from_environment({WORKERS_ENV: "beaucoup"})


@pytest.mark.parametrize("failure", [failure for failure, _ in SERVICE_FAILURES])
def test_a_data_service_that_fails_in_a_worker_reaches_the_route(failure):
    # A worker sends its error to the server process pickled: it must come back as itself, so
    # that the route answers the 502 that names the service.
    error = pickle.loads(pickle.dumps(failure("le service ne répond pas")))
    assert type(error) is failure
    assert str(error) == "le service ne répond pas"
