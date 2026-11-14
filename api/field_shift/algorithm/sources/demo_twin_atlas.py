"""A FICTITIOUS grid of observed climates around the farm (2011–2024), so that the real twin
search (step 4) runs in the demo.

Real cells would come from NASA POWER for every cultivated 0.5° cell of eastern North America,
computed once offline. Each fictitious cell starts from the farm's own observed indicators, moved
by typical gradients of eastern North America (colder and shorter seasons northward, wetter
eastward), plus a local offset and a small yearly noise. A cycle warmer than today therefore
finds its twins south of the farm, farther when it is warmer.
"""

from __future__ import annotations

from typing import Final

import numpy as np

from field_shift.algorithm.climate.indicator_table import IndicatorTable
from field_shift.algorithm.config.climate import TWIN_PERIOD, YearRange
from field_shift.algorithm.twins.climate_twin_finder import GridCell
from field_shift.algorithm.weather.daily_weather import DailyWeather

#: Grid step and extent around the farm, in degrees.
STEP_DEG: Final = 0.5
LATITUDE_SPAN_DEG: Final = 6
LONGITUDE_SPAN_DEG: Final = 8
#: Change of each indicator per degree north and per degree east (fictitious, plausible), in the
#: order of INDICATORS: degree-days, summer rain, frost-free days, hot days, January minimum.
PER_DEGREE_NORTH: Final = np.array([-100, -4, -6, -2.5, -1.3])
PER_DEGREE_EAST: Final = np.array([-8, 6, 0.5, -0.4, 0.3])
#: Local climate of a cell (hills, lakes…): a fixed offset per indicator, with this deviation.
CELL_OFFSET_SD: Final = np.array([40, 20, 4, 1.5, 0.6])
#: Small year-to-year noise of a cell, so that no two cells are exactly alike.
YEAR_NOISE_SD: Final = np.array([10, 5, 1, 0.5, 0.2])
#: Indicators that cannot be negative: degree-days, rain, frost-free days, hot days.
NON_NEGATIVE: Final = np.array([True, True, True, True, False])
SEED: Final = 2011


def demo_twin_atlas(
    farm_lat: float,
    farm_lon: float,
    farm_weather: DailyWeather,
    period: YearRange = TWIN_PERIOD,
) -> list[GridCell]:
    """The cells of the fictitious grid, with their observed climate over `period`."""
    rng = np.random.default_rng(SEED)
    observed = IndicatorTable.from_weather(farm_weather).between(period.first, period.last)
    lat_steps = round(LATITUDE_SPAN_DEG / STEP_DEG)
    lon_steps = round(LONGITUDE_SPAN_DEG / STEP_DEG)
    north_index = np.arange(-lat_steps, lat_steps + 1)
    east_index = np.arange(-lon_steps, lon_steps + 1)
    north = np.repeat(north_index, len(east_index)) * STEP_DEG
    east = np.tile(east_index, len(north_index)) * STEP_DEG
    n_cells = len(north)

    rows = (
        observed.rows[:, None, :]
        + PER_DEGREE_NORTH * north[None, :, None]
        + PER_DEGREE_EAST * east[None, :, None]
        + rng.normal(0, CELL_OFFSET_SD, (n_cells, len(CELL_OFFSET_SD)))[None, :, :]
        + rng.normal(0, YEAR_NOISE_SD, (len(observed.rows), n_cells, len(YEAR_NOISE_SD)))
    )
    rows = np.where(NON_NEGATIVE, np.maximum(rows, 0.0), rows)

    cell_ids = [f"{i}:{j}" for i in north_index for j in east_index]
    return [
        GridCell(
            id=cell_ids[c],
            lat=farm_lat + float(north[c]),
            lon=farm_lon + float(east[c]),
            cultivated=True,
            indicators=IndicatorTable(observed.years, rows[:, c, :]),
        )
        for c in range(n_cells)
    ]
