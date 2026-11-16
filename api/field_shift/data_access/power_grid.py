"""The observed climates of the twin search (step 4): the NASA POWER cells around the farm.

Every NASA POWER cell (MERRA-2, 0.5° × 0.625°) of a box of 10° × 10° centred on the farm, with
the 5 indicators of each year of TWIN_PERIOD (2011–2024, `IndicatorTable`) computed from its daily
temperatures and rain, exactly as for the farm itself.

The regional service serves one variable, at most 366 days and 10° × 10° per request: 3 variables
× 14 years = 42 requests, read in parallel (about 15 s). It is done once per box: the indicators of
the ~350 cells (a few hundred kB) are kept on disk, the daily values are not.

Whether a cell is cultivated is not known here: the crop maps say it when the cell becomes a
candidate twin (`twin_crops.py`).
"""

from __future__ import annotations

import math
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Final

import httpx
import numpy as np

from field_shift.algorithm.climate.indicator_table import IndicatorTable
from field_shift.algorithm.config.climate import TWIN_PERIOD, YearRange
from field_shift.algorithm.twins.climate_twin_finder import GridCell
from field_shift.algorithm.weather.daily_weather import DailyWeather
from field_shift.data_access.disk_cache import DataCache

API_URL: Final = "https://power.larc.nasa.gov/api/temporal/daily/regional"
PARAMETERS: Final = ("T2M_MAX", "T2M_MIN", "PRECTOTCORR")
#: The service accepts at most 10° of latitude and of longitude.
HALF_SPAN_DEG: Final = 5.0
#: The box is centred on the 0.5° point nearest the farm: nearby farms share it.
CENTRE_STEP_DEG: Final = 0.5
MAX_ABS_LATITUDE: Final = 89.5
FILL_VALUE: Final = -999
TIMEOUT_S: Final = 180.0
MAX_PARALLEL_REQUESTS: Final = 6
ATTEMPTS: Final = 3
RETRY_WAIT_S: Final = 2.0
COORDINATE_DECIMALS: Final = 3
CACHE_NAMESPACE: Final = "nasa-power-grid"


class GridUnavailableError(RuntimeError):
    """NASA POWER could not give the climates of the grid around the farm."""


def grid_box(lat: float, lon: float) -> tuple[float, float, float, float]:
    """(lat min, lat max, lon min, lon max) of the box of the farm."""
    centre_lat = round(lat / CENTRE_STEP_DEG) * CENTRE_STEP_DEG
    centre_lon = round(lon / CENTRE_STEP_DEG) * CENTRE_STEP_DEG
    lat_min = max(-MAX_ABS_LATITUDE, centre_lat - HALF_SPAN_DEG)
    lat_max = min(MAX_ABS_LATITUDE, centre_lat + HALF_SPAN_DEG)
    return lat_min, lat_max, centre_lon - HALF_SPAN_DEG, centre_lon + HALF_SPAN_DEG


def _dates(year: int) -> list[str]:
    """The days of a year as NASA POWER names them (YYYYMMDD)."""
    return [
        str(day).replace("-", "")
        for day in np.arange(
            np.datetime64(f"{year}-01-01"),
            np.datetime64(f"{year + 1}-01-01"),
            dtype="datetime64[D]",
        )
    ]


def _day_values(days: dict[str, Any], dates: list[str]) -> np.ndarray:
    """The values of a year in the order of its days, NaN where a day is missing or filled.

    Kept as one array per cell and per request instead of the answer's dict: the 42 answers
    of a box hold ~5 million days, ~500 MB as Python dicts and ~40 MB as arrays."""
    return np.array(
        [
            float(v) if isinstance(v, int | float) and v > FILL_VALUE else np.nan
            for v in (days.get(day, FILL_VALUE) for day in dates)
        ]
    )


def _filled(array: np.ndarray) -> np.ndarray:
    """Missing days (NaN) take the value of the day before (the first one: the next known day)."""
    known = np.flatnonzero(np.isfinite(array))
    if not known.size:
        raise GridUnavailableError("NASA POWER : une case de la grille n’a aucune valeur")
    index = np.maximum.accumulate(np.where(np.isfinite(array), np.arange(len(array)), -1))
    index[index < 0] = known[0]
    return array[index]


