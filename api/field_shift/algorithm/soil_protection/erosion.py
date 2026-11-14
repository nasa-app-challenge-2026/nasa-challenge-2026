"""Soil loss of a rotation with the structure of the Revised Universal Soil Loss Equation:

    A = R × K × LS × C × P          (t/ha/year)

    R   erosivity of the rain          from GPM IMERG, or estimated from the annual rain
    K   erodibility of the soil        from SSURGO, or estimated from texture and organic matter
    LS  slope length and steepness     from SRTM
    C   cover and management           from the rotation: this is what the ranking compares
    P   support practices              contouring, strips, terraces (1 without any)

RUSLE2 is "a guide to conservation planning rather than a precise estimator of soil loss" (RUSLE2
handbook): the value ranks rotations on a field, it does not predict the tonnes that will leave it.
The model covers sheet and rill erosion by rain only (no gullies, no snowmelt, no wind).

Simplifications against RUSLE2, which integrates day by day:
  - C is weighted by time, not by the distribution of the erosivity through the year (a crop that
    covers the soil during the most erosive months protects more than computed here);
  - K does not vary with the season; roughness and ridges are ignored;
  - a crop has one mean canopy and one residue cover for its whole season.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from field_shift.algorithm.config.soil_protection import (
    CANOPY_COVER_ANNUAL,
    CANOPY_COVER_DENSE,
    CANOPY_FALL_HEIGHT_M,
    CANOPY_HEIGHT_DECAY_PER_FT,
    CONSOLIDATED_SOIL_LOSS_RATIO,
    CONSOLIDATION_YEARS,
    EROSIVITY_RAIN_BREAK_MM,
    FEET_PER_METRE,
    K_US_TO_SI,
    MAX_SLOPE_LENGTH_M,
    MAX_SLOPE_PCT,
    ORGANIC_MATTER_PER_CARBON,
    RESIDUE_COVER_PCT_BY_SCORE,
    RESIDUE_HALF_LIFE_MONTHS,
    SOIL_LOSS_TOLERANCE_T_HA_YEAR,
    STEEPNESS_BREAK_PCT,
    SURFACE_COVER_EFFECTIVENESS,
    UNIT_PLOT_LENGTH_M,
)
from field_shift.algorithm.rotation.rotation import RotationPhase
from field_shift.algorithm.soil_protection.site_conditions import SiteConditions
from field_shift.reference.planning import MONTHS_PER_YEAR
from field_shift.reference.soil_protection import CoverKind, SoilProtectionProfile

# --- LS: topography -------------------------------------------------------------------------------


def slope_steepness_factor(slope_pct: float) -> float:
    """S: effect of the steepness, 1 on the 9 % unit plot (AH703, chapter 4).

    S = 10.8 sin θ + 0.03 below 9 %,  16.8 sin θ − 0.50 from 9 %.
    """
    sine = math.sin(math.atan(slope_pct / 100))
    if slope_pct < STEEPNESS_BREAK_PCT:
        return 10.8 * sine + 0.03
    return 16.8 * sine - 0.50


def slope_length_factor(slope_length_m: float, slope_pct: float) -> float:
    """L: effect of the slope length, 1 on the 22.13 m (72.6 ft) unit plot (AH703, ch. 4).

    L = (λ / 22.13)^m,  m = β / (1 + β),  β = (sin θ / 0.0896) / (3 (sin θ)^0.8 + 0.56)

    β is the ratio of rill to interrill erosion: on a flat field the erosion is interrill, the
    length hardly matters (m → 0); on a steep one, rills make it grow with the length.
    """
    sine = math.sin(math.atan(slope_pct / 100))
    rill_to_interrill = (sine / 0.0896) / (3 * sine**0.8 + 0.56)
    exponent = rill_to_interrill / (1 + rill_to_interrill)
    return (slope_length_m / UNIT_PLOT_LENGTH_M) ** exponent


def topographic_factor(slope_pct: float, slope_length_m: float) -> float:
    """LS. The slope is bounded to what RUSLE2 accepts: 0 to 100 %, at most 1000 ft long."""
    slope = min(max(slope_pct, 0.0), MAX_SLOPE_PCT)
    length = min(max(slope_length_m, 0.0), MAX_SLOPE_LENGTH_M)
    return slope_length_factor(length, slope) * slope_steepness_factor(slope)


# --- R and K --------------------------------------------------------------------------------------


def erosivity_from_annual_rain(annual_rain_mm: float) -> float:
    """R (MJ·mm/(ha·h·year)) estimated from the mean annual rain P in mm (Renard and Freimund,
    1994, fitted on the stations of the continental United States):

        R = 0.04830 P^1.610                       P ≤ 850 mm
        R = 587.8 − 1.219 P + 0.004105 P²         P > 850 mm

    A rough estimate (it ignores how intense the storms are): the R computed from the 30-minute
    intensities of GPM IMERG replaces it as soon as that source is configured.
    """
    rain = max(annual_rain_mm, 0.0)
    if rain <= EROSIVITY_RAIN_BREAK_MM:
        return 0.04830 * rain**1.610
    return 587.8 - 1.219 * rain + 0.004105 * rain**2


def erodibility_from_texture(
    sand_pct: float, silt_pct: float, clay_pct: float, organic_matter_pct: float
) -> float:
    """K (t·ha·h/(ha·MJ·mm)) estimated from the texture and the organic matter (EPIC equation,
    Williams 1995), for the soils SSURGO does not describe:

        K_US = f_sand × f_clay-silt × f_organic-carbon × f_high-sand

    Silty soils erode most; clay resists detachment; sand lets the water in. The organic matter is
    the *inherent* one: the RUSLE2 handbook forbids lowering K for the organic matter a rotation
    builds, since that effect is already in the C factor.
    """
    carbon = max(organic_matter_pct, 0.0) / ORGANIC_MATTER_PER_CARBON
    fines = clay_pct + silt_pct
    # Pure sand has no fines: nothing to divide by, and no silt to erode.
    clay_silt_term = 0.0 if fines <= 0 else (silt_pct / fines) ** 0.3
    sand_term = 0.2 + 0.3 * math.exp(-0.256 * sand_pct * (1 - silt_pct / 100))
    carbon_term = 1 - 0.25 * carbon / (carbon + math.exp(3.72 - 2.95 * carbon))
    not_sand = 1 - sand_pct / 100
    high_sand_term = 1 - 0.7 * not_sand / (not_sand + math.exp(-5.51 + 22.9 * not_sand))
    return sand_term * clay_silt_term * carbon_term * high_sand_term * K_US_TO_SI


# --- C: cover and management ----------------------------------------------------------------------


def residue_cover_pct(profile: SoilProtectionProfile) -> float:
    """Ground cover (%) the residue of a crop gives, from its residue score."""
    return RESIDUE_COVER_PCT_BY_SCORE[profile.residue]


def surface_cover_subfactor(ground_cover_pct: float) -> float:
    """exp(−b·M): what is left of the soil loss under M % of ground cover (RUSLE2 handbook).
    "Ground cover is the single factor having the greatest effect on erosion"."""
    return math.exp(-SURFACE_COVER_EFFECTIVENESS * ground_cover_pct)


def canopy_subfactor(canopy_cover: float) -> float:
    """1 − Fc·exp(−0.1·H): what is left of the soil loss under a canopy covering the share Fc of
    the soil, the drops falling again from the height H in feet (AH703, chapter 5)."""
    fall_height_ft = CANOPY_FALL_HEIGHT_M * FEET_PER_METRE
    return 1 - canopy_cover * math.exp(-CANOPY_HEIGHT_DECAY_PER_FT * fall_height_ft)


def consolidation_subfactor(years_undisturbed: float) -> float:
    """Mean soil loss ratio of a soil left untilled for `years_undisturbed` (a perennial stand).

    The ratio goes linearly from 1 (just tilled) to 0.45 (fully consolidated) in seven years, then
    stays there; the value returned is its mean over the stand.
    """
    full_drop = 1 - CONSOLIDATED_SOIL_LOSS_RATIO
    if years_undisturbed <= CONSOLIDATION_YEARS:
        return 1 - full_drop * years_undisturbed / (2 * CONSOLIDATION_YEARS)
    consolidating = CONSOLIDATION_YEARS * (1 - full_drop / 2)
    consolidated = (years_undisturbed - CONSOLIDATION_YEARS) * CONSOLIDATED_SOIL_LOSS_RATIO
    return (consolidating + consolidated) / years_undisturbed


def decayed_residue_pct(residue_pct: float, months: float) -> float:
    """Residue cover left after `months` of decay (it halves every half-life)."""
    return residue_pct * 0.5 ** (months / RESIDUE_HALF_LIFE_MONTHS)


def bare_soil_loss_ratio(residue_pct: float, months: float) -> float:
    """Mean soil loss ratio of a bare soil window that starts with `residue_pct` of residue cover.

    No canopy; the residue of the last crop still protects the soil and decays month after month
    (mean of the surface cover subfactor at the middle of each month).
    """
    steps = max(1, math.ceil(months))
    step_months = months / steps
    ratios = (
        surface_cover_subfactor(decayed_residue_pct(residue_pct, (step + 0.5) * step_months))
        for step in range(steps)
    )
    return sum(ratios) / steps


def crop_soil_loss_ratio(profile: SoilProtectionProfile, months: float, vigour: float) -> float:
    """Soil loss ratio while a crop holds the field: canopy × surface cover × consolidation.

    The canopy is the share of the soil a crop of this kind covers, times the vigour seen by the
    satellites (NDVI). Only perennials consolidate the soil: the others are tilled or sown again.
    """
    dense = profile.kind in (CoverKind.PERENNIAL, CoverKind.COVER)
    canopy_cover = (CANOPY_COVER_DENSE if dense else CANOPY_COVER_ANNUAL) * vigour
    ratio = canopy_subfactor(canopy_cover) * surface_cover_subfactor(residue_cover_pct(profile))
    if profile.kind is CoverKind.PERENNIAL:
        ratio *= consolidation_subfactor(months / MONTHS_PER_YEAR)
    return ratio


def cover_management_factor(
    timeline: Sequence[RotationPhase], vigour: float = 1.0, initial_residue_pct: float = 0.0
) -> float:
    """C: the soil loss of the rotation divided by the loss of the same field kept bare and tilled.

    The time-weighted mean of the soil loss ratio of every phase:
      - a crop: see `crop_soil_loss_ratio`; it leaves its residue on the soil when it ends;
      - bare soil after a crop: the residue left decays (see `bare_soil_loss_ratio`);
      - a fallow: tilled bare soil, ratio 1, and the residue is buried.

    `initial_residue_pct` is the residue on the soil when the simulation starts.
    """
    total_months = sum(phase.months for phase in timeline)
    if total_months <= 0:
        raise ValueError("the timeline of a rotation cannot be empty")
    residue_pct = initial_residue_pct
    weighted_ratio = 0.0
    for phase in timeline:
        profile = phase.profile
        if profile is None:
            ratio = bare_soil_loss_ratio(residue_pct, phase.months)
            residue_pct = decayed_residue_pct(residue_pct, phase.months)
        elif profile.kind is CoverKind.FALLOW:
            ratio, residue_pct = 1.0, 0.0
        else:
            ratio = crop_soil_loss_ratio(profile, phase.months, vigour)
            residue_pct = residue_cover_pct(profile)
        weighted_ratio += ratio * phase.months
    return weighted_ratio / total_months


def residue_at_cycle_end(cycle: Sequence[RotationPhase]) -> float:
    """Residue cover (%) on the soil at the end of a cycle: what the next cycle starts with, and
    what the simulation is assumed to start with (the rotation is taken as already in place)."""
    residue_pct = 0.0
    for phase in cycle:
        profile = phase.profile
        if profile is None:
            residue_pct = decayed_residue_pct(residue_pct, phase.months)
        elif profile.kind is CoverKind.FALLOW:
            residue_pct = 0.0
        else:
            residue_pct = residue_cover_pct(profile)
    return residue_pct


# --- A: soil loss ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class ErosionEstimate:
    """The soil loss of a rotation on a section, and the five factors it comes from.

    soil_loss_t_ha_year   A = R·K·LS·C·P
    bare_soil_loss        the same field kept bare and tilled (C = 1): the worst case
    """

    r_factor: float
    k_factor: float
    ls_factor: float
    c_factor: float
    p_factor: float

    @property
    def soil_loss_t_ha_year(self) -> float:
        return self.bare_soil_loss_t_ha_year * self.c_factor

    @property
    def bare_soil_loss_t_ha_year(self) -> float:
        return self.r_factor * self.k_factor * self.ls_factor * self.p_factor

    @property
    def tolerance_ratio(self) -> float:
        """Soil loss divided by the soil loss tolerance T: above 1, the soil degrades."""
        return self.soil_loss_t_ha_year / SOIL_LOSS_TOLERANCE_T_HA_YEAR

    @property
    def score(self) -> float:
        """From 0 to 1: 1 without soil loss, 0.5 at the tolerance T, towards 0 far beyond.

        1 / (1 + A/T) never saturates, so two rotations far above T are still told apart.
        """
        return 1 / (1 + self.tolerance_ratio)


def estimate_erosion(
    timeline: Sequence[RotationPhase], site: SiteConditions, initial_residue_pct: float = 0.0
) -> ErosionEstimate:
    """The RUSLE factors of a rotation timeline on a section.

    R and K are taken from the site when a data source gave them, estimated otherwise.
    """
    r_factor = site.r_factor
    if r_factor is None:
        r_factor = erosivity_from_annual_rain(site.annual_rain_mm)
    k_factor = site.k_factor
    if k_factor is None:
        k_factor = erodibility_from_texture(
            site.sand_pct, site.silt_pct, site.clay_pct, site.organic_matter_pct
        )
    return ErosionEstimate(
        r_factor=r_factor,
        k_factor=k_factor,
        ls_factor=topographic_factor(site.slope_pct, site.slope_length_m),
        c_factor=cover_management_factor(timeline, site.canopy_vigour, initial_residue_pct),
        p_factor=site.support_practice_factor,
    )
