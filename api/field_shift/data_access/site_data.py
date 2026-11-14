"""Reads the conditions of a place (slope, soil, rain, satellite measures) from the configured
data sources.

Each configured source is one HTTP GET at the point (see `data_source_config` for the format).
A source that fails is skipped and logged: the model then keeps its default value, and the
answer of the server says where each value came from.
"""

from __future__ import annotations

import logging
import math
import threading
from collections import OrderedDict
from typing import Any, Final, Protocol

import httpx

from field_shift.algorithm.soil_protection.site_conditions import SITE_VARIABLES, SiteReading
from field_shift.data_access.data_source_config import DataEndpoint, DataSourceConfig

logger = logging.getLogger(__name__)

TIMEOUT_S: Final = 15.0
#: Points closer than 0.01° (about 1 km) share the same readings.
CACHE_PRECISION: Final = 100
#: Places kept in memory.
MAX_CACHED_PLACES: Final = 256
COORDINATE_DECIMALS: Final = 5


class SiteDataError(RuntimeError):
    """A data source could not give its value (network, error answer, unexpected content)."""


class SiteDataProvider(Protocol):
    """Gives what the data sources know about a place."""

    def site_readings(self, lat: float, lon: float) -> list[SiteReading]:
        """The readings available at the point (possibly none); never raises."""
        ...


class NoSiteData:
    """No data source at all: the model runs on what the sections give and on its defaults
    (demo mode, tests)."""

    def site_readings(self, lat: float, lon: float) -> list[SiteReading]:
        return []


def value_at(document: Any, json_path: str) -> Any:
    """The value at a dotted path of a JSON document ("results.0.value").

    A segment is a key of an object or a position in a list. Raises SiteDataError when the path
    does not exist.
    """
    current = document
    for segment in filter(None, json_path.split(".")):
        try:
            current = current[int(segment)] if isinstance(current, list) else current[segment]
        except (KeyError, IndexError, ValueError, TypeError):
            raise SiteDataError(f"chemin {json_path!r} absent de la réponse") from None
    return current


class RemoteSiteData:
    """Reads the configured point sources over HTTP, and remembers the places already read."""

    def __init__(self, config: DataSourceConfig, http: httpx.Client | None = None) -> None:
        self._sources = config.point_sources
        self._http = http or httpx.Client(timeout=TIMEOUT_S)
        self._cache: OrderedDict[tuple[int, int], list[SiteReading]] = OrderedDict()
        self._lock = threading.Lock()

    def site_readings(self, lat: float, lon: float) -> list[SiteReading]:
        key = (round(lat * CACHE_PRECISION), round(lon * CACHE_PRECISION))
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
        readings, complete = self._read_all(lat, lon)
        if complete:  # a place with a failed source is not kept: the source is tried again
            with self._lock:
                self._cache[key] = readings
                while len(self._cache) > MAX_CACHED_PLACES:
                    self._cache.popitem(last=False)
        return readings

    def _read_all(self, lat: float, lon: float) -> tuple[list[SiteReading], bool]:
        """The readings of every source, and whether all of them answered."""
        readings: list[SiteReading] = []
        complete = True
        for source in self._sources:
            try:
                value = self._read(source, lat, lon)
                readings.append(SiteReading(source.key, value, source.dataset))
            except SiteDataError as error:
                complete = False
                logger.warning("%s (%s): %s; default value used", source.key, source.dataset, error)
        return readings, complete

    def _read(self, source: DataEndpoint, lat: float, lon: float) -> float:
        """The value of one source at the point, in the unit of its site variable."""
        url = source.url.replace("{lat}", f"{lat:.{COORDINATE_DECIMALS}f}").replace(
            "{lon}", f"{lon:.{COORDINATE_DECIMALS}f}"
        )
        try:
            response = self._http.get(url, headers=dict(source.headers))
            response.raise_for_status()
            raw = value_at(response.json(), source.json_path)
            value = float(raw) * source.scale
        except httpx.HTTPError as error:
            raise SiteDataError(f"la source n’a pas répondu : {error}") from error
        except (TypeError, ValueError) as error:
            raise SiteDataError(f"réponse illisible : {error}") from error
        if math.isnan(value) or not SITE_VARIABLES[source.key].accepts(value):
            raise SiteDataError(f"valeur hors limites : {value}")
        return value
