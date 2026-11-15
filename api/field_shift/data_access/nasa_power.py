"""NASA POWER daily weather at a point: ONE request per place for everything the server reads.

    the plan          maximum and minimum temperature at 2 m (°C), corrected rain (mm/day)
    the water model   relative humidity, wind at 2 m, solar radiation (FAO-56 ET0) and the
                      root-zone soil moisture of MERRA-2 (GWETROOT), from one more year (its soil
                      bucket fills up first)

All of it comes in one request (about 1.7 MB for 41 years), kept on disk (`DataCache`). Before,
the same weather was downloaded twice per place (once here, once by water_use), and again after
every restart of the server.

Public API, no account (https://power.larc.nasa.gov/docs/services/api/).
"""

from __future__ import annotations

from typing import Any, Final

import httpx
import numpy as np

from field_shift.algorithm.config.climate import FARM_WEATHER_YEARS, YearRange
from field_shift.algorithm.weather.daily_weather import DailyWeather
from field_shift.data_access.disk_cache import DataCache

API_URL: Final = "https://power.larc.nasa.gov/api/temporal/daily/point"
#: What the plan reads.
PARAMETERS: Final = ("T2M_MAX", "T2M_MIN", "PRECTOTCORR")
#: What the water model reads as well (water_use, Penman-Monteith and the MERRA-2 drought).
WATER_PARAMETERS: Final = ("RH2M", "WS2M", "ALLSKY_SFC_SW_DWN", "GWETROOT")
#: water_use starts one year before the years it scores: its soil bucket fills up first.
SPIN_UP_YEARS: Final = 1
DOWNLOAD_YEARS: Final = YearRange(FARM_WEATHER_YEARS.first - SPIN_UP_YEARS, FARM_WEATHER_YEARS.last)
COMMUNITY: Final = "AG"
FILL_VALUE: Final = -999
TIMEOUT_S: Final = 120.0
#: Points closer than 0.01° share the same answer (POWER cells are 0.5° × 0.625°).
CACHE_PRECISION: Final = 100
COORDINATE_DECIMALS: Final = 4
CACHE_NAMESPACE: Final = "nasa-power-daily"


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


def daily_weather_of(document: dict[str, Any], years: YearRange) -> DailyWeather:
    """The temperatures and rain of `years` in a NASA POWER daily answer.

    Raises WeatherUnavailableError when the answer misses a variable or a day."""
    try:
        columns = document["properties"]["parameter"]
        first, last = f"{years.first}0101", f"{years.last}1231"
        series = {
            name: _fill_gaps(
                [columns[name][day] for day in sorted(columns[name]) if first <= day <= last]
            )
            for name in PARAMETERS
        }
    except (KeyError, TypeError, ValueError) as error:
        raise WeatherUnavailableError(f"NASA POWER : réponse inattendue ({error!r})") from error
    expected_days = len(DailyWeather.calendar_columns(years.first, years.last)["year"])
    if any(len(values) != expected_days for values in series.values()):
        raise WeatherUnavailableError("NASA POWER a renvoyé un nombre de jours inattendu")
    return DailyWeather.from_series(
        years.first, years.last, series["T2M_MAX"], series["T2M_MIN"], series["PRECTOTCORR"]
    )


class NasaPowerClient:
    """Reads the daily weather of a point from NASA POWER, once per place."""

    def __init__(
        self,
        http: httpx.Client | None = None,
        url: str = API_URL,
        cache: DataCache | None = None,
    ) -> None:
        self._http = http or httpx.Client(timeout=TIMEOUT_S)
        self._url = url
        self._cache = cache or DataCache.default()

    def point_series(self, lat: float, lon: float) -> dict[str, Any]:
        """The whole daily answer of NASA POWER at the point (every variable, DOWNLOAD_YEARS),
        from the cache when the place was already read. Raises WeatherUnavailableError."""
        key = (
            f"{round(lat * CACHE_PRECISION)}:{round(lon * CACHE_PRECISION)}:"
            f"{DOWNLOAD_YEARS.first}-{DOWNLOAD_YEARS.last}:"
            f"{','.join(PARAMETERS + WATER_PARAMETERS)}"
        )
        return self._cache.get_or_fetch(CACHE_NAMESPACE, key, lambda: self._download(lat, lon))

    def fetch_daily(
        self, lat: float, lon: float, years: YearRange = FARM_WEATHER_YEARS
    ) -> DailyWeather:
        """The temperatures and rain of every day of `years` at the point."""
        return daily_weather_of(self.point_series(lat, lon), years)

    def _download(self, lat: float, lon: float) -> dict[str, Any]:
        params = {
            "parameters": ",".join(PARAMETERS + WATER_PARAMETERS),
            "community": COMMUNITY,
            "latitude": f"{lat:.{COORDINATE_DECIMALS}f}",
            "longitude": f"{lon:.{COORDINATE_DECIMALS}f}",
            "start": f"{DOWNLOAD_YEARS.first}0101",
            "end": f"{DOWNLOAD_YEARS.last}1231",
            "format": "JSON",
        }
        try:
            response = self._http.get(self._url, params=params)
            response.raise_for_status()
            document = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise WeatherUnavailableError(f"NASA POWER n’a pas pu être lu : {error}") from error
        # Checked before it is kept: a broken answer is never written to the cache.
        daily_weather_of(document, FARM_WEATHER_YEARS)
        return {
            "properties": {"parameter": document["properties"]["parameter"]},
            "geometry": document.get("geometry", {}),
            "header": {"fill_value": document.get("header", {}).get("fill_value", FILL_VALUE)},
            "parameters": document.get("parameters", {}),
        }
