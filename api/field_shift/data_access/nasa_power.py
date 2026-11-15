"""NASA POWER daily weather at a point: maximum and minimum temperature at 2 m (°C) and corrected
rain (mm/day).

Public API, no account (https://power.larc.nasa.gov/docs/services/api/). About 0.7 MB for 40
years. Results are kept in memory, per point.
"""

from __future__ import annotations

import threading
from typing import Final

import httpx
import numpy as np

from field_shift.algorithm.config.climate import YearRange
from field_shift.algorithm.weather.daily_weather import DailyWeather

API_URL: Final = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMETERS: Final = ("T2M_MAX", "T2M_MIN", "PRECTOTCORR")
COMMUNITY: Final = "AG"
FILL_VALUE: Final = -999
TIMEOUT_S: Final = 30.0
#: Points closer than 0.01° share the same POWER cell and the same cache entry.
CACHE_PRECISION: Final = 100
COORDINATE_DECIMALS: Final = 4


class WeatherUnavailableError(RuntimeError):
    """NASA POWER could not give the weather (network, error answer, unexpected content)."""


def _fill_gaps(values: list[float]) -> np.ndarray:
    """Missing days (fill value) take the value of the day before."""
    filled, previous = [], 0.0
    for value in values:
        if not isinstance(value, int | float) or value <= FILL_VALUE:
            value = previous
        filled.append(value)
        previous = value
    return np.array(filled, dtype=float)


class NasaPowerClient:
    """Reads the daily weather of a point from NASA POWER."""

    def __init__(self, http: httpx.Client | None = None, url: str = API_URL) -> None:
        self._http = http or httpx.Client(timeout=TIMEOUT_S)
        self._url = url
        self._cache: dict[tuple[int, int, int, int], DailyWeather] = {}
        self._lock = threading.Lock()

    def fetch_daily(self, lat: float, lon: float, years: YearRange) -> DailyWeather:
        """The weather of every day of `years` at the point, from the cache when already read."""
        key = (
            round(lat * CACHE_PRECISION),
            round(lon * CACHE_PRECISION),
            years.first,
            years.last,
        )
        with self._lock:
            if key not in self._cache:
                self._cache[key] = self._download(lat, lon, years)
            return self._cache[key]

    def _download(self, lat: float, lon: float, years: YearRange) -> DailyWeather:
        params = {
            "parameters": ",".join(PARAMETERS),
            "community": COMMUNITY,
            "latitude": f"{lat:.{COORDINATE_DECIMALS}f}",
            "longitude": f"{lon:.{COORDINATE_DECIMALS}f}",
            "start": f"{years.first}0101",
            "end": f"{years.last}1231",
            "format": "JSON",
        }
        try:
            response = self._http.get(self._url, params=params)
            response.raise_for_status()
            columns = response.json()["properties"]["parameter"]
            series = {
                name: _fill_gaps([columns[name][d] for d in sorted(columns[name])])
                for name in PARAMETERS
            }
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise WeatherUnavailableError(f"NASA POWER n’a pas pu être lu : {error}") from error
        expected_days = len(DailyWeather.calendar_columns(years.first, years.last)["year"])
        if any(len(values) != expected_days for values in series.values()):
            raise WeatherUnavailableError("NASA POWER a renvoyé un nombre de jours inattendu")
        return DailyWeather.from_series(
            years.first, years.last, series["T2M_MAX"], series["T2M_MIN"], series["PRECTOTCORR"]
        )
