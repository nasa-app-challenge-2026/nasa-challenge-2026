"""Times of the chain building: absolute months since January of EPOCH_YEAR, as decimals.

321.6 = (2026 − 2000) × 12 + 9.6 = about 19 October 2026. Months inside a year are 0-based
(0 = January), as in field_shift.py.
"""

from __future__ import annotations

import calendar
import math
from dataclasses import dataclass
from datetime import date

from field_shift.algorithm.config.timing import (
    DAYS_PER_MONTH,
    EPOCH_YEAR,
    MONTHS_PER_YEAR,
    TIME_EPSILON,
)

#: A year that is not a leap year, to read "a month of any year" as a day.
_COMMON_YEAR = 2001
#: A month given without a day ("2026-10") is read as its middle.
_MIDDLE_OF_MONTH = 0.5


@dataclass(frozen=True)
class MonthDay:
    """A day of the year without its year: month 1 to 12, day 1 to 31."""

    month: int
    day: int


def of(year: int, month: float) -> float:
    """Absolute time of month `month` (0-based decimal) of `year`."""
    return (year - EPOCH_YEAR) * MONTHS_PER_YEAR + month


def of_date(day: date) -> float:
    """Absolute time of a calendar date (the day is a fraction of its month)."""
    days_in_month = calendar.monthrange(day.year, day.month)[1]
    return of(day.year, day.month - 1 + (day.day - 1) / days_in_month)


def of_year_month(year: int, month: int) -> float:
    """Absolute time of the middle of a month (month 1 to 12): a harvest "in October"."""
    return of(year, month - 1 + _MIDDLE_OF_MONTH)


def year_of(time: float) -> int:
    return EPOCH_YEAR + math.floor(time / MONTHS_PER_YEAR)


def month_of_year(time: float) -> float:
    """Month of the year (0-based decimal) of an absolute time."""
    return time % MONTHS_PER_YEAR


def to_date(time: float) -> date:
    """Calendar date of an absolute time."""
    whole = math.floor(time + TIME_EPSILON)
    year = EPOCH_YEAR + whole // MONTHS_PER_YEAR
    month = whole % MONTHS_PER_YEAR
    return date(year, month + 1, _day_in_month(time - whole, year, month))


def month_day(month_in_year: float) -> MonthDay:
    """A month of the year (decimal, 0-based) as a day: 3.75 → 24 April."""
    month = math.floor(month_in_year)
    return MonthDay(month + 1, _day_in_month(month_in_year - month, _COMMON_YEAR, month))


def _day_in_month(fraction: float, year: int, month: int) -> int:
    days_in_month = calendar.monthrange(year, month + 1)[1]
    return max(1, min(days_in_month, math.floor(fraction * DAYS_PER_MONTH) + 1))
