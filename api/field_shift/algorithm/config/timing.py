"""Time constants of the chain building (step 9b).

Times are absolute months since January of EPOCH_YEAR, as decimals (see `timeline`).
"""

from __future__ import annotations

from typing import Final

from field_shift.reference.planning import EPOCH_YEAR, MONTHS_PER_YEAR

__all__ = [
    "COVER_ATTACH_EPSILON",
    "DAYS_PER_MONTH",
    "DEGREE_DAY_DAYS_PER_MONTH",
    "DOUBLE_CROP_MAX_DELAY_MONTHS",
    "EPOCH_YEAR",
    "MATURITY_STEP_MONTHS",
    "MAX_MATURITY_MONTHS",
    "MONTHS_PER_YEAR",
    "SOWING_DELAY_MONTHS",
    "SOWING_STEP_MONTHS",
    "SOWING_YEARS_TRIED",
    "TIME_EPSILON",
]

#: About one week between a harvest and the next sowing.
SOWING_DELAY_MONTHS: Final = 0.25
#: Step used to try later sowing dates inside a sowing window.
SOWING_STEP_MONTHS: Final = 0.25
#: Step of the degree-day accumulation from sowing to maturity.
MATURITY_STEP_MONTHS: Final = 0.05
#: A summer crop that is not mature after this many months never is.
MAX_MATURITY_MONTHS: Final = 12
#: Days per month in the degree-day accumulation (field_shift.py).
DEGREE_DAY_DAYS_PER_MONTH: Final = 30.4
#: Days per month when a day of the year becomes a decimal month.
DAYS_PER_MONTH: Final = 30.44
#: A double crop is sown at most this long after the harvest it follows.
DOUBLE_CROP_MAX_DELAY_MONTHS: Final = 1
#: Sowing years tried after a harvest, starting the year before it.
SOWING_YEARS_TRIED: Final = 5
#: Rounding guard when comparing decimal months.
TIME_EPSILON: Final = 1e-9
#: Rounding guard when a cover crop is attached to the crop harvested before it.
COVER_ATTACH_EPSILON: Final = 1e-6
