"""Step 2: a climate summed up in 5 numbers per year, the ones that matter for crops.

    djc10            growing degree-days base 10 °C, April to October   enough heat to mature?
    pluie_ete        rain from June to August (mm)                      enough water when it counts?
    saison_sans_gel  days between the last spring and first fall frost  frost-free season
    jours_chauds     days above 30 °C                                   heat stress?
    tmin_janvier     mean January minimum (°C)                          do winter crops survive?

Used on the target climate of the farm (step 3) and on the observed climate of every place of
the grid (step 4).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from field_shift.algorithm.config.climate import (
    DEGREE_DAY_BASE_C,
    DEGREE_DAY_CAP_C,
    FIRST_FALL_DAY_OF_YEAR,
    FROST_C,
    GROWING_SEASON,
    HOT_DAY_C,
    JANUARY,
    NO_FALL_FROST_DAY,
    NO_SPRING_FROST_DAY,
    SUMMER,
    MonthRange,
)
from field_shift.algorithm.weather.daily_weather import DailyWeather

INDICATORS = ("djc10", "pluie_ete", "saison_sans_gel", "jours_chauds", "tmin_janvier")


def daily_degree_days(tmax: np.ndarray, tmin: np.ndarray) -> np.ndarray:
    """Growing degree-days of each day (temperatures capped between 10 and 30 °C)."""
    capped_max = np.clip(tmax, DEGREE_DAY_BASE_C, DEGREE_DAY_CAP_C)
    capped_min = np.clip(tmin, DEGREE_DAY_BASE_C, DEGREE_DAY_CAP_C)
    return (capped_max + capped_min) / 2 - DEGREE_DAY_BASE_C


def in_months(month: np.ndarray, months: MonthRange) -> np.ndarray:
    return (month >= months.first_month) & (month <= months.last_month)


def frost_free_season(tmin: np.ndarray, day_of_year: np.ndarray) -> int:
    """Days between the last spring frost and the first fall frost of one year."""
    frost = tmin <= FROST_C
    spring = day_of_year[frost & (day_of_year < FIRST_FALL_DAY_OF_YEAR)]
    fall = day_of_year[frost & (day_of_year >= FIRST_FALL_DAY_OF_YEAR)]
    last_spring = int(spring.max()) if spring.size else NO_SPRING_FROST_DAY
    first_fall = int(fall.min()) if fall.size else NO_FALL_FROST_DAY
    return first_fall - last_spring - 1


def _indicators_of_year(weather: DailyWeather, days: slice) -> list[float]:
    tmax, tmin, rain = weather.tmax[days], weather.tmin[days], weather.rain[days]
    month = weather.month[days]
    degree_days = daily_degree_days(tmax, tmin)[in_months(month, GROWING_SEASON)].sum()
    return [
        float(degree_days),
        float(rain[in_months(month, SUMMER)].sum()),
        float(frost_free_season(tmin, weather.day_of_year[days])),
        float((tmax > HOT_DAY_C).sum()),
        float(tmin[month == JANUARY].mean()),
    ]


@dataclass(frozen=True, eq=False)
class IndicatorTable:
    """The 5 indicators (columns, in the order of INDICATORS) of each year (rows)."""

    years: np.ndarray
    rows: np.ndarray

    @classmethod
    def from_weather(cls, weather: DailyWeather) -> IndicatorTable:
        """Step 2 on a daily weather series."""
        years, rows = [], []
        for year, days in weather.year_slices():
            years.append(year)
            rows.append(_indicators_of_year(weather, days))
        return cls(np.array(years), np.array(rows))

    def between(self, first_year: int, last_year: int) -> IndicatorTable:
        """The rows of the years `first_year` to `last_year`."""
        keep = (self.years >= first_year) & (self.years <= last_year)
        return IndicatorTable(self.years[keep], self.rows[keep])

    def means(self) -> np.ndarray:
        """Mean of each indicator over the years."""
        return self.rows.mean(axis=0)
