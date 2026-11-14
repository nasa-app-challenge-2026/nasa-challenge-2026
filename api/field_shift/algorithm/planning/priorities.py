"""Step 1, block D: from the farmer's ranking of the criteria to their weights.

Rank order centroid method. With 5 ranked criteria the weights are 0.46 / 0.26 / 0.16 / 0.09 /
0.04. An unranked criterion keeps a share (25 %) of the smallest weight. The weights are then
adjusted to the risks of each field (see `criteria_weights.py`).
"""

from __future__ import annotations

from collections.abc import Sequence

from field_shift.reference.criteria import CRITERIA_IDS
from field_shift.reference.planning import UNRANKED_WEIGHT_SHARE


def rank_order_centroid(rank: int, count: int) -> float:
    """Weight of the criterion ranked `rank` (0 = first) among `count` ranked criteria."""
    return sum(1 / j for j in range(rank + 1, count + 1)) / count


def weights_from_ranking(
    ranking: Sequence[str], unranked_share: float = UNRANKED_WEIGHT_SHARE
) -> dict[str, float]:
    """Weight of every criterion. Without any ranking, all criteria weigh the same."""
    ranked = list(dict.fromkeys(c for c in ranking if c in CRITERIA_IDS))
    if not ranked:
        return dict.fromkeys(CRITERIA_IDS, 1.0)
    weights = {c: rank_order_centroid(i, len(ranked)) for i, c in enumerate(ranked)}
    unranked_weight = unranked_share * min(weights.values())
    return {c: weights.get(c, unranked_weight) for c in CRITERIA_IDS}
