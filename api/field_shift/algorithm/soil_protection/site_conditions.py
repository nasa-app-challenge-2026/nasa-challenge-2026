"""What the soil protection model knows about a section of a field: soil, relief, rain, and the
satellite measures that adjust the theory to what really happens there.

Pipeline of the specification, and the data each step reads:

    step 1  static properties   SSURGO (Ksat, organic matter, texture, K) + SRTM (slope)
    step 2  rotation timeline   the rotation itself (see `algorithm/rotation`)
    step 3  vigour adjustment   Landsat / MODIS NDVI (canopy) + ECOSTRESS (root activity)
    step 4  external forcing    GPM IMERG (rain, storms) + SMAP (soil moisture)

The values of steps 3 and 4 are optional: without them the model keeps the theoretical values.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from field_shift.algorithm.config.soil_protection import (
    DEFAULT_ANNUAL_RAIN_MM,
    DEFAULT_CLAY_PCT,
    DEFAULT_KSAT_MM_H,
    DEFAULT_ORGANIC_MATTER_PCT,
    DEFAULT_SAND_PCT,
    DEFAULT_SLOPE_LENGTH_M,
    DEFAULT_SLOPE_PCT,
    DEFAULT_STORM_INTENSITY_MM_H,
    NDVI_BARE_SOIL,
    NDVI_FULL_CANOPY,
)
from field_shift.algorithm.numerics.ratios import clamp01


@dataclass(frozen=True)
class SiteConditions:
    """The conditions of one section. Defaults describe a loam on a gentle slope.

    Step 1, static (SSURGO, SRTM)
        slope_pct               slope steepness (%)
        slope_length_m          length of the slope the runoff travels (m)
        sand_pct, clay_pct      texture of the fine earth (%); silt is the rest
        organic_matter_pct      inherent organic matter (%)
        ksat_mm_h               saturated hydraulic conductivity (mm/h): the infiltration baseline
        k_factor                RUSLE soil erodibility K in SI units (t·ha·h/(ha·MJ·mm)); None to
                                estimate it from the texture and the organic matter
        support_practice_factor RUSLE P factor (contouring, strips, terraces): 1 = none

    Step 3, vigour (optional)
        ndvi                    mean NDVI of the growing season (Landsat, MODIS / VIIRS)
        root_activity           actual / potential evapotranspiration, 0 to 1 (ECOSTRESS): how much
                                of the root system really works

    Step 4, forcing
        annual_rain_mm          mean annual rain (mm)
        r_factor                RUSLE erosivity R in SI units (MJ·mm/(ha·h·year)), from the storm
                                intensities of GPM IMERG; None to estimate it from the annual rain
        storm_intensity_mm_h    intensity of the storm the infiltration is compared with (mm/h)
        soil_saturation         relative saturation of the surface soil, 0 (dry) to 1 (saturated),
                                from SMAP; None when unknown
    """

    slope_pct: float = DEFAULT_SLOPE_PCT
    slope_length_m: float = DEFAULT_SLOPE_LENGTH_M
    sand_pct: float = DEFAULT_SAND_PCT
    clay_pct: float = DEFAULT_CLAY_PCT
    organic_matter_pct: float = DEFAULT_ORGANIC_MATTER_PCT
    ksat_mm_h: float = DEFAULT_KSAT_MM_H
    k_factor: float | None = None
    support_practice_factor: float = 1.0
    ndvi: float | None = None
    root_activity: float | None = None
    annual_rain_mm: float = DEFAULT_ANNUAL_RAIN_MM
    r_factor: float | None = None
    storm_intensity_mm_h: float = DEFAULT_STORM_INTENSITY_MM_H
    soil_saturation: float | None = None

    @property
    def silt_pct(self) -> float:
        """What is neither sand nor clay (never negative, even with rounded soil tests)."""
        return max(0.0, 100.0 - self.sand_pct - self.clay_pct)

    @property
    def canopy_vigour(self) -> float:
        """How dense the canopy really is, from 0 (bare soil) to 1 (full vigour).

        Linear between the NDVI of bare soil and the NDVI of a dense canopy. Without NDVI the
        crops are taken at full vigour: the theoretical scores are kept.
        """
        if self.ndvi is None:
            return 1.0
        return clamp01((self.ndvi - NDVI_BARE_SOIL) / (NDVI_FULL_CANOPY - NDVI_BARE_SOIL))

    @property
    def root_vigour(self) -> float:
        """How active the roots really are, from 0 to 1 (1 without ECOSTRESS measure)."""
        return 1.0 if self.root_activity is None else clamp01(self.root_activity)


@dataclass(frozen=True)
class SiteVariable:
    """One value of `SiteConditions` as the outside world sees it: its unit, the range a valid
    value lies in (a section or a data source giving a value outside is refused or ignored) and a
    label for the reports."""

    key: str
    label: str
    unit: str
    minimum: float
    maximum: float

    def accepts(self, value: float) -> bool:
        """True for a real number within the range (NaN and fill values such as -999 are not)."""
        return self.minimum <= value <= self.maximum


#: Every value of `SiteConditions`, by field name. The keys are also the names used in the
#: configuration of the data sources and in the `site` object of a section.
SITE_VARIABLES: dict[str, SiteVariable] = {
    variable.key: variable
    for variable in (
        SiteVariable("slope_pct", "Pente", "%", 0, 100),
        SiteVariable("slope_length_m", "Longueur de pente", "m", 0.3, 2000),
        SiteVariable("sand_pct", "Sable", "%", 0, 100),
        SiteVariable("clay_pct", "Argile", "%", 0, 100),
        SiteVariable("organic_matter_pct", "Matière organique", "%", 0, 100),
        SiteVariable("ksat_mm_h", "Conductivité hydraulique à saturation (Ksat)", "mm/h", 0, 2000),
        SiteVariable("k_factor", "Érodibilité du sol (K)", "t·ha·h/(ha·MJ·mm)", 0, 0.1),
        SiteVariable("support_practice_factor", "Pratiques de conservation (P)", "", 0, 1),
        SiteVariable("ndvi", "NDVI de la saison de croissance", "", -1, 1),
        SiteVariable("root_activity", "Activité racinaire (ET réelle / potentielle)", "", 0, 2),
        SiteVariable("annual_rain_mm", "Pluie annuelle", "mm", 0, 12000),
        SiteVariable("r_factor", "Érosivité des pluies (R)", "MJ·mm/(ha·h·an)", 0, 50000),
        SiteVariable("storm_intensity_mm_h", "Intensité de l’averse de référence", "mm/h", 0, 500),
        SiteVariable("soil_saturation", "Saturation du sol en surface", "", 0, 1),
    )
}

#: Where a value comes from when nobody gave it.
ORIGIN_DEFAULT = "valeur par défaut"
#: Where a value comes from when the section gave it in the request.
ORIGIN_SECTION = "section"


@dataclass(frozen=True)
class SiteReading:
    """One value of the conditions of a section and where it comes from (the section itself, a
    data source such as "SRTM", or the default)."""

    key: str
    value: float
    origin: str


def site_from_readings(readings: Iterable[SiteReading]) -> SiteConditions:
    """The conditions made of the readings; what no reading gives keeps its default."""
    return SiteConditions(**{reading.key: reading.value for reading in readings})


def default_readings() -> list[SiteReading]:
    """The default value of every variable that has one (those the model always needs)."""
    defaults = SiteConditions()
    return [
        SiteReading(key, getattr(defaults, key), ORIGIN_DEFAULT)
        for key in SITE_VARIABLES
        if getattr(defaults, key) is not None
    ]
