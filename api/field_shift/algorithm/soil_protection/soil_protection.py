"""The soil protection measure: what a rotation does to the erosion and to the infiltration of a
section, over a simulation.

It runs the four steps of the pipeline and gives its three results:

    Rotation Protection Index   the theory: scores of the crops weighted by time (protection_index)
    soil loss                   RUSLE on the section: slope, soil, rain, cover (erosion)
    effective infiltration      Ksat, roots and cover, soil moisture, against a storm (infiltration)

and one score from 0 to 1 for the ranking:

    score = 0.3 × (adjusted RPI − 1) / 4  +  0.4 × erosion score  +  0.3 × infiltrated share

The RPI says how good the rotation is in itself; the two others say what it changes on *this*
section: the same rotation is worth more on a steep silty field than on a flat sandy one.
"""

from __future__ import annotations

from dataclasses import dataclass

from field_shift.algorithm.config.soil_protection import (
    BARE_SOIL_SCORE,
    BEST_SCORE,
    SCORE_SHARE_EROSION,
    SCORE_SHARE_INFILTRATION,
    SCORE_SHARE_RPI,
)
from field_shift.algorithm.rotation.rotation import Rotation
from field_shift.algorithm.soil_protection.erosion import (
    ErosionEstimate,
    estimate_erosion,
    residue_at_cycle_end,
)
from field_shift.algorithm.soil_protection.infiltration import (
    InfiltrationEstimate,
    estimate_infiltration,
)
from field_shift.algorithm.soil_protection.protection_index import (
    ProtectionIndex,
    protection_index,
)
from field_shift.algorithm.soil_protection.site_conditions import SiteConditions
from field_shift.reference.planning import MONTHS_PER_YEAR


@dataclass(frozen=True)
class SoilProtection:
    """The soil protection of one rotation on one section."""

    simulation_months: float
    index: ProtectionIndex
    erosion: ErosionEstimate
    infiltration: InfiltrationEstimate

    @property
    def rpi_score(self) -> float:
        """The adjusted RPI brought from its 1..5 range to 0..1."""
        return (self.index.adjusted_rpi - BARE_SOIL_SCORE) / (BEST_SCORE - BARE_SOIL_SCORE)

    @property
    def score(self) -> float:
        """Score of the measure, from 0 (bare soil on an eroding field) to 1."""
        return (
            SCORE_SHARE_RPI * self.rpi_score
            + SCORE_SHARE_EROSION * self.erosion.score
            + SCORE_SHARE_INFILTRATION * self.infiltration.infiltrated_share
        )

    @property
    def cumulative_soil_loss_t_ha(self) -> float:
        """Soil lost over the whole simulation (t/ha)."""
        return self.erosion.soil_loss_t_ha_year * self.simulation_months / MONTHS_PER_YEAR


def evaluate_soil_protection(
    rotation: Rotation, site: SiteConditions, simulation_months: float
) -> SoilProtection:
    """Soil protection of `rotation` on the section described by `site`, over the simulation.

    The rotation is taken as already in place when the simulation starts: the soil carries the
    residue the end of a cycle leaves.
    """
    timeline = rotation.timeline(simulation_months)
    return SoilProtection(
        simulation_months=simulation_months,
        index=protection_index(timeline, site),
        erosion=estimate_erosion(timeline, site, residue_at_cycle_end(rotation.phases)),
        infiltration=estimate_infiltration(timeline, site),
    )