class PowerGridClient:
    """Reads the observed climates of the cells around a farm."""

    def __init__(
        self,
        http: httpx.Client | None = None,
        url: str = API_URL,
        cache: DataCache | None = None,
        period: YearRange = TWIN_PERIOD,
    ) -> None:
        self._http = http or httpx.Client(timeout=TIMEOUT_S)
        self._url = url
        self._cache = cache or DataCache.default()
        self._period = period

    def cells(self, lat: float, lon: float) -> list[GridCell]:
        """The cells of the box of the farm, their cultivation unknown. Raises
        GridUnavailableError."""
        box = grid_box(lat, lon)
        key = f"{box}:{self._period.first}-{self._period.last}:{','.join(PARAMETERS)}"
        stored = self._cache.get_or_fetch(CACHE_NAMESPACE, key, lambda: self._indicators(box))
        years = np.array(stored["years"])
        return [
            GridCell(
                id=cell["id"],
                lat=cell["lat"],
                lon=cell["lon"],
                cultivated=None,
                indicators=IndicatorTable(years, np.array(cell["rows"], dtype=float)),
            )
            for cell in stored["cells"]
        ]

    def _request(
        self, box: tuple[float, float, float, float], name: str, year: int
    ) -> dict[tuple[float, float], np.ndarray]:
        lat_min, lat_max, lon_min, lon_max = box
        params = {
            "parameters": name,
            "community": "AG",
            "latitude-min": f"{lat_min:g}",
            "latitude-max": f"{lat_max:g}",
            "longitude-min": f"{lon_min:g}",
            "longitude-max": f"{lon_max:g}",
            "start": f"{year}0101",
            "end": f"{year}1231",
            "format": "JSON",
        }
        last_error: Exception | None = None
        for attempt in range(ATTEMPTS):
            try:
                response = self._http.get(self._url, params=params)
                response.raise_for_status()
                features = response.json()["features"]
                dates = _dates(year)
                return {
                    (
                        round(f["geometry"]["coordinates"][1], COORDINATE_DECIMALS),
                        round(f["geometry"]["coordinates"][0], COORDINATE_DECIMALS),
                    ): _day_values(f["properties"]["parameter"][name], dates)
                    for f in features
                }
            except httpx.HTTPStatusError as error:
                last_error = error
                if error.response.status_code in (400, 404, 422):
                    break  # a wrong request: no use asking again
            except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
                last_error = error
            time.sleep(RETRY_WAIT_S * (attempt + 1))
        raise GridUnavailableError(
            f"NASA POWER (grille régionale, {name} {year}) n’a pas pu être lu : {last_error}"
        )

    def _indicators(self, box: tuple[float, float, float, float]) -> dict[str, Any]:
        years = range(self._period.first, self._period.last + 1)
        jobs = [(name, year) for year in years for name in PARAMETERS]
        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_REQUESTS) as pool:
            answers = list(pool.map(lambda job: self._request(box, *job), jobs))
        by_job = dict(zip(jobs, answers, strict=True))
        points = sorted(set.intersection(*(set(answer) for answer in answers)))
        if not points:
            raise GridUnavailableError("NASA POWER : la grille autour de la ferme est vide")
        cells = []
        for point in points:
            columns = {}
            for name in PARAMETERS:
                values = np.concatenate([by_job[(name, year)][point] for year in years])
                columns[name] = _filled(values)
            weather = DailyWeather.from_series(
                self._period.first,
                self._period.last,
                columns["T2M_MAX"],
                columns["T2M_MIN"],
                columns["PRECTOTCORR"],
            )
            table = IndicatorTable.from_weather(weather)
            cell_lat, cell_lon = point
            cells.append(
                {
                    "id": f"{cell_lat:.2f}:{cell_lon:.3f}",
                    "lat": cell_lat,
                    "lon": cell_lon,
                    "rows": [[float(v) for v in row] for row in table.rows],
                }
            )
        return {"years": [int(y) for y in years], "cells": cells}


def distance_km(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    """Great-circle distance between two points."""
    earth_radius_km = 6371.0
    p1, p2 = math.radians(lat_a), math.radians(lat_b)
    dp, dl = p2 - p1, math.radians(lon_b - lon_a)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * earth_radius_km * math.asin(math.sqrt(a))
