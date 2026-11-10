"""Normalised daily climate data, independent of the provider it came from.

Units are fixed here once and for all: temperatures in degrees Celsius, precipitation in
millimetres per day. A missing value is ``None`` and is never replaced by an estimate.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True, slots=True)
class DailyRecord:
    """One calendar day at one location."""

    day: date
    t_mean_c: float | None
    """24-hour mean air temperature at 2 m (°C)."""
    t_max_c: float | None
    """Daily maximum air temperature at 2 m (°C)."""
    t_min_c: float | None
    """Daily minimum air temperature at 2 m (°C)."""
    precipitation_mm: float | None
    """Daily precipitation total (mm)."""

    @property
    def is_complete(self) -> bool:
        return None not in (self.t_mean_c, self.t_max_c, self.t_min_c, self.precipitation_mm)


@dataclass(frozen=True, slots=True)
class YearData:
    """A complete calendar year as parallel arrays indexed by day of year (0 = 1 January).

    Only built for years without a single missing value, so indicator code never has to
    decide what a gap means.
    """

    year: int
    days: tuple[date, ...]
    t_mean_c: tuple[float, ...]
    t_max_c: tuple[float, ...]
    t_min_c: tuple[float, ...]
    precipitation_mm: tuple[float, ...]

    def __len__(self) -> int:
        return len(self.days)

    def index_of(self, month: int, day: int) -> int:
        """Day-of-year index (0-based) of a calendar date in this year."""
        return (date(self.year, month, day) - date(self.year, 1, 1)).days


@dataclass(frozen=True, slots=True)
class YearCompleteness:
    """How much of a calendar year is usable."""

    year: int
    expected_days: int
    present_days: int
    missing_days: int

    @property
    def is_complete(self) -> bool:
        return self.missing_days == 0 and self.present_days == self.expected_days


def days_in_year(year: int) -> int:
    return (date(year + 1, 1, 1) - date(year, 1, 1)).days


class ClimateSeries:
    """Daily records in strictly ascending order, at most one per calendar day."""

    def __init__(self, records: Sequence[DailyRecord]) -> None:
        for previous, current in itertools.pairwise(records):
            if current.day <= previous.day:
                raise ValueError(
                    f"records must be in strictly ascending date order: "
                    f"{current.day} follows {previous.day}"
                )
        self._records: tuple[DailyRecord, ...] = tuple(records)

    def __len__(self) -> int:
        return len(self._records)

    def __iter__(self) -> Iterator[DailyRecord]:
        return iter(self._records)

    @property
    def records(self) -> tuple[DailyRecord, ...]:
        return self._records

    @property
    def first_day(self) -> date | None:
        return self._records[0].day if self._records else None

    @property
    def last_day(self) -> date | None:
        return self._records[-1].day if self._records else None

    def completeness(self) -> tuple[YearCompleteness, ...]:
        """Per calendar year: days expected, present with all variables, and missing.

        A day absent from the series and a day present with a missing variable are both
        counted as missing.
        """
        complete_days: dict[int, int] = {}
        for record in self._records:
            complete_days.setdefault(record.day.year, 0)
            if record.is_complete:
                complete_days[record.day.year] += 1
        return tuple(
            YearCompleteness(
                year=year,
                expected_days=days_in_year(year),
                present_days=present,
                missing_days=days_in_year(year) - present,
            )
            for year, present in sorted(complete_days.items())
        )

    def complete_years(self) -> tuple[YearData, ...]:
        """Calendar years with every day present and every variable known."""
        by_year: dict[int, list[DailyRecord]] = {}
        for record in self._records:
            by_year.setdefault(record.day.year, []).append(record)

        years: list[YearData] = []
        for year, records in sorted(by_year.items()):
            year_data = _to_year_data(year, records)
            if year_data is not None:
                years.append(year_data)
        return tuple(years)


def _to_year_data(year: int, records: Sequence[DailyRecord]) -> YearData | None:
    if len(records) != days_in_year(year):
        return None
    first = date(year, 1, 1)
    t_mean: list[float] = []
    t_max: list[float] = []
    t_min: list[float] = []
    precipitation: list[float] = []
    for offset, record in enumerate(records):
        if record.day != first + timedelta(days=offset):
            return None
        if (
            record.t_mean_c is None
            or record.t_max_c is None
            or record.t_min_c is None
            or record.precipitation_mm is None
        ):
            return None
        t_mean.append(record.t_mean_c)
        t_max.append(record.t_max_c)
        t_min.append(record.t_min_c)
        precipitation.append(record.precipitation_mm)
    return YearData(
        year=year,
        days=tuple(record.day for record in records),
        t_mean_c=tuple(t_mean),
        t_max_c=tuple(t_max),
        t_min_c=tuple(t_min),
        precipitation_mm=tuple(precipitation),
    )
