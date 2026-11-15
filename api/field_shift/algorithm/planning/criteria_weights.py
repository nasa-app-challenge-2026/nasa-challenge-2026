"""Weights of a cycle: the farmer's weights adjusted to the risks of the field (step 8).

protection_sol × (1 + erosion risk),  eau × (1 + water risk).

With the nine criteria of field_shift.py v5.1 (reference tests), the forage weight is also
multiplied by 0.3 when the farm has no livestock.
"""

from __future__ import annotations

from collections.abc import Mapping

from field_shift.algorithm.config.scoring import NO_LIVESTOCK_FORAGE_FACTOR
from field_shift.algorithm.diagnostic.parcel_diagnostic import Risks
from field_shift.reference.criteria import FORAGE_CRITERION, SOIL_CRITERION, WATER_CRITERION


def weights_for_cycle(
    base_weights: Mapping[str, float], risks: Risks, livestock: bool
) -> dict[str, float]:
    weights = dict(base_weights)
    weights[SOIL_CRITERION] *= 1 + risks.erosion
    weights[WATER_CRITERION] *= 1 + risks.water
    if FORAGE_CRITERION in weights and not livestock:
        weights[FORAGE_CRITERION] *= NO_LIVESTOCK_FORAGE_FACTOR
    return weights
