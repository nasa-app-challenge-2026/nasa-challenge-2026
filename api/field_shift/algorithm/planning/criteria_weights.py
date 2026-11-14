"""Weights of a cycle: the farmer's weights adjusted to the risks of the field (step 8).

erosion × (1 + erosion risk),  water × (1 + water risk),  forage × 0.3 without livestock.
"""

from __future__ import annotations

from collections.abc import Mapping

from field_shift.algorithm.config.scoring import NO_LIVESTOCK_FORAGE_FACTOR
from field_shift.algorithm.diagnostic.parcel_diagnostic import Risks


def weights_for_cycle(
    base_weights: Mapping[str, float], risks: Risks, livestock: bool
) -> dict[str, float]:
    weights = dict(base_weights)
    weights["erosion"] *= 1 + risks.erosion
    weights["eau"] *= 1 + risks.water
    if not livestock:
        weights["fourrage"] *= NO_LIVESTOCK_FORAGE_FACTOR
    return weights
