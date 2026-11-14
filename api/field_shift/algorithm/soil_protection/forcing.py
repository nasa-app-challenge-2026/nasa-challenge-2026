"""Statistics the forcing variables of a section are made of, from the series the data sources
give (step 3 and step 4 of the pipeline):

    storm intensity   mean of the annual maxima of the hourly rain (NASA POWER, MERRA-2)
    growing season    the months the NDVI, the ET / PET ratio and the soil moisture are averaged on
    ET / PET          actual over potential evapotranspiration of the season (MODIS MOD16A2)

The hourly rain of MERRA-2 is a mean over a cell of about 50 × 60 km: it smooths the local
downpours, so the storm intensity is lower than what a rain gauge on the field would record. It
ranks rotations on the same field consistently; a measured intensity can be given in the request.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from field_shift.algorithm.config.soil_protection import (
    GROWING_SEASON_NORTH,
    GROWING_SEASON_SOUTH,
    MIN_STORM_YEARS,
    MIN_VALID_HOURS_SHARE,
)

HOURS_PER_YEAR = 8760
MONTHS_PER_YEAR = 12
#: A season is used once this many months have passed since its end (processing of the products).
SEASON_PROCESSING_MONTHS = 1

YearMonth = tuple[int, int]
MONTH_NAMES = ("janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.",
               "nov.", "déc.")  # fmt: skip


class SeriesError(ValueError):
    """A series is too incomplete to give the statistic (message in French)."""


# --- Growing season -------------------------------------------------------------------------------


def growing_season_months(lat: float) -> tuple[int, ...]:
    """The months of the growing season at a latitude (northern or southern hemisphere)."""
    return GROWING_SEASON_NORTH if lat >= 0 else GROWING_SEASON_SOUTH


def _months_between(start: YearMonth, end: YearMonth) -> int:
    return (end[0] - start[0]) * MONTHS_PER_YEAR + end[1] - start[1]


def last_growing_season(lat: float, today: date) -> tuple[YearMonth, ...]:
    """The (year, month) of the most recent growing season over at least one month ago.

    A season across the new year (south: November to March) belongs to the year it ends in.
    """
    months = growing_season_months(lat)
    crosses_year = months[-1] < months[0]
    for end_year in range(today.year, today.year - 3, -1):
        season = tuple(
            (end_year - 1 if crosses_year and month >= months[0] else end_year, month)
            for month in months
        )
        if _months_between(season[-1], (today.year, today.month)) > SEASON_PROCESSING_MONTHS:
            return season
    raise AssertionError("a season ends every year")  # pragma: no cover


def season_label(season: Sequence[YearMonth]) -> str:
    """ "mai–sept. 2026": the months of a season, for the reports."""
    names = MONTH_NAMES
    (first_year, first), (last_year, last) = season[0], season[-1]
    if first_year == last_year:
        return f"{names[first - 1]}–{names[last - 1]} {last_year}"
    return f"{names[first - 1]} {first_year}–{names[last - 1]} {last_year}"


def two_month_windows(season: Sequence[YearMonth]) -> list[tuple[date, date]]:
    """The season cut in windows of at most two months (first day, last day): one request each to
    a service that gives at most 10 composites per request."""
    windows = []
    for i in range(0, len(season), 2):
        first, last = season[i], season[min(i + 1, len(season) - 1)]
        next_year, next_month = (
            (last[0] + 1, 1) if last[1] == MONTHS_PER_YEAR else (last[0], last[1] + 1)
        )
        end = date.fromordinal(date(next_year, next_month, 1).toordinal() - 1)
        windows.append((date(first[0], first[1], 1), end))
    return windows


def mean_over_months(monthly: Mapping[int, float], months: Iterable[int]) -> float:
    """Mean of monthly values (month number → value) over some months."""
    values = [monthly[month] for month in months]
    return sum(values) / len(values)


# --- Storm intensity ------------------------------------------------------------------------------


@dataclass(frozen=True)
class StormIntensity:
    """The storm the infiltration is compared with, and the years it was computed from."""

    intensity_mm_h: float
    years: tuple[int, ...]


def storm_intensity(hourly_rain: Mapping[str, float]) -> StormIntensity:
    """Mean of the annual maxima of the hourly rain (mm/h).

    `hourly_rain` maps "YYYYMMDDHH" to the rain of the hour; negative values (fill values) are
    left out. A year with less than 80 % of valid hours is left out; fewer than 5 years left is an
    error.
    """
    by_year: dict[int, list[float]] = defaultdict(list)
    for stamp, rain in hourly_rain.items():
        if rain >= 0:
            by_year[int(stamp[:4])].append(rain)
    years = sorted(
        year
        for year, values in by_year.items()
        if len(values) >= MIN_VALID_HOURS_SHARE * HOURS_PER_YEAR
    )
    if len(years) < MIN_STORM_YEARS:
        raise SeriesError(
            f"pluie horaire trop incomplète : {len(years)} année(s) complète(s), "
            f"{MIN_STORM_YEARS} au moins"
        )
    maxima = [max(by_year[year]) for year in years]
    return StormIntensity(sum(maxima) / len(maxima), tuple(years))


# --- Evapotranspiration ---------------------------------------------------------------------------


def evapotranspiration_ratio(actual: Mapping[str, float], potential: Mapping[str, float]) -> float:
    """ΣET / ΣPET over the dates where both are known (date → mm): how much of the water the
    vegetation could use it really uses."""
    dates = sorted(set(actual) & set(potential))
    total_potential = sum(potential[d] for d in dates)
    if not dates or total_potential <= 0:
        raise SeriesError("aucune date avec ET et ET potentielle valides dans la saison")
    return sum(actual[d] for d in dates) / total_potential
