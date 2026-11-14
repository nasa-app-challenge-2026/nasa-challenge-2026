"""From the priorities of the user to the weight of each measure in the score of a rotation.

The priorities can be written in two ways:
  - weights, one number per measure: {"protection_sol": 3, "rendement": 1}. Only their proportions
    matter; a measure that is not named weighs nothing;
  - a ranking, the most important measure first: ["protection_sol", "rendement"]. The ranks become
    weights with the rank order centroid method, the one the plan uses for its nine criteria; an
    unranked measure keeps a quarter of the smallest weight.

Without priorities the four measures weigh the same. The weights returned always add up to 1.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from field_shift.algorithm.planning.priorities import rank_order_centroid
from field_shift.reference.measures import MEASURE_IDS
from field_shift.reference.planning import UNRANKED_WEIGHT_SHARE

Priorities = Mapping[str, float] | Sequence[str] | None


def _normalised(weights: Mapping[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    return {measure: weights[measure] / total for measure in MEASURE_IDS}


def weights_from_ranking(ranking: Sequence[str]) -> dict[str, float]:
    """Weights of a ranking of measures (most important first)."""
    ranked = list(dict.fromkeys(ranking))
    weights = {measure: rank_order_centroid(i, len(ranked)) for i, measure in enumerate(ranked)}
    unranked_weight = UNRANKED_WEIGHT_SHARE * min(weights.values())
    return _normalised({measure: weights.get(measure, unranked_weight) for measure in MEASURE_IDS})


def measure_weights(priorities: Priorities) -> dict[str, float]:
    """Weight of each of the four measures, adding up to 1 (see the module documentation).

    Raises ValueError (message in French) for an unknown measure, a negative weight, or weights
    that are all zero.
    """
    if not priorities:
        return _normalised(dict.fromkeys(MEASURE_IDS, 1.0))
    unknown = [measure for measure in priorities if measure not in MEASURE_IDS]
    if unknown:
        raise ValueError(f"mesure inconnue : {', '.join(unknown)}")
    if not isinstance(priorities, Mapping):
        return weights_from_ranking(priorities)
    if any(weight < 0 for weight in priorities.values()):
        raise ValueError("un poids ne peut pas être négatif")
    if sum(priorities.values()) <= 0:
        raise ValueError("au moins une mesure doit avoir un poids supérieur à zéro")
    return _normalised({measure: priorities.get(measure, 0.0) for measure in MEASURE_IDS})
