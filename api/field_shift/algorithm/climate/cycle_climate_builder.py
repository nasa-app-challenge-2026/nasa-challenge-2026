"""Builds the climate calendar of a cycle (CycleClimate) from a daily weather series."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from field_shift.algorithm.climate.cycle_climate import ClimateMethod, CycleClimate
from field_shift.algorithm.climate.indicator_table import (
    daily_degree_days,
    in_months,
)
from field_shift.algorithm.config.climate import (
    FIRST_FALL_DAY_OF_YEAR,
    FROST_C,
    HARVEST_ADVANCE_MONTHS_PER_C,
    JANUARY,
    SUMMER,
)
from field_shift.algorithm.config.timing import DAYS_PER_MONTH, MONTHS_PER_YEAR
from field_shift.algorithm.weather.daily_weather import DailyWeather


def _mean_of_finite(values: Sequence[float]) -> float | None:
    finite = [v for v in values if np.isfinite(v)]
    return float(np.mean(finite)) if finite else None


def _day_to_month(day_of_year: float | None) -> float | None:
    return None if day_of_year is None else (day_of_year - 1) / DAYS_PER_MONTH


def _mean_frost_days(weather: DailyWeather) -> tuple[float | None, float | None]:
    """Mean day of the last spring frost and first fall frost, over the years that had one."""
    last_springs, first_falls = [], []
    for _, days in weather.year_slices():
        frost = weather.tmin[days] <= FROST_C
        doy = weather.day_of_year[days]
        spring = doy[frost & (doy < FIRST_FALL_DAY_OF_YEAR)]
        fall = doy[frost & (doy >= FIRST_FALL_DAY_OF_YEAR)]
        last_springs.append(spring.max() if spring.size else np.nan)
        first_falls.append(fall.min() if fall.size else np.nan)
    return _mean_of_finite(last_springs), _mean_of_finite(first_falls)


def mean_summer_rain(weather: DailyWeather) -> float:
    """Mean, over the years, of the June–August rain."""
    summer = in_months(weather.month, SUMMER)
    return float(
        np.mean([weather.rain[days][summer[days]].sum() for _, days in weather.year_slices()])
    )


def mean_temperature(weather: DailyWeather) -> float:
    """Mean daily temperature over the whole series."""
    return float(weather.daily_mean.mean())


def climate_from_weather(
    weather: DailyWeather,
    *,
    warming_c: float,
    method: ClimateMethod,
    source: str,
    summer_rain_change_pct: float = 0.0,
    models: tuple[str, ...] = (),
) -> CycleClimate:
    """The climate calendar of the weather of a cycle."""
    degree_days = daily_degree_days(weather.tmax, weather.tmin)
    per_month = tuple(
        float(degree_days[weather.month == month].mean()) for month in range(1, MONTHS_PER_YEAR + 1)
    )
    last_spring, first_fall = _mean_frost_days(weather)
    return CycleClimate(
        degree_days_per_day=per_month,
        last_spring_frost=_day_to_month(last_spring),
        first_fall_frost=_day_to_month(first_fall),
        january_minimum_c=float(weather.tmin[weather.month == JANUARY].mean()),
        harvest_advance_months=HARVEST_ADVANCE_MONTHS_PER_C * warming_c,
        method=method,
        source=source,
        warming_c=warming_c,
        summer_rain_change_pct=summer_rain_change_pct,
        models=models,
    )


def average_climates(
    climates: Sequence[CycleClimate], *, method: ClimateMethod, source: str
) -> CycleClimate:
    """One calendar per cycle: the mean of the climate models (case 2)."""

    def mean_of(get) -> float:
        return float(np.mean([get(c) for c in climates]))

    def mean_frost(get) -> float | None:
        return _mean_of_finite([np.nan if get(c) is None else get(c) for c in climates])

    return CycleClimate(
        degree_days_per_day=tuple(
            mean_of(lambda c, k=k: c.degree_days_per_day[k]) for k in range(MONTHS_PER_YEAR)
        ),
        last_spring_frost=mean_frost(lambda c: c.last_spring_frost),
        first_fall_frost=mean_frost(lambda c: c.first_fall_frost),
        january_minimum_c=mean_of(lambda c: c.january_minimum_c),
        harvest_advance_months=mean_of(lambda c: c.harvest_advance_months),
        method=method,
        source=source,
        warming_c=mean_of(lambda c: c.warming_c),
        summer_rain_change_pct=mean_of(lambda c: c.summer_rain_change_pct),
        models=tuple(model for c in climates for model in c.models),
    )
