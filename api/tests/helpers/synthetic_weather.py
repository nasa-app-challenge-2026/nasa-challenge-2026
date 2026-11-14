"""Deterministic synthetic weather, identical to the one of the fixture export script.

Every number comes from a Park-Miller generator (integer arithmetic), so the fixtures exported from
the reference and these tests start from exactly the same weather.
"""

from __future__ import annotations

import numpy as np

from field_shift.algorithm.climate.target_climate_projector import ModelSimulation
from field_shift.algorithm.weather.daily_weather import DailyWeather

MODULUS = 2147483647
MULTIPLIER = 48271
MONTHLY_MEAN_C = [-10, -8, -2, 6.5, 13.5, 19, 21.5, 20.5, 15.5, 8.5, 2, -6]


class ParkMiller:
    def __init__(self, seed: int) -> None:
        self.state = seed % MODULUS or 1

    def next(self) -> float:
        self.state = (self.state * MULTIPLIER) % MODULUS
        return self.state / MODULUS


def synthetic_weather(
    first_year: int, last_year: int, seed: int, trend: float = 0.04, offset_c: float = 0.0
) -> DailyWeather:
    rng = ParkMiller(seed)
    calendar = DailyWeather.calendar_columns(first_year, last_year)
    anomaly = {y: (rng.next() - 0.5) * 2.4 for y in range(first_year, last_year + 1)}
    tmax, tmin, rain = [], [], []
    for year, month in zip(calendar["year"], calendar["month"], strict=True):
        mean = (
            MONTHLY_MEAN_C[month - 1]
            + offset_c
            + trend * (year - 2014.5)
            + anomaly[int(year)]
            + (rng.next() - 0.5) * 12.0
        )
        tmax.append(mean + 6.0)
        tmin.append(mean - 6.0)
        wet, amount = rng.next(), rng.next()
        rain.append(0.0 if wet < 0.6 else amount * 25.0)
    return DailyWeather(**calendar, tmax=np.array(tmax), tmin=np.array(tmin), rain=np.array(rain))


class SyntheticModel:
    """A fictitious climate model built on synthetic weather."""

    def __init__(self, name: str, seed: int, warming_factor: float, rain_ratio: float) -> None:
        self.name = name
        self._warming_factor = warming_factor
        self._rain_ratio = rain_ratio
        self._historical = synthetic_weather(1985, 2014, seed).shifted_by(1.0)

    def simulate(self, first_year: int, last_year: int) -> ModelSimulation:
        delta = self._warming_factor * 0.04 * ((first_year + last_year) / 2 - 1999.5)
        future = self._historical.shifted_by(delta)
        return ModelSimulation(
            self._historical, future.with_values(rain=self._historical.rain * self._rain_ratio)
        )
