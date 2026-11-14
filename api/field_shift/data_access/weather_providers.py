"""Where the weather of the farm comes from: NASA POWER (real) or the fictitious series (offline,
tests, and when NASA POWER cannot be reached — the plan then says so)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from field_shift.algorithm.config.climate import FARM_WEATHER_YEARS
from field_shift.algorithm.sources.data_source import DataSource
from field_shift.algorithm.sources.demo_farm_weather import demo_farm_weather
from field_shift.algorithm.weather.daily_weather import DailyWeather
from field_shift.data_access.nasa_power import NasaPowerClient, WeatherUnavailableError

logger = logging.getLogger(__name__)

WEATHER_KEY = "farmWeather"
NASA_SOURCE = DataSource(
    WEATHER_KEY,
    real=True,
    label=(
        f"NASA POWER, météo quotidienne {FARM_WEATHER_YEARS.first}–{FARM_WEATHER_YEARS.last} "
        "au point de la ferme"
    ),
)
DEMO_SOURCE = DataSource(WEATHER_KEY, real=False, label="Météo fictive (mode démonstration)")
FALLBACK_SOURCE = DataSource(
    WEATHER_KEY, real=False, label="Météo fictive (NASA POWER n’a pas pu être joint)"
)


@dataclass(frozen=True)
class FarmWeather:
    """The weather of a farm, where it comes from, and whether it replaces a failed read (then it
    is not kept: NASA POWER is tried again next time)."""

    weather: DailyWeather
    source: DataSource
    is_fallback: bool = False


class WeatherProvider(Protocol):
    def farm_weather(self, lat: float, lon: float) -> FarmWeather: ...


class DemoWeatherProvider:
    """The fictitious weather of field_shift.py, whatever the place."""

    def farm_weather(self, lat: float, lon: float) -> FarmWeather:
        return FarmWeather(demo_farm_weather(), DEMO_SOURCE)


class NasaPowerWeatherProvider:
    """The real weather; the fictitious one if NASA POWER cannot be read."""

    def __init__(self, client: NasaPowerClient | None = None) -> None:
        self._client = client or NasaPowerClient()

    def farm_weather(self, lat: float, lon: float) -> FarmWeather:
        try:
            return FarmWeather(self._client.fetch_daily(lat, lon, FARM_WEATHER_YEARS), NASA_SOURCE)
        except WeatherUnavailableError as error:
            logger.warning("%s: using the fictitious weather", error)
            return FarmWeather(demo_farm_weather(), FALLBACK_SOURCE, is_fallback=True)
