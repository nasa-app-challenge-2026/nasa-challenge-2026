"""Where the weather of the farm comes from: NASA POWER. There is no fictitious weather to fall
back on: when NASA POWER cannot be read, the plan fails (`WeatherUnavailableError`, answered 502)
and NASA POWER is tried again at the next request."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from field_shift.algorithm.config.climate import FARM_WEATHER_YEARS
from field_shift.algorithm.sources.data_source import DataSource
from field_shift.algorithm.weather.daily_weather import DailyWeather
from field_shift.data_access.nasa_power import NasaPowerClient

WEATHER_KEY = "farmWeather"
NASA_SOURCE = DataSource(
    WEATHER_KEY,
    real=True,
    label=(
        f"NASA POWER, météo quotidienne {FARM_WEATHER_YEARS.first}–{FARM_WEATHER_YEARS.last} "
        "au point de la ferme"
    ),
)


@dataclass(frozen=True)
class FarmWeather:
    """The weather of a farm and where it comes from.

    `power_series` is the whole NASA POWER answer at the point (humidity, wind, radiation, soil
    moisture too), given to the water model so that it does not download it again; None when the
    weather does not come from NASA POWER (the tests)."""

    weather: DailyWeather
    source: DataSource
    power_series: dict[str, Any] | None = field(default=None, repr=False)


class WeatherProvider(Protocol):
    def farm_weather(self, lat: float, lon: float) -> FarmWeather:
        """The weather at the farm. Raises WeatherUnavailableError."""
        ...


class NasaPowerWeatherProvider:
    """The real weather of NASA POWER (one request per place, kept on disk)."""

    def __init__(self, client: NasaPowerClient | None = None) -> None:
        self._client = client or NasaPowerClient()

    def farm_weather(self, lat: float, lon: float) -> FarmWeather:
        series = self._client.point_series(lat, lon)
        return FarmWeather(
            self._client.fetch_daily(lat, lon, FARM_WEATHER_YEARS), NASA_SOURCE, series
        )
