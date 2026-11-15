"""FICTITIOUS satellite measures and soil of a section, for the tests and the contract examples.

The values of the demo field of field_shift.py, varying a little from one section to the next so
that two sections do not look identical. The server never uses them: it reads the real measures
(`field_shift/data_access/field_measures.py`).
"""

from __future__ import annotations

from typing import Final, TypeVar

from field_shift.algorithm.diagnostic.parcel_diagnostic import FieldMeasures
from field_shift.algorithm.sources.data_source import DataSource
from field_shift.algorithm.sources.field_data import (
    FIELD_MEASURES_KEY,
    SOIL_TEST_SOURCE,
    FieldData,
    SectionPlace,
)
from field_shift.algorithm.twins.soil_comparison import Soil
from field_shift.algorithm.weather.daily_weather import DailyWeather

T = TypeVar("T")

DEMO_SOIL_SOURCE: Final = "SoilGrids 2.0 (fictif)"
DEMO_FIELD_SOURCE: Final = DataSource(
    FIELD_MEASURES_KEY, False, "Mesures satellites de l’érosion et sol fictifs"
)
_HASH_MULTIPLIER: Final = 31
_HASH_MASK: Final = 0xFFFFFFFF
_HASH_BUCKETS: Final = 2001  # a shift from -1 to +1 in steps of 0.001
_HASH_CENTRE: Final = 1000

#: The demo field of field_shift.py (the "MESURES_PARCELLE" constants).
REFERENCE_DEMO_MEASURES: Final = FieldMeasures(
    slope_pct=6,
    heavy_rain_days=6,
    bare_soil_days=120,
)
_MEASURE_VARIATION: Final = FieldMeasures(
    slope_pct=3,
    heavy_rain_days=2,
    bare_soil_days=30,
)
_MEASURE_DECIMALS: Final = FieldMeasures(1, 0, 0)
_BASE_SOIL: Final = Soil(clay_pct=30, sand_pct=25, organic_carbon=25, ph=6.5)
_SOIL_VARIATION: Final = Soil(clay_pct=8, sand_pct=12, organic_carbon=6, ph=0.4)
_SOIL_DECIMALS: Final = Soil(0, 0, 1, 1)


def _shift(section_id: str, name: str) -> float:
    """A number from −1 to 1 that depends only on the section and the measure (stable)."""
    value = 0
    for char in f"{section_id}:{name}":
        value = (value * _HASH_MULTIPLIER + ord(char)) & _HASH_MASK
    return ((value % _HASH_BUCKETS) - _HASH_CENTRE) / _HASH_CENTRE


def _varied(base: T, variation: T, decimals: T, section_id: str) -> T:
    """`base` moved by up to ± `variation` for this section, rounded to `decimals`."""
    values = {
        name: round(
            getattr(base, name) + getattr(variation, name) * _shift(section_id, name),
            getattr(decimals, name),
        )
        for name in vars(base)
    }
    return type(base)(**values)


class DemoFieldDataSource:
    """Fictitious measures and soil, stable for a section id."""

    source = DEMO_FIELD_SOURCE

    def field_data(
        self, section: SectionPlace, soil_test: Soil | None, weather: DailyWeather | None = None
    ) -> FieldData:
        measures = _varied(
            REFERENCE_DEMO_MEASURES, _MEASURE_VARIATION, _MEASURE_DECIMALS, section.id
        )
        if soil_test is not None:
            return FieldData(measures, soil_test, SOIL_TEST_SOURCE)
        soil = _varied(_BASE_SOIL, _SOIL_VARIATION, _SOIL_DECIMALS, section.id)
        return FieldData(measures, soil, DEMO_SOIL_SOURCE)
