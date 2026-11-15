"""Steps 3 to 7 for one cycle: the target climate of the farm (step 3), its twins (step 4), then
what the twins grow and how well (steps 5 to 7). The water model is put on the daily weather of
the cycle (one weather per climate model).

The planner only sees `cycle_data(first_year, last_year)`; where the data come from (real or the
references of the tests) is decided when the provider is built.

The climate, the twins and the water of a cycle are the same for every field of the place: they
are computed once. The evidence of the twins depends on the soil of the field too (step 5 keeps the
twin fields of a comparable soil): it is computed once per cycle and soil.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from field_shift.algorithm.climate.target_climate_projector import (
    ProjectedClimate,
    TargetClimateProjector,
)
from field_shift.algorithm.planning.cycle_plan import CycleData
from field_shift.algorithm.twins.climate_twin_finder import ClimateTwinFinder, Twin
from field_shift.algorithm.twins.soil_comparison import Soil
from field_shift.algorithm.twins.twin_evidence import TwinEvidence
from field_shift.algorithm.water.water_model import CycleWater, WaterModel

#: Steps 5 to 7: the evidence of a cycle from its twins, for the soil of a field (None: the soil
#: is not known, no soil filter).
EvidenceFor = Callable[[int, int, Sequence[Twin], Soil | None], TwinEvidence]


@dataclass(frozen=True)
class _CycleBase:
    """What a cycle is for every field of the place."""

    projected: ProjectedClimate
    twins: list[Twin]
    water: CycleWater


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
        self._bases: dict[tuple[int, int], _CycleBase] = {}
        self._evidence: dict[tuple[int, int, Soil | None], TwinEvidence] = {}

    def _base(self, first_year: int, last_year: int) -> _CycleBase:
        key = (first_year, last_year)
        if key not in self._bases:
            projected = self._projector.project(first_year, last_year)
            self._bases[key] = _CycleBase(
                projected=projected,
                twins=self._twin_finder.twins_of(projected.targets),
                water=self._water.for_cycle(projected.weathers),
            )
        return self._bases[key]

    def cycle_data(self, first_year: int, last_year: int, soil: Soil | None = None) -> CycleData:
        base = self._base(first_year, last_year)
        key = (first_year, last_year, soil)
        if key not in self._evidence:
            self._evidence[key] = self._evidence_for(first_year, last_year, base.twins, soil)
        return CycleData(
            climate=base.projected.climate, evidence=self._evidence[key], water=base.water
        )

    def for_soil(self, soil: Soil | None) -> SoilCycleData:
        """The cycles of a field of this soil."""
        return SoilCycleData(self, soil)


class SoilCycleData:
    """The cycle data of one field: the place's, with the evidence of its soil."""

    def __init__(self, provider: CycleDataProvider, soil: Soil | None) -> None:
        self._provider = provider
        self._soil = soil

    def cycle_data(self, first_year: int, last_year: int) -> CycleData:
        return self._provider.cycle_data(first_year, last_year, self._soil)
