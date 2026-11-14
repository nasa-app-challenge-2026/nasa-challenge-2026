"""What the farmer chooses before the algorithm runs (step 1 of field_shift.py v5.1).

The cycle, how often a crop is harvested, the horizon, the criteria he ranks, the reserve mode.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

MONTHS_PER_YEAR: Final = 12
#: Absolute times count months since January of this year (see `algorithm/timeline`).
EPOCH_YEAR: Final = 2000

#: A rotation cycle lasts from 2 to 6 years.
MIN_CYCLE_YEARS: Final = 2
MAX_CYCLE_YEARS: Final = 6

#: Last year covered by the climate projections: horizons stop there.
LAST_PROJECTION_YEAR: Final = 2060

#: Fewest years of history asked to the farmer.
MIN_HISTORY_YEARS: Final = 3

#: An unranked criterion keeps this share of the smallest weight.
UNRANKED_WEIGHT_SHARE: Final = 0.25


@dataclass(frozen=True)
class Frequency:
    """How often a crop is harvested. `position_start_month` = month (0-based) where the
    positions of the cycle start: January with one crop a year, February otherwise."""

    months: int
    label: str
    position_start_month: int


FREQUENCIES: Final[tuple[Frequency, ...]] = (
    Frequency(12, "1 culture par an", 0),
    Frequency(6, "2 cultures par an (été et hiver)", 1),
    Frequency(4, "3 cultures par an (cultures courtes, rare au Québec)", 1),
)


class ReserveMode(StrEnum):
    """What the seed reserve means for the proposals."""

    PREFERRED = "preferer"
    ONLY = "uniquement"
