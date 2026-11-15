"""Plans the sections of a farm at the same time, each in its own process.

Nothing of the algorithm changes here: a section is planned from the farm (place, cycle,
priorities, seeds) and from itself, never from the other sections. The plan of a farm is
therefore the plans of its sections put together, and each one can be computed alone
(`tests/test_parallel_plan_service.py` checks that the result is the one of `PlanService`).

Almost all the time of a plan is the daily soil water simulation of the best chains, in pure
Python: threads would wait for each other, processes do not. With four sections, the plan takes
about the time of its slowest section instead of the sum of the four.

    the server process   keeps the place, plans the first section
    one worker process   per other section, always the same one for the same rank: a section
                         planned again (the farmer changes a setting) finds the water scores
                         its worker already simulated

A worker builds its own `PlanService`. The place is built first in the server process: what
its data services answer is then on disk, and the workers read it there instead of asking the
network several times for the same thing.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from concurrent.futures import Future, ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from datetime import UTC, date, datetime
from typing import Any, Final

from field_shift.contract.farm_input import FarmInput
from field_shift.contract.farm_plan import FarmPlan
from field_shift.services.plan_service import PlanService

#: Number of worker processes; 0 plans every section in the server process, one after the other.
WORKERS_ENV: Final = "FIELD_SHIFT_WORKERS"
#: Workers started when the variable is absent (a farm of the demo has four sections: one is
#: planned by the server process, three by workers), never more than the other processors.
DEFAULT_MAX_WORKERS: Final = 3

#: Builds the plan service of a process. Sent to the workers: a function of a module (or a
#: `functools.partial` of one), not a lambda.
PlanServiceFactory = Callable[[], PlanService]

_worker_service: PlanService | None = None


def workers_from_environment(environment: Mapping[str, str] | None = None) -> int:
    """The number of worker processes asked for, else one per other processor (3 at most)."""
    env = os.environ if environment is None else environment
    asked = env.get(WORKERS_ENV, "").strip()
    if asked:
        try:
            return max(0, int(asked))
        except ValueError as error:
            raise ValueError(f"{WORKERS_ENV} doit être un nombre entier : {asked!r}") from error
    return min(DEFAULT_MAX_WORKERS, max(0, (os.cpu_count() or 1) - 1))


def _start_worker(factory: PlanServiceFactory) -> None:
    global _worker_service  # one service per worker process, kept between the requests
    _worker_service = factory()


def _plan_in_worker(farm: dict[str, Any], generated_at: datetime) -> FarmPlan:
    if _worker_service is None:
        raise RuntimeError("the worker process was started without its plan service")
    return _worker_service.plan_farm(FarmInput.model_validate(farm), generated_at)


class ParallelPlanService:
    """A `PlanService` that plans the sections of a farm in several processes."""

    def __init__(
        self,
        factory: PlanServiceFactory,
        workers: int,
        clock: Callable[[], date] = date.today,
    ) -> None:
        self._factory = factory
        self._local = factory()
        self._clock = clock
        self._slots = [self._new_slot() for _ in range(workers)]

    def _new_slot(self) -> ProcessPoolExecutor:
        """One process that keeps its plan service (started at its first section)."""
        return ProcessPoolExecutor(
            max_workers=1, initializer=_start_worker, initargs=(self._factory,)
        )

    def plan_farm(self, farm_input: FarmInput, generated_at: datetime | None = None) -> FarmPlan:
        if not self._slots or len(farm_input.sections) < 2:
            return self._local.plan_farm(farm_input, generated_at)
        # The same date and the same time for every section, whichever process plans it.
        today = farm_input.today or self._clock()
        generated_at = generated_at or datetime.now(UTC)
        location = farm_input.farm.location
        self._local.prepare_place(location.lat, location.lon, today)

        farms = [
            farm_input.model_copy(update={"today": today, "sections": [section]})
            for section in farm_input.sections
        ]
        jobs = [
            self._submit(rank % len(self._slots), farm, generated_at)
            for rank, farm in enumerate(farms[1:])
        ]
        try:
            plans = [self._local.plan_farm(farms[0], generated_at)]
            for farm, job in zip(farms[1:], jobs, strict=True):
                plans.append(self._result(job, farm, generated_at))
        finally:
            for job in jobs:
                job.cancel()
        return plans[0].model_copy(
            update={"sections": [section for plan in plans for section in plan.sections]}
        )

    def _submit(self, slot: int, farm: FarmInput, generated_at: datetime) -> Future[FarmPlan]:
        payload = farm.model_dump(mode="json", by_alias=True)
        try:
            return self._slots[slot].submit(_plan_in_worker, payload, generated_at)
        except BrokenProcessPool:  # the worker died during an earlier request: a new one
            self._slots[slot] = self._new_slot()
            return self._slots[slot].submit(_plan_in_worker, payload, generated_at)

    def _result(self, job: Future[FarmPlan], farm: FarmInput, generated_at: datetime) -> FarmPlan:
        try:
            return job.result()
        except BrokenProcessPool:  # the worker died: its section is planned here instead
            return self._local.plan_farm(farm, generated_at)

    def close(self) -> None:
        """Stops the worker processes (when the server stops)."""
        for slot in self._slots:
            slot.shutdown(wait=False, cancel_futures=True)
