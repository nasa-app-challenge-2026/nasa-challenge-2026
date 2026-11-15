"""The satellite measures of the erosion (step 8) and the soil (step 5) of a field: the interface.

The server reads them from the data services (`data_access/field_measures.py`) at the place of
the section: the slope over its outline (Copernicus DEM), the days of heavy rain (NASA POWER), the
days of bare soil (MODIS NDVI) and the soil (SoilGrids 2.0). A soil test of the farmer replaces
SoilGrids. Nothing about water is here: it comes from the water model (`algorithm/water`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Protocol

from field_shift.algorithm.diagnostic.parcel_diagnostic import FieldMeasures
from field_shift.algorithm.sources.data_source import DataSource
from field_shift.algorithm.twins.soil_comparison import Soil
from field_shift.algorithm.weather.daily_weather import DailyWeather

SOIL_TEST_SOURCE: Final = "Votre analyse de sol"
FIELD_MEASURES_KEY: Final = "fieldMeasures"


@dataclass(frozen=True)
class SectionPlace:
    """Where a section is.

    `ring` is its outline, a closed ring of (lon, lat) points, when the farmer drew it; else it is
    empty and (lat, lon) is the point of the farm."""

    id: str
    lat: float
    lon: float
    ring: tuple[tuple[float, float], ...] = ()


@dataclass(frozen=True)
class FieldData:
    """What is known about the ground of a section, and where each value comes from."""

    measures: FieldMeasures
    soil: Soil
    soil_source: str
    measures_source: str = ""


class FieldDataUnavailableError(RuntimeError):
    """A data service could not give a measure of a section (the plan answers 502)."""


class FieldDataSource(Protocol):
    #: Where the measures come from (shown in the plan, key FIELD_MEASURES_KEY).
    source: DataSource

    def field_data(
        self, section: SectionPlace, soil_test: Soil | None, weather: DailyWeather
    ) -> FieldData:
        """Measures and soil of a section; a soil test of the farmer replaces SoilGrids.
        `weather` is the daily weather of the farm (NASA POWER). Raises
        FieldDataUnavailableError."""
        ...
