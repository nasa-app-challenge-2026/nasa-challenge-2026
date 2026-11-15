"""FICTITIOUS NASA POWER series (1985–2024), used when the real API cannot be reached (offline,
tests).

Same recipe, same random numbers as field_shift.py (`meteo_power_fictive`), so the plans of the
demo are those of the algorithm document: Montérégie monthly temperatures, a warming trend, a
deviation per year, warm and cold spells of a few days, random rain.
"""

from __future__ import annotations

import math
from typing import Final

import numpy as np

from field_shift.algorithm.config.climate import FARM_WEATHER_YEARS, YearRange
from field_shift.algorithm.weather.daily_weather import DailyWeather

#: Fictitious mean monthly temperatures of 2005–2024 in Montérégie (°C).
MONTHLY_MEAN_C: Final = [-10, -8, -2, 6.5, 13.5, 19, 21.5, 20.5, 15.5, 8.5, 2, -6]
#: Day of the year in the middle of each month.
MID_MONTH_DAY: Final = np.array([15, 46, 74, 105, 135, 166, 196, 227, 258, 288, 319, 349])
DAYS_PER_YEAR: Final = 365
OFFSET_C: Final = 0.5
TREND_C_PER_YEAR: Final = 0.04
TREND_CENTRE_YEAR: Final = 2014.5
YEAR_DEVIATION_SD: Final = 0.8
#: Warm and cold spells last a few days: each day keeps 70 % of the previous deviation.
SPELL_PERSISTENCE: Final = 0.7
SPELL_SD: Final = 3.5
#: tmax and tmin are this far above and below the daily mean.
DAILY_HALF_RANGE_C: Final = 6.0
RAIN_SHAPE: Final = 0.6
RAIN_SCALE_MM: Final = 4.7
SEED: Final = 1


def demo_farm_weather(
    years: YearRange = FARM_WEATHER_YEARS, trend: float = TREND_C_PER_YEAR, seed: int = SEED
) -> DailyWeather:
    """The fictitious weather of the farm (daily, over `years`). Always the same for a seed."""
    rng = np.random.default_rng(seed)
    calendar = DailyWeather.calendar_columns(years.first, years.last)
    n_days = len(calendar["year"])
    seasonal = np.interp(
        calendar["day_of_year"],
        np.r_[MID_MONTH_DAY - DAYS_PER_YEAR, MID_MONTH_DAY, MID_MONTH_DAY + DAYS_PER_YEAR],
        MONTHLY_MEAN_C * 3,
    )
    year_deviation = dict(
        zip(
            range(years.first, years.last + 1),
            rng.normal(0, YEAR_DEVIATION_SD, years.last - years.first + 1),
            strict=True,
        )
    )
    shocks = rng.normal(0, SPELL_SD * math.sqrt(1 - SPELL_PERSISTENCE**2), n_days)
    spell = np.zeros(n_days)
    for day in range(1, n_days):
        spell[day] = SPELL_PERSISTENCE * spell[day - 1] + shocks[day]
    mean = (
        seasonal
        + OFFSET_C
        + trend * (calendar["year"] - TREND_CENTRE_YEAR)
        + np.array([year_deviation[int(y)] for y in calendar["year"]])
        + spell
    )
    return DailyWeather(
        **calendar,
        tmax=mean + DAILY_HALF_RANGE_C,
        tmin=mean - DAILY_HALF_RANGE_C,
        rain=rng.gamma(RAIN_SHAPE, RAIN_SCALE_MM, n_days),
    )
