"""Step 3, case 2 (a cycle that ends later): the delta method.

For each month, a climate model gives the change between its simulation of 1985–2014 and the
future window (+2.5 °C in July, −8 % of rain…). That change is applied to the real NASA POWER
weather of 1985–2014: temperatures are shifted, rain is multiplied by a bounded ratio. A model
that sees the farm 1 °C too warm in the past and in the future has its error cancelled.
"""

from __future__ import annotations

import numpy as np

from field_shift.algorithm.config.climate import MAX_RAIN_RATIO, MIN_RAIN_RATIO
from field_shift.algorithm.config.timing import MONTHS_PER_YEAR
from field_shift.algorithm.weather.daily_weather import DailyWeather


def monthly_means(weather: DailyWeather, values: np.ndarray) -> np.ndarray:
    """Mean of `values` (one per day) for each month of the year, January first."""
    sums = np.bincount(weather.month, weights=values, minlength=MONTHS_PER_YEAR + 1)[1:]
    counts = np.bincount(weather.month, minlength=MONTHS_PER_YEAR + 1)[1:]
    return sums / counts


def _monthly_change(
    observed: DailyWeather, historical: DailyWeather, future: DailyWeather, column: str
):
    """The model's change per month, repeated for every day of the observed series."""
    change = monthly_means(future, getattr(future, column)) - monthly_means(
        historical, getattr(historical, column)
    )
    return change[observed.month - 1]


def apply_deltas(
    observed: DailyWeather, historical: DailyWeather, future: DailyWeather
) -> DailyWeather:
    """The observed weather (1985–2014) moved to the future window of a model.

    historical  the model on 1985–2014;  future  the model on the future window.
    """
    rain_ratio = np.clip(
        monthly_means(future, future.rain) / monthly_means(historical, historical.rain),
        MIN_RAIN_RATIO,
        MAX_RAIN_RATIO,
    )
    return observed.with_values(
        tmax=observed.tmax + _monthly_change(observed, historical, future, "tmax"),
        tmin=observed.tmin + _monthly_change(observed, historical, future, "tmin"),
        rain=observed.rain * rain_ratio[observed.month - 1],
    )
