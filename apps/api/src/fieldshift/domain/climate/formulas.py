"""Daily agroclimatic formulas. Pure functions, each tied to a published definition.

Source identifiers (``bourgeois_2012``, ``fao56`` ...) refer to ``data/reference/sources.yaml``;
the full derivations and limits are in ``docs/methodology.md``.
"""

from __future__ import annotations

import math

# --- Thermal time ------------------------------------------------------------

CHU_DAY_BASE_C = 10.0
"""Daytime base temperature of the crop heat unit (source: omafra_93_119, bourgeois_2012)."""

CHU_NIGHT_BASE_C = 4.44
"""Night-time base temperature of the crop heat unit, 40 °F (source: bourgeois_2012)."""


def daily_mean_from_extremes(t_max_c: float, t_min_c: float) -> float:
    """Daily mean used by degree-day methods: ``(Tmax + Tmin) / 2`` (source: aafc_agroclimate).

    Agroclimatic indices are defined on this mean, not on the 24-hour mean of the reanalysis.
    """
    return (t_max_c + t_min_c) / 2.0


def growing_degree_days(t_max_c: float, t_min_c: float, base_c: float) -> float:
    """Growing degree-days of one day: ``max(0, (Tmax + Tmin) / 2 - base)``.

    Standard method, no upper cap (source: aafc_agroclimate, omafra_fieldcropnews_2025).
    """
    return max(0.0, daily_mean_from_extremes(t_max_c, t_min_c) - base_c)


def crop_heat_units(t_max_c: float, t_min_c: float) -> float:
    """Crop heat units (unités thermiques maïs, UTM) of one day.

    ``UTM = (Ymax + Ymin) / 2`` with
    ``Ymax = 3.33 (Tmax - 10) - 0.084 (Tmax - 10)²`` if ``Tmax >= 10 °C`` else 0, and
    ``Ymin = 1.8 (Tmin - 4.44)`` if ``Tmin >= 4.44 °C`` else 0
    (source: bourgeois_2012, equations unchanged from Laurence et al. 2002; same curve as
    omafra_93_119).

    The daytime curve peaks at 30 °C and turns negative above about 49.6 °C; it is floored at
    zero so that an absurd input can never subtract heat.
    """
    y_max = 0.0
    if t_max_c >= CHU_DAY_BASE_C:
        excess = t_max_c - CHU_DAY_BASE_C
        y_max = max(0.0, 3.33 * excess - 0.084 * excess * excess)
    y_min = 1.8 * (t_min_c - CHU_NIGHT_BASE_C) if t_min_c >= CHU_NIGHT_BASE_C else 0.0
    return (y_max + y_min) / 2.0


# --- Reference evapotranspiration (FAO-56) -----------------------------------

SOLAR_CONSTANT_MJ_M2_MIN = 0.0820
"""Gsc in FAO-56 equation 21."""

MJ_M2_DAY_TO_MM_DAY = 0.408
"""Equivalent evaporation of 1 MJ m⁻² day⁻¹ (FAO-56 equation 20)."""

HARGREAVES_COEFFICIENT = 0.0023
HARGREAVES_TEMPERATURE_OFFSET_C = 17.8


def extraterrestrial_radiation_mj(latitude_deg: float, day_of_year: int) -> float:
    """Extraterrestrial radiation Ra for a day and latitude, in MJ m⁻² day⁻¹.

    FAO-56 equations 21 to 25 (source: fao56). ``day_of_year`` is 1 on 1 January.
    Polar day and polar night are handled by clamping the sunset hour angle.
    """
    latitude_rad = math.radians(latitude_deg)
    inverse_relative_distance = 1.0 + 0.033 * math.cos(2.0 * math.pi * day_of_year / 365.0)
    declination = 0.409 * math.sin(2.0 * math.pi * day_of_year / 365.0 - 1.39)
    cos_sunset = -math.tan(latitude_rad) * math.tan(declination)
    sunset_hour_angle = math.acos(min(1.0, max(-1.0, cos_sunset)))
    radiation = (
        (24.0 * 60.0 / math.pi)
        * SOLAR_CONSTANT_MJ_M2_MIN
        * inverse_relative_distance
        * (
            sunset_hour_angle * math.sin(latitude_rad) * math.sin(declination)
            + math.cos(latitude_rad) * math.cos(declination) * math.sin(sunset_hour_angle)
        )
    )
    return max(0.0, radiation)


def hargreaves_reference_evapotranspiration_mm(
    t_max_c: float, t_min_c: float, latitude_deg: float, day_of_year: int
) -> float:
    """Reference evapotranspiration ETo of one day (mm), Hargreaves method.

    ``ETo = 0.0023 (Tmean + 17.8) (Tmax - Tmin)^0.5 Ra`` with Ra in mm/day
    (FAO-56 equation 52, source: fao56). Chosen because it only needs temperature; FAO-56
    notes that it tends to overpredict under high humidity, so the absolute level is
    indicative and comparisons between years are more reliable than the level itself.
    """
    radiation_mm = MJ_M2_DAY_TO_MM_DAY * extraterrestrial_radiation_mj(latitude_deg, day_of_year)
    t_mean_c = daily_mean_from_extremes(t_max_c, t_min_c)
    daily_range = max(0.0, t_max_c - t_min_c)
    evapotranspiration = (
        HARGREAVES_COEFFICIENT
        * (t_mean_c + HARGREAVES_TEMPERATURE_OFFSET_C)
        * math.sqrt(daily_range)
        * radiation_mm
    )
    return max(0.0, evapotranspiration)
