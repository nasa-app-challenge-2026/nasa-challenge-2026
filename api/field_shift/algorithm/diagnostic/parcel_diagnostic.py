"""Step 8: the weak points of a field, redone for every cycle, to give more weight to the criteria
concerned.

    Erosion  slope (SRTM / NASADEM) 50 %, days with 25 mm of rain or more (GPM IMERG) 30 %,
             days of bare soil (MODIS / HLS NDVI) 20 %
    Water    summer plant stress (ECOSTRESS ESI) 40 %, root-zone drought (SMAP L4) 30 %,
             summer rain drop forecast for the cycle (step 3) 20 %,
             regional water storage drop (GRACE-FO) 10 %

The satellite measures describe the field today and do not change from one cycle to the next;
only the rain drop forecast does (0 % in the short term, since rain is not extended; mean of the
models in the long term). An irrigated field keeps 40 % of its water risk.
"""

from __future__ import annotations

from dataclasses import dataclass

from field_shift.algorithm.climate.cycle_climate import CycleClimate
from field_shift.algorithm.config.scoring import (
    EROSION_BARE_SOIL,
    EROSION_HEAVY_RAIN,
    EROSION_SLOPE,
    IRRIGATED_WATER_RISK_FACTOR,
    WATER_DROUGHT_SHARE,
    WATER_GROUNDWATER_DROP,
    WATER_RAIN_DROP,
    WATER_STRESS_NONE_ABOVE,
    WATER_STRESS_RANGE,
    WATER_STRESS_SHARE,
    RiskTerm,
)
from field_shift.algorithm.numerics.ratios import clamp01


@dataclass(frozen=True)
class FieldMeasures:
    """Satellite measures of a field.

    slope_pct                       slope (%)
    heavy_rain_days                 days a year with 25 mm of rain or more
    bare_soil_days                  days a year with bare soil
    summer_stress_index             ECOSTRESS evaporative stress index in summer (1 = no stress)
    root_zone_drought               SMAP L4 root-zone drought, 0 to 1
    groundwater_trend_cm_per_year   GRACE-FO water storage trend (negative = drop)
    """

    slope_pct: float
    heavy_rain_days: float
    bare_soil_days: float
    summer_stress_index: float
    root_zone_drought: float
    groundwater_trend_cm_per_year: float


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

    def water_risk(self, summer_rain_change_pct: float) -> float:
        """Water risk with the summer rain change forecast for a cycle (%)."""
        m = self.measures
        stress = clamp01((WATER_STRESS_NONE_ABOVE - m.summer_stress_index) / WATER_STRESS_RANGE)
        raw = (
            WATER_STRESS_SHARE * stress
            + WATER_DROUGHT_SHARE * clamp01(m.root_zone_drought)
            + _term(WATER_RAIN_DROP, -summer_rain_change_pct)
            + _term(WATER_GROUNDWATER_DROP, -m.groundwater_trend_cm_per_year)
        )
        return raw * (IRRIGATED_WATER_RISK_FACTOR if self.irrigated else 1.0)

    def risks_for(self, climate: CycleClimate) -> Risks:
        return Risks(
            erosion=self.erosion_risk,
            water=self.water_risk(climate.summer_rain_change_pct),
        )
