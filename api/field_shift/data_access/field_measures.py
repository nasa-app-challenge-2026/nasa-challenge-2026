"""The real measures of a section (step 8: erosion) and its soil (step 5), read at its place.

    slope_pct         plane fitted on the elevations of Copernicus DEM GLO-90 (Open-Meteo) over the
                      outline of the section (the same method as the soil protection, `terrain/`)
    heavy_rain_days   mean number of days a year with 25 mm of rain or more, in the NASA POWER
                      weather of the farm (PRECTOTCORR), RECENT_WINDOW
    bare_soil_days    days of the last complete year when MODIS sees no living plant on the
                      section: share of the NDVI composites (Terra + Aqua, 250 m, at the centre of
                      the section) at or below NDVI_BARE_SOIL, × 365
    soil              SoilGrids 2.0, clay, sand, organic carbon and pH over 0–30 cm at the centre
                      of the section; the soil test of the farmer replaces it

A section that is not drawn is measured at the point of the farm (a window of 270 m for the
slope). Nothing has a default value: a measure no service can give fails the plan (502, with the
name of the service), and a point without soil (built-up area, water) asks for a soil test.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import date
from typing import Final

import httpx
import numpy as np

from field_shift.algorithm.config.climate import RECENT_WINDOW
from field_shift.algorithm.config.soil_protection import (
    EARTH_RADIUS_M,
    MIN_TERRAIN_WINDOW_M,
    NDVI_BARE_SOIL,
)
from field_shift.algorithm.diagnostic.parcel_diagnostic import FieldMeasures
from field_shift.algorithm.sources.data_source import DataSource
from field_shift.algorithm.sources.field_data import (
    FIELD_MEASURES_KEY,
    SOIL_TEST_SOURCE,
    FieldData,
    FieldDataUnavailableError,
    SectionPlace,
)
from field_shift.algorithm.terrain.section_shape import SectionShape
from field_shift.algorithm.terrain.slope import terrain_of, terrain_sample
from field_shift.algorithm.twins.soil_comparison import Soil
from field_shift.algorithm.weather.daily_weather import DailyWeather
from field_shift.data_access.data_source_config import (
    ELEVATION,
    MODIS_NDVI,
    SOILGRIDS,
    DataSourceConfig,
)
from field_shift.data_access.disk_cache import DataCache
from field_shift.data_access.modis_ndvi import ModisNdviClient, NdviUnavailableError
from field_shift.data_access.site_readers import SourceError, read_elevations
from field_shift.data_access.soilgrids import NoSoilError, SoilGridsClient, SoilGridsError

#: A day of heavy rain: 25 mm or more (the definition of the erosion risk, step 8).
HEAVY_RAIN_MM: Final = 25.0
DAYS_PER_YEAR: Final = 365
#: Fewest valid NDVI composites in the year for a share of bare days.
MIN_NDVI_COMPOSITES: Final = 12
ELEVATION_CACHE: Final = "elevations"
DECIMALS: Final = 1
#: SoilGrids is the slowest of the services (up to a minute).
TIMEOUT_S: Final = 90.0

FIELD_SOURCE: Final = DataSource(
    FIELD_MEASURES_KEY,
    True,
    "Pente : Copernicus DEM (Open-Meteo) sur le contour de la section ; jours de forte pluie : "
    "NASA POWER ; jours de sol nu : NDVI MODIS (Planetary Computer) ; sol : SoilGrids 2.0",
)


def heavy_rain_days(weather: DailyWeather) -> float:
    """Mean days a year with HEAVY_RAIN_MM or more over RECENT_WINDOW."""
    recent = weather.between(RECENT_WINDOW.first, RECENT_WINDOW.last)
    years = RECENT_WINDOW.last - RECENT_WINDOW.first + 1
    return float(np.count_nonzero(recent.rain >= HEAVY_RAIN_MM)) / years


def bare_soil_days(series: list[tuple[str, float]]) -> float:
    """Days of the year without living plants: share of the composites at or below
    NDVI_BARE_SOIL. Raises ValueError with too few composites."""
    if len(series) < MIN_NDVI_COMPOSITES:
        raise ValueError(f"{len(series)} composites NDVI valides, {MIN_NDVI_COMPOSITES} au moins")
    bare = sum(1 for _, ndvi in series if ndvi <= NDVI_BARE_SOIL)
    return DAYS_PER_YEAR * bare / len(series)


def square_around(lat: float, lon: float, side_m: float = MIN_TERRAIN_WINDOW_M) -> SectionShape:
    """A square of `side_m` centred on a point (the window of a section that is not drawn)."""
    half_lat = math.degrees(side_m / 2 / EARTH_RADIUS_M)
    half_lon = half_lat / max(math.cos(math.radians(lat)), 1e-6)
    ring = [
        (lon - half_lon, lat - half_lat),
        (lon + half_lon, lat - half_lat),
        (lon + half_lon, lat + half_lat),
        (lon - half_lon, lat + half_lat),
        (lon - half_lon, lat - half_lat),
    ]
    return SectionShape.from_coordinates(ring)


class RemoteFieldData:
    """The measures of the sections, from the data services (kept on disk)."""

    source = FIELD_SOURCE

    def __init__(
        self,
        config: DataSourceConfig,
        http: httpx.Client | None = None,
        cache: DataCache | None = None,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._config = config
        self._http = http or httpx.Client(timeout=TIMEOUT_S)
        self._cache = cache or DataCache.default()
        self._today = today
        self._soilgrids = SoilGridsClient(config[SOILGRIDS], self._http, self._cache)
        self._ndvi = ModisNdviClient(config[MODIS_NDVI], self._http, self._cache)

    def field_data(
        self, section: SectionPlace, soil_test: Soil | None, weather: DailyWeather
    ) -> FieldData:
        shape = (
            SectionShape(section.ring) if section.ring else square_around(section.lat, section.lon)
        )
        slope_pct, slope_origin = self._slope(shape, drawn=bool(section.ring))
        bare_days, bare_origin = self._bare_soil_days(section.lat, section.lon)
        measures = FieldMeasures(
            slope_pct=round(slope_pct, DECIMALS),
            heavy_rain_days=round(heavy_rain_days(weather), DECIMALS),
            bare_soil_days=round(bare_days),
        )
        origin = (
            f"pente : {slope_origin} ; jours de forte pluie (≥ {HEAVY_RAIN_MM:g} mm) : NASA POWER "
            f"PRECTOTCORR {RECENT_WINDOW.first}–{RECENT_WINDOW.last} ; sol nu : {bare_origin}"
        )
        if soil_test is not None:
            return FieldData(measures, soil_test, SOIL_TEST_SOURCE, origin)
        return FieldData(measures, *self._soil(section), origin)

    def _slope(self, shape: SectionShape, drawn: bool) -> tuple[float, str]:
        endpoint = self._config[ELEVATION]
        sample = terrain_sample(shape)
        key = repr([(round(lon, 6), round(lat, 6)) for lon, lat in sample.geographic])
        try:
            elevations = self._cache.get_or_fetch(
                ELEVATION_CACHE,
                key,
                lambda: read_elevations(self._http, endpoint, sample.geographic),
            )
        except SourceError as error:
            raise FieldDataUnavailableError(str(error)) from error
        terrain = terrain_of(shape, sample, elevations)
        where = "sur le contour de la section" if drawn else "au point de la ferme (non tracée)"
        return terrain.slope_pct, f"{endpoint.dataset}, {terrain.points} altitudes {where}"

    def _bare_soil_days(self, lat: float, lon: float) -> tuple[float, str]:
        year = self._today().year - 1
        try:
            series = self._ndvi.year_series(lat, lon, year)
            days = bare_soil_days(series)
        except (NdviUnavailableError, ValueError) as error:
            raise FieldDataUnavailableError(f"{self._ndvi.dataset} : {error}") from error
        return days, (
            f"{len(series)} composites NDVI MODIS de {year} au centre de la section, "
            f"NDVI ≤ {NDVI_BARE_SOIL:g}"
        )

    def _soil(self, section: SectionPlace) -> tuple[Soil, str]:
        try:
            soil = self._soilgrids.topsoil_soil(section.lat, section.lon)
        except NoSoilError as error:
            raise FieldDataUnavailableError(
                f"section {section.id} : {error}. Donnez l’analyse de sol de la section."
            ) from error
        except SoilGridsError as error:
            raise FieldDataUnavailableError(f"section {section.id} : {error}") from error
        return soil, f"{self._soilgrids.dataset}, 0–30 cm au centre de la section"
