"""Step 3, case 1 (a cycle that ends within 10 years): the trend of the last 40 years of NASA POWER.

No climate model. The warming is the slope of the yearly mean temperature (e.g. 0.03 °C a year).
The 20 most recent years are shifted by that trend up to the middle of the cycle: each year keeps
its real late frosts and heat waves. Rain is not shifted: it varies too much from year to year to
extend a trend.
"""

from __future__ import annotations

import numpy as np

from field_shift.algorithm.config.climate import RECENT_WINDOW, YearRange
from field_shift.algorithm.weather.daily_weather import DailyWeather

_LINE_DEGREE = 1


class TemperatureTrend:
    """The warming of a farm, measured on its NASA POWER weather (about 40 years)."""

    def __init__(self, weather: DailyWeather) -> None:
        years, means = [], []
        for year, days in weather.year_slices():
            years.append(year)
            means.append(weather.daily_mean[days].mean())
        self.weather = weather
        #: Warming in °C per year.
        self.slope_per_year = float(np.polyfit(years, means, _LINE_DEGREE)[0])

    def extend_to(
        self, target_year: float, window: YearRange = RECENT_WINDOW
    ) -> tuple[DailyWeather, float]:
        """The recent years, as if they happened around `target_year`: (weather, shift in °C)."""
        middle = (window.first + window.last) / 2
        shift_c = self.slope_per_year * (target_year - middle)
        recent = self.weather.between(window.first, window.last)
        return recent.shifted_by(shift_c), shift_c
