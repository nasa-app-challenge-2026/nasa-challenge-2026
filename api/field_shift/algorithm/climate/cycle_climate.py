"""The climate calendar of one cycle (output of step 3, used by step 9b).

Heat of each month, mean dates of the last spring frost and the first fall frost, mean January
minimum, and how much earlier the fixed-date harvests come.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum

from field_shift.algorithm.config.timing import (
    DEGREE_DAY_DAYS_PER_MONTH,
    MATURITY_STEP_MONTHS,
    MAX_MATURITY_MONTHS,
    MONTHS_PER_YEAR,
)


class ClimateMethod(StrEnum):
    """How the target climate of a cycle was built."""

    TREND = "tendance"
    MODELS = "modeles"


@dataclass
class CycleClimate:
    """Climate of a cycle.

    degree_days_per_day   12 values: mean degree-days per day of each month
    last_spring_frost     mean last spring frost (0-based month: 4.15 = ~5 May); None = no frost
    first_fall_frost      mean first fall frost, None = no frost
    harvest_advance_months fixed-date harvests come this much earlier (warming)
    warming_c             temperature shift compared with 2005–2024
    summer_rain_change_pct June–August rain compared with 2005–2024
    source                readable source ("tendance NASA POWER"…)
    models                the climate models averaged (case 2)
    """

    degree_days_per_day: tuple[float, ...]
    last_spring_frost: float | None
    first_fall_frost: float | None
    january_minimum_c: float
    harvest_advance_months: float
    method: ClimateMethod
    source: str
    warming_c: float = 0.0
    summer_rain_change_pct: float = 0.0
    models: tuple[str, ...] = ()
    _maturity_offsets: dict[tuple[float, float], float | None] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )

    def maturity(self, sowing: float, degree_days: float) -> float | None:
        """When a crop sown at `sowing` (absolute month) has received `degree_days`, or None if
        it never does within a year. Computed from the month of the year it is sown, so the
        result does not depend on the year."""
        start = sowing % MONTHS_PER_YEAR
        key = (start, degree_days)
        if key not in self._maturity_offsets:
            self._maturity_offsets[key] = self._maturity_offset(start, degree_days)
        offset = self._maturity_offsets[key]
        return None if offset is None else sowing + offset

    def _maturity_offset(self, start: float, degree_days: float) -> float | None:
        received = 0.0
        t = start
        while received < degree_days:
            month = math.floor(t) % MONTHS_PER_YEAR
            received += (
                self.degree_days_per_day[month] * DEGREE_DAY_DAYS_PER_MONTH * MATURITY_STEP_MONTHS
            )
            t += MATURITY_STEP_MONTHS
            if t - start > MAX_MATURITY_MONTHS:
                return None
        return t - start
