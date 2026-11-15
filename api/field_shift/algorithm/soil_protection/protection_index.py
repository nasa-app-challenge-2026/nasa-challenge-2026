"""Rotation Protection Index (RPI): the theoretical protection a rotation gives to the soil.

    SC   intrinsic score of a crop      = (infiltration + erosion + cover scores) / 3
    WSC  score weighted by time         = SC × months of the crop / months of the simulation
    RPI  index of the rotation          = sum of the WSC of every phase

Bare soil and fallow count as a phase with the lowest score (1), so the RPI goes from 1 to 5:

    1.0 to 2.4   high erosion risk, poor infiltration (degradation alert)
    2.5 to 3.9   moderate protection
    4.0 to 5.0   excellent protection, the soil structure regenerates

The *adjusted* RPI is the same sum with the scores brought down to what the satellites see on the
field (step 3 of the pipeline): the cover score follows the vigour of the canopy (MODIS NDVI),
the infiltration score follows the activity of the roots (MODIS ET / PET). A score of 1 cannot go
lower: a crop without vigour protects like bare soil. At full vigour both indices are equal.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from field_shift.algorithm.config.soil_protection import (
    BARE_SOIL_SCORE,
    RPI_EXCELLENT_FROM,
    RPI_MODERATE_FROM,
)
from field_shift.algorithm.rotation.rotation import RotationPhase
from field_shift.algorithm.soil_protection.site_conditions import SiteConditions


class ProtectionClass(StrEnum):
    """The three classes of the RPI."""

    HIGH_RISK = "risque-eleve"
    MODERATE = "moderee"
    EXCELLENT = "excellente"


def protection_class(rpi: float) -> ProtectionClass:
    """The class of an RPI (see the module documentation)."""
    if rpi >= RPI_EXCELLENT_FROM:
        return ProtectionClass.EXCELLENT
    if rpi >= RPI_MODERATE_FROM:
        return ProtectionClass.MODERATE
    return ProtectionClass.HIGH_RISK


@dataclass(frozen=True)
class PhaseScore:
    """The line of one phase in the RPI table.

    crop_id         the crop in place (None: bare soil)
    months          months the phase lasts within the simulation
    intrinsic       SC, the theoretical score of the phase (1 to 5)
    adjusted        SC with the cover and infiltration scores adjusted to the measured vigour
    weighted        WSC = intrinsic × share of the simulation time
    """

    crop_id: str | None
    months: float
    intrinsic: float
    adjusted: float
    weighted: float


@dataclass(frozen=True)
class ProtectionIndex:
    """The RPI of a rotation over a simulation, with the table it comes from."""

    rpi: float
    adjusted_rpi: float
    phases: tuple[PhaseScore, ...]

    @property
    def protection_class(self) -> ProtectionClass:
        """Class of the adjusted index: what the field really gets."""
        return protection_class(self.adjusted_rpi)


def _toward_bare(score: float, vigour: float) -> float:
    """A score between bare soil (vigour 0) and its theoretical value (vigour 1)."""
    return BARE_SOIL_SCORE + (score - BARE_SOIL_SCORE) * vigour


def intrinsic_scores(phase: RotationPhase, site: SiteConditions) -> tuple[float, float]:
    """(SC, adjusted SC) of a phase. Bare soil and fallow have the lowest score on both."""
    profile = phase.profile
    if profile is None or phase.is_bare:
        return BARE_SOIL_SCORE, BARE_SOIL_SCORE
    adjusted = (
        _toward_bare(profile.infiltration, site.root_vigour)
        + profile.residue
        + _toward_bare(profile.cover, site.canopy_vigour)
    ) / 3
    return profile.intrinsic_score, adjusted


def protection_index(timeline: Sequence[RotationPhase], site: SiteConditions) -> ProtectionIndex:
    """The RPI of the phases a field goes through during a simulation (`Rotation.timeline`)."""
    total_months = sum(phase.months for phase in timeline)
    if total_months <= 0:
        raise ValueError("the timeline of a rotation cannot be empty")
    rows: list[PhaseScore] = []
    rpi = adjusted_rpi = 0.0
    for phase in timeline:
        share = phase.months / total_months
        intrinsic, adjusted = intrinsic_scores(phase, site)
        rows.append(PhaseScore(phase.crop_id, phase.months, intrinsic, adjusted, intrinsic * share))
        rpi += intrinsic * share
        adjusted_rpi += adjusted * share
    return ProtectionIndex(rpi, adjusted_rpi, tuple(rows))
