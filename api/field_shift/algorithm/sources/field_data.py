"""The satellite measures of the erosion (step 8) and the soil (step 5) of a field.

Real values: SRTM / NASADEM slope, GPM IMERG heavy rain days, MODIS / HLS bare soil days,
SoilGrids 2.0. The demo source gives FICTITIOUS values: the ones of the demo field of
field_shift.py, varying a little from one section to the next so that two sections do not look
identical. Nothing about water is here: it comes from the water model (`algorithm/water`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Protocol, TypeVar

from field_shift.algorithm.diagnostic.parcel_diagnostic import FieldMeasures
from field_shift.algorithm.twins.soil_comparison import Soil

T = TypeVar("T")

SOIL_TEST_SOURCE: Final = "Votre analyse de sol"
DEMO_SOIL_SOURCE: Final = "SoilGrids 2.0 (fictif)"
_HASH_MULTIPLIER: Final = 31
_HASH_MASK: Final = 0xFFFFFFFF
_HASH_BUCKETS: Final = 2001  # a shift from -1 to +1 in steps of 0.001
_HASH_CENTRE: Final = 1000


@dataclass(frozen=True)
class FieldData:
    """What is known about the ground of a section."""

    measures: FieldMeasures
    soil: Soil
    soil_source: str


class FieldDataSource(Protocol):
    def field_data(self, section_id: str, soil_test: Soil | None) -> FieldData:
        """Measures and soil of a section; a soil test of the farmer replaces SoilGrids."""
        ...


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

    def field_data(self, section_id: str, soil_test: Soil | None) -> FieldData:
        measures = _varied(
            REFERENCE_DEMO_MEASURES, _MEASURE_VARIATION, _MEASURE_DECIMALS, section_id
        )
        if soil_test is not None:
            return FieldData(measures, soil_test, SOIL_TEST_SOURCE)
        soil = _varied(_BASE_SOIL, _SOIL_VARIATION, _SOIL_DECIMALS, section_id)
        return FieldData(measures, soil, DEMO_SOIL_SOURCE)
