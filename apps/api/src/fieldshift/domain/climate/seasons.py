"""Frost dates and season boundaries within one calendar year (northern hemisphere).

The functions work on day-of-year indices (0 = 1 January) of a complete ``YearData``.
Southern-hemisphere seasons, which straddle two calendar years, are not handled: the
application rejects such locations instead of producing misleading numbers.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import median

from fieldshift.domain.climate.formulas import daily_mean_from_extremes
from fieldshift.domain.climate.series import YearData

# --- Documented thresholds ---------------------------------------------------


@dataclass(frozen=True, slots=True)
class FrostThreshold:
    """A frost definition: daily minimum below (or at) a temperature."""

    temperature_c: float
    inclusive: bool
    """True: ``Tmin <= temperature``. False: ``Tmin < temperature``."""

    def is_reached(self, t_min_c: float) -> bool:
        if self.inclusive:
            return t_min_c <= self.temperature_c
        return t_min_c < self.temperature_c


FROST = FrostThreshold(temperature_c=0.0, inclusive=False)
"""Frost day: ``Tmin < 0 °C`` (ETCCDI index FD; last spring frost in bourgeois_2012)."""

KILLING_FROST = FrostThreshold(temperature_c=-2.0, inclusive=True)
"""Killing frost: ``Tmin <= -2 °C``, the event that ends heat accumulation for
warm-season crops (source: bourgeois_2012, omafra_93_119)."""

FROST_SEASON_PIVOT = (7, 15)
"""Frosts before 15 July count as spring frosts, from 15 July on as fall frosts.
Project convention: no source prescribes the split; mid-July is the warmest part of the
year at the latitudes targeted, so the choice has no effect unless frost occurs in July."""

GROWING_SEASON_THRESHOLD_C = 5.0
GROWING_SEASON_SPAN_DAYS = 6
GROWING_SEASON_SECOND_HALF = (7, 1)
"""ETCCDI growing season length (GSL): from the first span of at least 6 days with a daily
mean above 5 °C to the first span, after 1 July, of 6 days with a daily mean below 5 °C
(source: etccdi_indices)."""

CHU_START_MEAN_C = 12.8
CHU_START_MOVING_MEAN_DAYS = 5
CHU_REFERENCE_YEARS = 30
"""Québec method for the start of crop heat unit accumulation: first date, on or after the
median date of the last spring frost over 30 years, where the 5-day moving mean of the
daily mean temperature reaches 12.8 °C (source: bourgeois_2012)."""


@dataclass(frozen=True, slots=True)
class Season:
    """A run of consecutive days: ``start_index`` included, ``end_index`` excluded."""

    start_index: int
    end_index: int

    def __post_init__(self) -> None:
        if self.end_index <= self.start_index:
            raise ValueError("a season must contain at least one day")

    @property
    def length_days(self) -> int:
        return self.end_index - self.start_index

    @property
    def last_index(self) -> int:
        return self.end_index - 1


# --- Frost dates -------------------------------------------------------------


def last_spring_frost_index(year: YearData, threshold: FrostThreshold = FROST) -> int | None:
    """Index of the last day before the pivot date with a frost, or ``None`` if there is none."""
    pivot = year.index_of(*FROST_SEASON_PIVOT)
    for index in range(pivot - 1, -1, -1):
        if threshold.is_reached(year.t_min_c[index]):
            return index
    return None


def first_fall_frost_index(year: YearData, threshold: FrostThreshold = FROST) -> int | None:
    """Index of the first day on or after the pivot date with a frost, or ``None``."""
    pivot = year.index_of(*FROST_SEASON_PIVOT)
    for index in range(pivot, len(year)):
        if threshold.is_reached(year.t_min_c[index]):
            return index
    return None


def frost_free_season(year: YearData, threshold: FrostThreshold = FROST) -> Season | None:
    """Days strictly between the last spring frost and the first fall frost.

    ``None`` when either frost is absent from the calendar year: the season is then not
    bounded inside the year and its length cannot be stated.
    """
    last_spring = last_spring_frost_index(year, threshold)
    first_fall = first_fall_frost_index(year, threshold)
    if last_spring is None or first_fall is None or first_fall - last_spring < 2:
        return None
    return Season(start_index=last_spring + 1, end_index=first_fall)


# --- Thermal growing season (ETCCDI GSL) -------------------------------------


def _first_span(flags: Sequence[bool], start: int, stop: int, span: int) -> int | None:
    """First index in ``[start, stop - span]`` opening ``span`` consecutive true flags
    that all lie before ``stop``."""
    run = 0
    for index in range(start, stop):
        run = run + 1 if flags[index] else 0
        if run >= span:
            return index - span + 1
    return None


def thermal_growing_season(year: YearData) -> Season | None:
    """Growing season as defined by the ETCCDI index GSL.

    Start: first day of the first span of 6 days with a daily mean above 5 °C, the whole span
    falling before 1 July. End: first day of the first span of 6 days with a daily mean
    below 5 °C starting on or after 1 July; 31 December if there is none. ``None`` when the
    season never starts.
    """
    means = [
        daily_mean_from_extremes(t_max, t_min)
        for t_max, t_min in zip(year.t_max_c, year.t_min_c, strict=True)
    ]
    second_half = year.index_of(*GROWING_SEASON_SECOND_HALF)
    warm = [mean > GROWING_SEASON_THRESHOLD_C for mean in means]
    cold = [mean < GROWING_SEASON_THRESHOLD_C for mean in means]

    start = _first_span(warm, 0, second_half, GROWING_SEASON_SPAN_DAYS)
    if start is None:
        return None
    end = _first_span(cold, second_half, len(year), GROWING_SEASON_SPAN_DAYS)
    return Season(start_index=start, end_index=end if end is not None else len(year))


# --- Crop heat unit season (Québec method) -----------------------------------


def median_last_spring_frost_index(years: Sequence[YearData]) -> int:
    """Median day-of-year index of the last spring frost over the most recent 30 years.

    Years without any spring frost are ignored; if no year has one (frost-free climate) the
    search for the start of the heat-unit season begins on 1 January. A median falling
    between two days is rounded up: a later start accumulates less heat, the cautious side.
    """
    reference = years[-CHU_REFERENCE_YEARS:]
    indices = [
        index for year in reference if (index := last_spring_frost_index(year, FROST)) is not None
    ]
    if not indices:
        return 0
    return math.ceil(median(indices))


def crop_heat_unit_season(year: YearData, search_start_index: int) -> Season | None:
    """Period over which crop heat units accumulate, Québec method (source: bourgeois_2012).

    Start: first day on or after ``search_start_index`` where the mean of the daily mean
    temperature over that day and the four before reaches 12.8 °C. End: first day on or after
    15 July with a minimum of -2 °C or less (that day excluded); 31 December if there is
    none. ``None`` when the start is never reached before the end.
    """
    means = [
        daily_mean_from_extremes(t_max, t_min)
        for t_max, t_min in zip(year.t_max_c, year.t_min_c, strict=True)
    ]
    killing_frost = first_fall_frost_index(year, KILLING_FROST)
    end = killing_frost if killing_frost is not None else len(year)

    window = CHU_START_MOVING_MEAN_DAYS
    first_candidate = max(search_start_index, window - 1)
    for index in range(first_candidate, end):
        moving_mean = sum(means[index - window + 1 : index + 1]) / window
        if moving_mean >= CHU_START_MEAN_C:
            return Season(start_index=index, end_index=end)
    return None
