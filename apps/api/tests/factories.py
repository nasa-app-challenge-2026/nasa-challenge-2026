"""Synthetic climate years with exactly known values."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

from fieldshift.domain.climate.series import ClimateSeries, DailyRecord, YearData

Profile = Callable[[date], tuple[float, float, float]]
"""Returns (t_max, t_min, precipitation) for a day."""


def year_records(year: int, profile: Profile) -> list[DailyRecord]:
    day, records = date(year, 1, 1), []
    while day.year == year:
        t_max, t_min, rain = profile(day)
        records.append(DailyRecord(day, (t_max + t_min) / 2, t_max, t_min, rain))
        day += timedelta(days=1)
    return records


def make_year(year: int, profile: Profile) -> YearData:
    return ClimateSeries(year_records(year, profile)).complete_years()[0]


def seasonal(day: date) -> tuple[float, float, float]:
    """Cold until 30 April, warm from 1 May to 30 September, cold afterwards."""
    if date(day.year, 5, 1) <= day <= date(day.year, 9, 30):
        return 25.0, 12.0, 0.0
    return -5.0, -15.0, 2.0
