"""Step 8: the weak points of a field, redone for every cycle, to give more weight to the criteria
concerned.

    Erosion  slope (SRTM / NASADEM) 50 %, days with 25 mm of rain or more (GPM IMERG) 30 %,
             days of bare soil (MODIS / HLS NDVI) 20 %
    Water    the water pressure of the farm during the cycle, from the water model
             (`algorithm/water`): aridity of the weather of the cycle, summer rain drop,
             groundwater, measured stress (dry root zone, evaporative stress)

The satellite measures of the erosion describe the field today and do not change from one cycle
to the next. The water pressure is computed on the weather of each cycle (the mean of the climate
models in the long term). An irrigated field keeps 40 % of its water risk.
"""

from __future__ import annotations

from dataclasses import dataclass

from field_shift.algorithm.config.scoring import (
    EROSION_BARE_SOIL,
    EROSION_HEAVY_RAIN,
    EROSION_SLOPE,
    IRRIGATED_WATER_RISK_FACTOR,
    RiskTerm,
)
from field_shift.algorithm.numerics.ratios import clamp01
from field_shift.algorithm.water.water_model import WaterPressure


@dataclass(frozen=True)
class FieldMeasures:
    """Satellite measures of a field (erosion).

    slope_pct         slope (%)
    heavy_rain_days   days a year with 25 mm of rain or more
    bare_soil_days    days a year with bare soil
    """

    slope_pct: float
    heavy_rain_days: float
    bare_soil_days: float


@dataclass(frozen=True)
class Risks:
    """The two risks of a field during a cycle, from 0 to 1."""

    erosion: float
    water: float


def _term(term: RiskTerm, measure: float) -> float:
    return term.share * clamp01(measure / term.saturation)


class ParcelDiagnostic:
    """Erosion and water risks of one field."""

    def __init__(self, measures: FieldMeasures, irrigated: bool = False) -> None:
        self.measures = measures
        self.irrigated = irrigated

    @property
    def erosion_risk(self) -> float:
        m = self.measures
        return (
            _term(EROSION_SLOPE, m.slope_pct)
            + _term(EROSION_HEAVY_RAIN, m.heavy_rain_days)
            + _term(EROSION_BARE_SOIL, m.bare_soil_days)
        )

    def water_risk(self, pressure: float) -> float:
        """Water risk of the field for a water pressure of the farm (0 to 1)."""
        return clamp01(pressure) * (IRRIGATED_WATER_RISK_FACTOR if self.irrigated else 1.0)

    def risks_for(self, water: WaterPressure) -> Risks:
        """The risks of a cycle, with the water pressure of its weather."""
        return Risks(erosion=self.erosion_risk, water=self.water_risk(water.pressure))
