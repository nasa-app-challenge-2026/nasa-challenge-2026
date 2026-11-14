"""Step 9b, placement rules: can a sheet fill position p after the previous harvest?

- A crop belongs to the position where it is HARVESTED ("wheat 2028" = sown in 2027, harvested
  in 2028).
- Sowing: inside its window, at least a week after the previous harvest, after the last spring
  frost for a frost-sensitive crop.
- Harvest of a summer crop: when the degree-days since sowing are enough, with the heat of each
  month of the cycle's climate; it must mature before the first fall frost. Winter crops and
  perennials have a fixed harvest date (earlier with warming).
- A crop longer than f months (alfalfa, hay, wheat with f = 6) spans positions.
- Double crop (soybean after wheat): only right after it, at most a month later.
- A winter crop must survive the January minimum of the cycle.
"""

from __future__ import annotations

import math
from typing import NamedTuple

from field_shift.algorithm.climate.cycle_climate import CycleClimate
from field_shift.algorithm.config.timing import (
    DOUBLE_CROP_MAX_DELAY_MONTHS,
    MONTHS_PER_YEAR,
    SOWING_DELAY_MONTHS,
    SOWING_STEP_MONTHS,
    SOWING_YEARS_TRIED,
    TIME_EPSILON,
)
from field_shift.algorithm.planning.time_settings import TimeSettings
from field_shift.reference.crops import FALLOW_SHEET_ID, SHEETS, CropSheet


class Placement(NamedTuple):
    """Where a sheet lands: sowing and harvest (absolute months, sowing None for fallow) and the
    last position it holds (absolute index)."""

    sowing: float | None
    harvest: float
    last_position: int


def place_crop(
    sheet_id: str,
    position: int,
    previous_harvest: float,
    previous_sheet_id: str | None,
    time: TimeSettings,
    climate: CycleClimate,
) -> Placement | None:
    """Try to make `sheet_id` fit at `position` (absolute index) after `previous_harvest`."""
    sheet = SHEETS[sheet_id]
    if sheet_id == FALLOW_SHEET_ID:
        return Placement(None, previous_harvest, position)  # nothing is sown
    if sheet.january_minimum_c is not None and climate.january_minimum_c < sheet.january_minimum_c:
        return None  # does not survive the winter of this climate
    if sheet.only_after and previous_sheet_id not in sheet.only_after:
        return None  # double crop: only after a winter cereal
    assert sheet.sowing_window is not None

    f = time.frequency_months
    anchor = time.position_start_month
    position_start = anchor + position * f
    position_end = anchor + (position + 1) * f
    window_start, window_end = sheet.sowing_window
    first_year = math.floor(previous_harvest / MONTHS_PER_YEAR) - 1
    for year in range(first_year, first_year + SOWING_YEARS_TRIED):
        year_start = year * MONTHS_PER_YEAR
        sowing = max(year_start + window_start, previous_harvest + SOWING_DELAY_MONTHS)
        if sheet.frost_sensitive and climate.last_spring_frost is not None:
            sowing = max(sowing, year_start + climate.last_spring_frost)
        if sheet.is_perennial:
            sowing = max(sowing, position_start)  # 1st year of production = this position
        if sheet.only_after:
            window_end = min(
                window_end, previous_harvest - year_start + DOUBLE_CROP_MAX_DELAY_MONTHS
            )
        while sowing <= year_start + window_end + TIME_EPSILON:
            harvest = _harvest_time(sheet, sowing, year_start, window_start, climate)
            if harvest is None:
                break  # not mature before the frost: try the next year
            within_one_position = not sheet.is_perennial and harvest - sowing <= f
            if harvest >= position_end and within_one_position:
                break  # harvested too late for this position
            if harvest >= position_start:
                last_position = math.floor((harvest - anchor) / f)
                if last_position > position and within_one_position:
                    break
                return Placement(sowing, harvest, last_position)
            sowing += SOWING_STEP_MONTHS  # harvested before the position: sow later
    return None


def _harvest_time(
    sheet: CropSheet,
    sowing: float,
    year_start: float,
    window_start: float,
    climate: CycleClimate,
) -> float | None:
    """Harvest of a sheet sown at `sowing`, or None when a summer crop cannot mature."""
    if sheet.degree_days is not None:
        harvest = climate.maturity(sowing, sheet.degree_days)
        frozen = (
            sheet.frost_sensitive
            and climate.first_fall_frost is not None
            and harvest is not None
            and harvest > year_start + climate.first_fall_frost
        )
        return None if harvest is None or frozen else harvest
    assert sheet.harvest_month is not None
    month = sheet.harvest_month - climate.harvest_advance_months
    harvest = year_start + month + MONTHS_PER_YEAR * (sheet.years_occupied - 1)
    if month < window_start:
        harvest += MONTHS_PER_YEAR  # sown in fall, harvested the next year
    return harvest
