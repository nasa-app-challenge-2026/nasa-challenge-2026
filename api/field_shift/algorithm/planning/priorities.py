"""Step 1, block D: from the farmer's ranking of the priorities to their weights.

Rank order centroid method. With the four priorities ranked, the weights are 0.52 / 0.27 / 0.15 /
0.06. A priority left unranked keeps a share (25 %) of the smallest weight. The weights are then
adjusted to the risks of each field (see `criteria_weights.py`).

The criteria are the four priorities (`CRITERIA_IDS`); the reference tests give the nine criteria
of field_shift.py v5.1 instead.
"""

from __future__ import annotations

from collections.abc import Sequence

from field_shift.reference.criteria import CRITERIA_IDS
from field_shift.reference.planning import UNRANKED_WEIGHT_SHARE


def rank_order_centroid(rank: int, count: int) -> float:
    """Weight of the criterion ranked `rank` (0 = first) among `count` ranked criteria."""
    return sum(1 / j for j in range(rank + 1, count + 1)) / count


def weights_from_ranking(
    ranking: Sequence[str],
    criteria: Sequence[str] = CRITERIA_IDS,
    unranked_share: float = UNRANKED_WEIGHT_SHARE,
) -> dict[str, float]:
    """Weight of every criterion of `criteria`. Without any ranking, they all weigh the same."""
    ranked = list(dict.fromkeys(c for c in ranking if c in criteria))
    if not ranked:
        return dict.fromkeys(criteria, 1.0)
    weights = {c: rank_order_centroid(i, len(ranked)) for i, c in enumerate(ranked)}
    unranked_weight = unranked_share * min(weights.values())
    return {c: weights.get(c, unranked_weight) for c in criteria}
