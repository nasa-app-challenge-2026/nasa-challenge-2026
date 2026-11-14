"""Steps 3 to 7 for one cycle: the target climate of the farm (step 3), its twins (step 4), then
what the twins grow and how well (steps 5 to 7). The water model is put on the daily weather of
the cycle (one weather per climate model).

The planner only sees `cycle_data(first_year, last_year)`; where the data come from (real or demo)
is decided when the provider is built.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from field_shift.algorithm.climate.target_climate_projector import TargetClimateProjector
from field_shift.algorithm.planning.cycle_plan import CycleData
from field_shift.algorithm.twins.climate_twin_finder import ClimateTwinFinder, Twin
from field_shift.algorithm.twins.twin_evidence import TwinEvidence
from field_shift.algorithm.water.water_model import WaterModel

#: Steps 5 to 7: the evidence of a cycle from its twins (soil filter, crop maps, greenness).
EvidenceFor = Callable[[int, int, Sequence[Twin]], TwinEvidence]


class CycleDataProvider:
    """Gives the planner the climate and the twin evidence of any cycle (computed once)."""

    def __init__(
        self,
        projector: TargetClimateProjector,
        twin_finder: ClimateTwinFinder,
        evidence_for: EvidenceFor,
        water: WaterModel,
    ) -> None:
        self._projector = projector
        self._twin_finder = twin_finder
        self._evidence_for = evidence_for
        self._water = water
        self._cache: dict[tuple[int, int], CycleData] = {}

    def cycle_data(self, first_year: int, last_year: int) -> CycleData:
        key = (first_year, last_year)
        if key not in self._cache:
            projected = self._projector.project(first_year, last_year)
            twins = self._twin_finder.twins_of(projected.targets)
            self._cache[key] = CycleData(
                climate=projected.climate,
                evidence=self._evidence_for(first_year, last_year, twins),
                water=self._water.for_cycle(projected.weathers),
            )
        return self._cache[key]
