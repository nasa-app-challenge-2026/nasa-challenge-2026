"""Everything step 9b needs to know about one cycle of one field.

The time layout, where the field starts (last harvest, last sold crop, history), the climate of the
cycle, the twin evidence, the weights and the farmer's constraints.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from functools import cached_property

from field_shift.algorithm.climate.cycle_climate import CycleClimate
from field_shift.algorithm.config.timing import MONTHS_PER_YEAR
from field_shift.algorithm.delays.occupation import Occupation
from field_shift.algorithm.delays.return_delay_catalog import (
    DEFAULT_DELAY_CATALOG,
    ReturnDelayCatalog,
)
from field_shift.algorithm.delays.return_delay_checker import ReturnDelayChecker
from field_shift.algorithm.planning.time_settings import TimeSettings
from field_shift.algorithm.twins.twin_evidence import TwinEvidence
from field_shift.reference.crops import SHEETS


@dataclass(frozen=True, eq=False)
class CycleContext:
    """One cycle of one field.

    first_position   absolute index of the cycle's first position
    entry_harvest    when the field becomes free (absolute month)
    entry_sheet_id   last sold sheet before the cycle
    weights          criteria weights for this cycle
    reserve          seeds owned (counted in the 1st cycle only), else None
    history          what grew before the cycle
    diseases         declared soil diseases
    candidates       sheets that may fill a position
    covers_enabled   rye is sown automatically between two crops
    """

    time: TimeSettings
    first_position: int
    entry_harvest: float
    entry_sheet_id: str | None
    climate: CycleClimate
    evidence: TwinEvidence
    weights: Mapping[str, float]
    reserve: frozenset[str] | None
    history: Sequence[Occupation]
    diseases: tuple[str, ...]
    candidates: tuple[str, ...]
    covers_enabled: bool
    catalog: ReturnDelayCatalog = DEFAULT_DELAY_CATALOG

    def with_changes(self, **changes) -> CycleContext:
        """The same context with some fields changed."""
        return replace(self, **changes)

    @property
    def positions(self) -> int:
        return self.time.positions_per_cycle

    @property
    def cycle_months(self) -> int:
        return self.time.cycle_years * MONTHS_PER_YEAR

    @property
    def entry_crop_id(self) -> str | None:
        """The crop (not the sheet) in place before the cycle."""
        return SHEETS[self.entry_sheet_id].crop_id if self.entry_sheet_id else None

    @cached_property
    def delays(self) -> ReturnDelayChecker:
        return ReturnDelayChecker(
            cycle_years=self.time.cycle_years,
            history=self.history,
            diseases=self.diseases,
            catalog=self.catalog,
        )
