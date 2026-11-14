"""Effective infiltration of a rotation: how much of a storm the soil of the section takes in.

    baseline     Ksat of the soil: the infiltration it can reach
    × rotation   the roots and the cover of the rotation open the soil (meta-analysis below)
    × moisture   a soil already wet takes less, whatever its roots
    = effective infiltration rate (mm/h), compared with the intensity of a storm

Effect of the rotation (Basche and DeLonge, PLOS ONE 2019, 89 field studies, 391 comparisons):
perennials raise the infiltration rate by 59.2 % (± 20.9) against annual crops, cover crops by
34.8 % (± 7.7) against bare soil. The gain is applied during the months the perennial or the cover
crop is in place, in proportion to the activity of its roots (ET / PET). The other practices of
the meta-analysis had no significant effect (no-till, crop rotation) and are not counted; annual
crops and bare soil are the control (no gain).

The meta-analysis found no effect of the duration of the experiments: the gain does not grow with
the years here either.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from field_shift.algorithm.config.soil_protection import (
    COVER_CROP_INFILTRATION_GAIN,
    PERENNIAL_INFILTRATION_GAIN,
    SATURATION_INFILTRATION_LOSS,
)
from field_shift.algorithm.numerics.ratios import clamp01
from field_shift.algorithm.rotation.rotation import RotationPhase
from field_shift.algorithm.soil_protection.site_conditions import SiteConditions
from field_shift.reference.soil_protection import CoverKind

#: Gain of the infiltration rate while a crop of each kind is in place.
INFILTRATION_GAIN_BY_KIND = {
    CoverKind.PERENNIAL: PERENNIAL_INFILTRATION_GAIN,
    CoverKind.COVER: COVER_CROP_INFILTRATION_GAIN,
    CoverKind.ANNUAL: 0.0,
    CoverKind.FALLOW: 0.0,
}


@dataclass(frozen=True)
class InfiltrationEstimate:
    """The infiltration of a section under a rotation.

    baseline_mm_h         Ksat of the soil
    rotation_multiplier   mean effect of the rotation over the simulation (1 = annual crops only)
    moisture_factor       what the soil moisture leaves of it (1 = dry)
    storm_intensity_mm_h  the storm the infiltration is compared with
    """

    baseline_mm_h: float
    rotation_multiplier: float
    moisture_factor: float
    storm_intensity_mm_h: float

    @property
    def potential_mm_h(self) -> float:
        """Infiltration rate the rotation gives to a soil that is not wet yet."""
        return self.baseline_mm_h * self.rotation_multiplier

    @property
    def effective_mm_h(self) -> float:
        """Infiltration rate with the soil moisture of the place."""
        return self.potential_mm_h * self.moisture_factor

    @property
    def gain_pct(self) -> float:
        """Change of the infiltration rate due to the rotation, in percent."""
        return 100 * (self.rotation_multiplier - 1)

    @property
    def infiltrated_share(self) -> float:
        """Share of the storm that enters the soil, from 0 to 1; the rest runs off and erodes.

        This is the score of the infiltration: 1 when the soil takes the whole storm.
        """
        if self.storm_intensity_mm_h <= 0:
            return 1.0
        return clamp01(self.effective_mm_h / self.storm_intensity_mm_h)


def rotation_multiplier(timeline: Sequence[RotationPhase], root_vigour: float = 1.0) -> float:
    """Mean multiplier of the infiltration rate over a rotation timeline.

    Each phase counts for its months: 1 + the gain of its kind × the activity of the roots.
    """
    total_months = sum(phase.months for phase in timeline)
    if total_months <= 0:
        raise ValueError("the timeline of a rotation cannot be empty")
    weighted = 0.0
    for phase in timeline:
        profile = phase.profile
        gain = 0.0 if profile is None else INFILTRATION_GAIN_BY_KIND[profile.kind]
        weighted += (1 + gain * root_vigour) * phase.months
    return weighted / total_months


def moisture_factor(soil_saturation: float) -> float:
    """What the soil moisture leaves of the infiltration: 1 on a dry soil, down to 0.1 on a
    saturated one."""
    return 1 - SATURATION_INFILTRATION_LOSS * clamp01(soil_saturation)


def estimate_infiltration(
    timeline: Sequence[RotationPhase], site: SiteConditions
) -> InfiltrationEstimate:
    """The infiltration of a section during a rotation timeline."""
    return InfiltrationEstimate(
        baseline_mm_h=site.ksat_mm_h,
        rotation_multiplier=rotation_multiplier(timeline, site.root_vigour),
        moisture_factor=moisture_factor(site.soil_saturation),
        storm_intensity_mm_h=site.storm_intensity_mm_h,
    )
