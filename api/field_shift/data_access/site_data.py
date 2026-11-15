"""Reads the conditions of a section (slope, soil, rain, satellite measures) from the data
services, at the place and over the shape of the section.

Only the services that give a variable the request did not give are called, in parallel. A
service that fails makes the whole section fail (`SiteDataUnavailableError`, with every failed
service and its reason): the model has no default value to fall back on. What a service answered
for a place is remembered, so a farmer editing his field does not read it again.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from collections.abc import Callable, Collection
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Final, Protocol, TypeVar

import httpx

from field_shift.algorithm.soil_protection.forcing import last_growing_season
from field_shift.algorithm.soil_protection.site_conditions import SiteReading
from field_shift.algorithm.terrain.section_shape import SectionShape
from field_shift.algorithm.terrain.slope import terrain_of, terrain_sample
from field_shift.data_access.data_source_config import (
    ELEVATION,
    MODIS,
    POWER_CLIMATOLOGY,
    POWER_HOURLY,
    SOILGRIDS,
    DataSourceConfig,
)
from field_shift.data_access.site_readers import (
    SourceError,
    read_climatology,
    read_elevations,
    read_et_ratio,
    read_ndvi,
    read_soil,
    read_storm,
)

T = TypeVar("T")

TIMEOUT_S: Final = 30.0
#: Points closer than 0.001° (about 100 m) share the same readings.
CACHE_PRECISION: Final = 1000
MAX_CACHED: Final = 512
MAX_PARALLEL_REQUESTS: Final = 6
ORIGIN_SHAPE: Final = "calcul : forme de la section"

TERRAIN_KEYS: Final = frozenset({"slope_pct", "slope_length_m"})
SOIL_KEYS: Final = frozenset({"sand_pct", "clay_pct", "organic_matter_pct"})
CLIMATOLOGY_KEYS: Final = frozenset({"annual_rain_mm", "soil_saturation"})


class SiteDataUnavailableError(RuntimeError):
    """One or more data services could not give the values a section needs."""

    def __init__(self, failures: Collection[SourceError]) -> None:
        self.failures = tuple(failures)
        super().__init__(" ; ".join(str(failure) for failure in self.failures))


class SiteDataProvider(Protocol):
    """Gives what the data services know about a section."""

    def site_readings(self, shape: SectionShape, needed: Collection[str]) -> list[SiteReading]:
        """The readings of the `needed` variables. Raises SiteDataUnavailableError."""
        ...


class _Cache:
    """A small thread-safe memory of the last answers, by key."""

    def __init__(self) -> None:
        self._items: OrderedDict[object, object] = OrderedDict()
        self._lock = threading.Lock()

    def get_or_compute(self, key: object, compute: Callable[[], T]) -> T:
        with self._lock:
            if key in self._items:
                self._items.move_to_end(key)
                return self._items[key]  # type: ignore[return-value]
        value = compute()  # outside the lock: services are read in parallel; failures not kept
        with self._lock:
            self._items[key] = value
            while len(self._items) > MAX_CACHED:
                self._items.popitem(last=False)
        return value


class RemoteSiteData:
    """Reads the configured data services over HTTP."""

    def __init__(
        self,
        config: DataSourceConfig,
        http: httpx.Client | None = None,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._config = config
        self._http = http or httpx.Client(timeout=TIMEOUT_S)
        self._today = today
        self._cache = _Cache()

    def site_readings(self, shape: SectionShape, needed: Collection[str]) -> list[SiteReading]:
        needed = set(needed)
        lon, lat = shape.centroid
        place = (round(lat * CACHE_PRECISION), round(lon * CACHE_PRECISION))
        jobs: list[tuple[object, Callable[[], list[SiteReading]]]] = []
        if needed & TERRAIN_KEYS:
            jobs.append((("terrain", shape.ring), lambda: self._terrain(shape)))
        if needed & SOIL_KEYS:
            jobs.append(
                (("soil", place), lambda: read_soil(self._http, self._config[SOILGRIDS], lat, lon))
            )
        if needed & CLIMATOLOGY_KEYS:
            jobs.append(
                (
                    ("climatology", place),
                    lambda: read_climatology(self._http, self._config[POWER_CLIMATOLOGY], lat, lon),
                )
            )
        today = self._today()
        if "storm_intensity_mm_h" in needed:
            jobs.append(
                (
                    ("storm", place, today.year),
                    lambda: [read_storm(self._http, self._config[POWER_HOURLY], lat, lon, today)],
                )
            )
        season = last_growing_season(lat, today)
        if "ndvi" in needed:
            jobs.append(
                (
                    ("ndvi", place, season),
                    lambda: [read_ndvi(self._http, self._config[MODIS], lat, lon, season)],
                )
            )
        if "root_activity" in needed:
            jobs.append(
                (
                    ("et", place, season),
                    lambda: [read_et_ratio(self._http, self._config[MODIS], lat, lon, season)],
                )
            )
        return [reading for reading in self._run(jobs) if reading.key in needed]

    def _run(self, jobs: list[tuple[object, Callable[[], list[SiteReading]]]]) -> list[SiteReading]:
        """Every job in parallel; all the failures together."""
        if not jobs:
            return []

        def attempt(
            job: tuple[object, Callable[[], list[SiteReading]]],
        ) -> list[SiteReading] | SourceError:
            key, compute = job
            try:
                return self._cache.get_or_compute(key, compute)
            except SourceError as error:
                return error

        with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_REQUESTS, len(jobs))) as pool:
            results = list(pool.map(attempt, jobs))
        failures = [result for result in results if isinstance(result, SourceError)]
        if failures:
            raise SiteDataUnavailableError(failures)
        return [
            reading
            for result in results
            if not isinstance(result, SourceError)
            for reading in result
        ]

    def _terrain(self, shape: SectionShape) -> list[SiteReading]:
        endpoint = self._config[ELEVATION]
        sample = terrain_sample(shape)
        terrain = terrain_of(
            shape, sample, read_elevations(self._http, endpoint, sample.geographic)
        )
        where = (
            "dans la section"
            if terrain.inside
            else "sur une fenêtre de 270 m autour de la section (plus petite que la grille)"
        )
        return [
            SiteReading(
                "slope_pct",
                terrain.slope_pct,
                endpoint.dataset,
                f"plan ajusté par moindres carrés sur {terrain.points} altitudes {where}",
            ),
            SiteReading(
                "slope_length_m",
                terrain.slope_length_m,
                ORIGIN_SHAPE,
                "longueur de la section dans le sens de la plus grande pente (RUSLE la borne à "
                "305 m)",
            ),
        ]
