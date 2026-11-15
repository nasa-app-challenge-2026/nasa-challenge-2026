"""What the soil protection model knows about a section of a field: soil, relief, rain, and the
satellite measures that adjust the theory to what really happens there.

Pipeline of the specification, and the data each step reads:

    step 1  static properties   SoilGrids 2.0 (texture, organic carbon) + Copernicus DEM (slope)
    step 2  rotation timeline   the rotation itself (see `algorithm/rotation`)
    step 3  vigour adjustment   MODIS NDVI (canopy) + MODIS ET / PET (root activity)
    step 4  external forcing    NASA POWER (rain, storms, soil moisture)

There is NO default value: every variable comes from the request, from a data source, or from a
published model fed with those (Ksat, K and R, see `site_estimates`). A missing variable is an
error (`MissingSiteDataError`), never a silent guess.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, fields

from field_shift.algorithm.config.soil_protection import NDVI_BARE_SOIL, NDVI_FULL_CANOPY
from field_shift.algorithm.numerics.ratios import clamp01


@dataclass(frozen=True)
class SiteConditions:
    """The conditions of one section.

    Step 1, static
        slope_pct               slope steepness (%)
        slope_length_m          length of the slope the runoff travels (m)
        sand_pct, clay_pct      texture of the fine earth (%); silt is the rest
        organic_matter_pct      inherent organic matter (%)
        ksat_mm_h               saturated hydraulic conductivity (mm/h): the infiltration baseline
        k_factor                RUSLE soil erodibility K in SI units (t·ha·h/(ha·MJ·mm))
        support_practice_factor RUSLE P factor (contouring, strips, terraces): 1 = none

    Step 3, vigour
        ndvi                    mean NDVI of the growing season
        root_activity           actual / potential evapotranspiration, 0 to 1: how much of the
                                root system really works

    Step 4, forcing
        annual_rain_mm          mean annual rain (mm)
        r_factor                RUSLE erosivity R in SI units (MJ·mm/(ha·h·year))
        storm_intensity_mm_h    intensity of the storm the infiltration is compared with (mm/h)
        soil_saturation         relative saturation of the surface soil, 0 (dry) to 1 (saturated)
    """

    slope_pct: float
    slope_length_m: float
    sand_pct: float
    clay_pct: float
    organic_matter_pct: float
    ksat_mm_h: float
    k_factor: float
    support_practice_factor: float
    ndvi: float
    root_activity: float
    annual_rain_mm: float
    r_factor: float
    storm_intensity_mm_h: float
    soil_saturation: float

    @property
    def silt_pct(self) -> float:
        """What is neither sand nor clay (never negative, even with rounded soil tests)."""
        return max(0.0, 100.0 - self.sand_pct - self.clay_pct)

    @property
    def canopy_vigour(self) -> float:
        """How dense the canopy really is, from 0 (bare soil) to 1 (full vigour): linear between
        the NDVI of bare soil and the NDVI of a dense canopy."""
        return clamp01((self.ndvi - NDVI_BARE_SOIL) / (NDVI_FULL_CANOPY - NDVI_BARE_SOIL))

    @property
    def root_vigour(self) -> float:
        """How active the roots really are, from 0 to 1."""
        return clamp01(self.root_activity)


@dataclass(frozen=True)
class SiteVariable:
    """One value of `SiteConditions` as the outside world sees it: its unit, the range a valid
    value lies in (a section or a data source giving a value outside is refused) and a label for
    the reports."""

    key: str
    label: str
    unit: str
    minimum: float
    maximum: float

    def accepts(self, value: float) -> bool:
        """True for a real number within the range (NaN and fill values such as -999 are not)."""
        return self.minimum <= value <= self.maximum


#: Every value of `SiteConditions`, by field name. The keys are also the names used in the `site`
#: object of a section.
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

if set(SITE_VARIABLES) != {field.name for field in fields(SiteConditions)}:
    raise RuntimeError("SITE_VARIABLES and SiteConditions must name the same variables")

#: Where a value comes from when the section gave it in the request.
ORIGIN_SECTION = "section"


@dataclass(frozen=True)
class SiteReading:
    """One value of the conditions of a section and where it comes from.

    origin  "section", or the dataset or model it comes from ("SoilGrids 2.0 (ISRIC)")
    method  how it was computed, when it is not the value of the dataset as read (a conversion,
            a statistic, a model); empty for a value given or read as is
    """

    key: str
    value: float
    origin: str
    method: str = ""


class MissingSiteDataError(ValueError):
    """Some variables of a section are known neither from the request nor from a source."""

    def __init__(self, missing: Iterable[str]) -> None:
        self.missing = tuple(missing)
        labels = ", ".join(SITE_VARIABLES[key].label for key in self.missing)
        super().__init__(f"données de la section manquantes : {labels}")


def site_from_readings(readings: Iterable[SiteReading]) -> SiteConditions:
    """The conditions made of the readings (one per variable: a later reading of a variable
    replaces an earlier one).

    Raises MissingSiteDataError when a variable has no reading, ValueError when the texture adds
    up to more than 100 %.
    """
    values = {reading.key: reading.value for reading in readings}
    missing = [key for key in SITE_VARIABLES if key not in values]
    if missing:
        raise MissingSiteDataError(missing)
    check_texture(values["sand_pct"], values["clay_pct"])
    return SiteConditions(**{key: values[key] for key in SITE_VARIABLES})


def check_texture(sand_pct: float, clay_pct: float) -> None:
    """Raises ValueError when sand and clay add up to more than 100 % (one may come from the
    request and the other from a data service)."""
    if sand_pct + clay_pct > 100:
        raise ValueError("sable + argile ne peut pas dépasser 100 %")
