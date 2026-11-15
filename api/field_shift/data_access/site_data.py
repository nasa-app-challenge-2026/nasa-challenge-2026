"""Reads the conditions of a section (slope, soil, rain, satellite measures) from the data
services, at the place and over the shape of the section.

Only the services that give a variable the request did not give are called, in parallel. A
service that fails makes the whole section fail (`SiteDataUnavailableError`, with every failed
service and its reason): the model has no default value to fall back on. What a service answered
is kept on disk (`DataCache`), so a farmer editing his field, or the next sections of his farm,
do not read it again:

    - SoilGrids, MODIS: per point (about 100 m: the size of their pixels);
    - NASA POWER climatology and hourly rain: per NASA POWER cell (0.5° × 0.625°). Every section of
      a farm is in the same cell: the 10 years of hourly rain (1.5 MB) are read once per farm, not
      once per section.
"""

from __future__ import annotations

from collections.abc import Callable, Collection
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import date
from typing import Final, Protocol

import httpx

from field_shift.algorithm.soil_protection.forcing import last_growing_season
from field_shift.algorithm.soil_protection.site_conditions import SiteReading
from field_shift.algorithm.terrain.section_shape import SectionShape
from field_shift.algorithm.terrain.slope import terrain_of, terrain_sample
from field_shift.data_access.data_source_config import (
    ELEVATION,
    MODIS,
    MODIS_NDVI,
    POWER_CLIMATOLOGY,
    POWER_HOURLY,
    SOILGRIDS,
    DataSourceConfig,
)
from field_shift.data_access.disk_cache import DataCache
from field_shift.data_access.modis_ndvi import ModisNdviClient
from field_shift.data_access.site_readers import (
    SourceError,
    read_annual_et_ratio,
    read_climatology,
    read_elevations,
    read_et_ratio,
    read_season_ndvi,
    read_soil,
    read_storm,
)
from field_shift.data_access.soilgrids import SoilGridsClient

TIMEOUT_S: Final = 30.0
#: Points closer than 0.001° (about 100 m) share the same readings.
CACHE_PRECISION: Final = 1000
#: The cells of NASA POWER (MERRA-2): 0.5° of latitude, 0.625° of longitude.
POWER_CELL_LAT_DEG: Final = 0.5
POWER_CELL_LON_DEG: Final = 0.625
MAX_PARALLEL_REQUESTS: Final = 6
ORIGIN_SHAPE: Final = "calcul : forme de la section"
CACHE_NAMESPACE: Final = "site-readings"

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


def power_cell(lat: float, lon: float) -> tuple[int, int]:
    """The NASA POWER cell of a point (indices of the nearest cell centre)."""
    return (round((lat + 90) / POWER_CELL_LAT_DEG), round((lon + 180) / POWER_CELL_LON_DEG))


def _stored(readings: list[SiteReading]) -> list[dict]:
    return [asdict(reading) for reading in readings]


def _readings(stored: list[dict]) -> list[SiteReading]:
    return [SiteReading(**reading) for reading in stored]


class RemoteSiteData:
    """Reads the configured data services over HTTP."""

    def __init__(
        self,
        config: DataSourceConfig,
        http: httpx.Client | None = None,
        today: Callable[[], date] = date.today,
        cache: DataCache | None = None,
    ) -> None:
        """`cache` keeps the answers (on disk in the server); None: in memory only."""
        self._config = config
        self._http = http or httpx.Client(timeout=TIMEOUT_S)
        self._today = today
        self._cache = cache or DataCache.in_memory()
        self._ndvi = ModisNdviClient(config[MODIS_NDVI], self._http, self._cache)
        self._soilgrids = SoilGridsClient(config[SOILGRIDS], self._http, self._cache)

    def site_readings(self, shape: SectionShape, needed: Collection[str]) -> list[SiteReading]:
        needed = set(needed)
        lon, lat = shape.centroid
        place = (round(lat * CACHE_PRECISION), round(lon * CACHE_PRECISION))
        cell = power_cell(lat, lon)
        jobs: list[tuple[object, Callable[[], list[SiteReading]]]] = []
        if needed & TERRAIN_KEYS:
            jobs.append((("terrain", shape.ring), lambda: self._terrain(shape)))
        if needed & SOIL_KEYS:
            jobs.append((("soil", place), lambda: read_soil(self._soilgrids, lat, lon)))
        if needed & CLIMATOLOGY_KEYS:
            jobs.append(
                (
                    ("climatology", cell),
                    lambda: read_climatology(self._http, self._config[POWER_CLIMATOLOGY], lat, lon),
                )
            )
        today = self._today()
        if "storm_intensity_mm_h" in needed:
            jobs.append(
                (
                    ("storm", cell, today.year),
                    lambda: [read_storm(self._http, self._config[POWER_HOURLY], lat, lon, today)],
                )
            )
        season = last_growing_season(lat, today)
        if "ndvi" in needed:
            jobs.append(
                (
                    ("ndvi", place, season),
                    lambda: [read_season_ndvi(self._ndvi, lat, lon, season)],
                )
            )
        if "root_activity" in needed:
            jobs.append(
                (
                    ("et", place, season),
                    lambda: [self._et_ratio(lat, lon, season)],
                )
            )
        return [reading for reading in self._run(jobs) if reading.key in needed]

    def _et_ratio(self, lat: float, lon: float, season) -> SiteReading:
        """ΣET / ΣPET of the season (ORNL DAAC), else of its year (Planetary Computer)."""
        try:
            return read_et_ratio(self._http, self._config[MODIS], lat, lon, season)
        except SourceError as error:
            return read_annual_et_ratio(self._ndvi, lat, lon, season, error.reason)

    def _run(self, jobs: list[tuple[object, Callable[[], list[SiteReading]]]]) -> list[SiteReading]:
        """Every job in parallel; all the failures together."""
        if not jobs:
            return []

        def attempt(
            job: tuple[object, Callable[[], list[SiteReading]]],
        ) -> list[SiteReading] | SourceError:
            key, compute = job
            try:
                return _readings(
                    self._cache.get_or_fetch(CACHE_NAMESPACE, repr(key), lambda: _stored(compute()))
                )
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
