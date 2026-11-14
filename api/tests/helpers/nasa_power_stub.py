"""A NASA POWER server that answers from memory: the tests never use the network."""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import numpy as np

from field_shift.algorithm.config.climate import FARM_WEATHER_YEARS
from field_shift.algorithm.sources.demo_farm_weather import demo_farm_weather
from field_shift.algorithm.weather.daily_weather import DailyWeather
from field_shift.data_access.nasa_power import FILL_VALUE, NasaPowerClient


def power_body(weather: DailyWeather, missing_days: int = 0) -> str:
    """The JSON NASA POWER sends for a daily point request (the first days missing if asked)."""
    days = np.arange(
        np.datetime64(f"{weather.first_year}-01-01"),
        np.datetime64(f"{weather.last_year + 1}-01-01"),
        dtype="datetime64[D]",
    )
    dates = [str(day).replace("-", "") for day in days]  # "1985-01-01" → "19850101"

    def column(values: np.ndarray) -> dict[str, float]:
        data = {date: float(value) for date, value in zip(dates, values, strict=True)}
        for date in dates[:missing_days]:
            data[date] = FILL_VALUE
        return data

    parameter = {
        "T2M_MAX": column(weather.tmax),
        "T2M_MIN": column(weather.tmin),
        "PRECTOTCORR": column(weather.rain),
    }
    return json.dumps({"properties": {"parameter": parameter}})


class StubbedPower:
    """A NasaPowerClient on a fake transport, counting the requests it received."""

    def __init__(self, respond: Callable[[httpx.Request], httpx.Response] | None = None) -> None:
        self.requests: list[httpx.Request] = []
        self.body = power_body(demo_farm_weather(FARM_WEATHER_YEARS))
        self._respond = respond or (lambda request: httpx.Response(200, content=self.body))
        transport = httpx.MockTransport(self._handle)
        self.client = NasaPowerClient(http=httpx.Client(transport=transport))

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self._respond(request)
