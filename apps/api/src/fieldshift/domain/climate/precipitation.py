"""Counting rules on daily precipitation totals.

All functions take the daily series of a year and a half-open index range ``[start, stop)``.
"""

from __future__ import annotations

from collections.abc import Sequence

WET_DAY_THRESHOLD_MM = 1.0
"""A wet day has at least 1 mm of precipitation; a dry day has less (ETCCDI convention for
CDD/CWD, source: etccdi_indices). Gridded products rain a little on many days, so a strict
"0 mm" definition would leave almost no dry day."""

HEAVY_PRECIPITATION_THRESHOLD_MM = 20.0
"""Very heavy precipitation day, ETCCDI index R20mm (source: etccdi_indices)."""


def is_dry_day(precipitation_mm: float) -> bool:
    return precipitation_mm < WET_DAY_THRESHOLD_MM


def total(precipitation_mm: Sequence[float], start: int, stop: int) -> float:
    return sum(precipitation_mm[start:stop])


def count_wet_days(precipitation_mm: Sequence[float], start: int, stop: int) -> int:
    return sum(1 for value in precipitation_mm[start:stop] if not is_dry_day(value))


def count_days_at_or_above(
    precipitation_mm: Sequence[float], start: int, stop: int, threshold_mm: float
) -> int:
    return sum(1 for value in precipitation_mm[start:stop] if value >= threshold_mm)


def longest_dry_spell(precipitation_mm: Sequence[float], start: int, stop: int) -> int:
    """Largest number of consecutive dry days inside the range (ETCCDI CDD, restricted to
    the range instead of the whole year)."""
    longest = 0
    current = 0
    for value in precipitation_mm[start:stop]:
        current = current + 1 if is_dry_day(value) else 0
        longest = max(longest, current)
    return longest


def count_dry_window_starts(
    precipitation_mm: Sequence[float], start: int, stop: int, window_days: int
) -> int:
    """Number of days in ``[start, stop)`` that open ``window_days`` consecutive dry days.

    The window may run past ``stop`` (hay cut on the last day of the period still dries
    afterwards) but never past the end of the series: a window that cannot be observed in
    full is not counted.
    """
    if window_days < 1:
        raise ValueError("window_days must be at least 1")
    count = 0
    for index in range(start, stop):
        window = precipitation_mm[index : index + window_days]
        if len(window) == window_days and all(is_dry_day(value) for value in window):
            count += 1
    return count
