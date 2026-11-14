"""After the last cycle, the robustness of each adopted chain.

It is played again in each of the following cycles (their climate, their twins, their return
delays) and its worst score is kept. If it becomes impossible in a future cycle, the app shows
"becomes infeasible later".
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from field_shift.algorithm.chain.chain_replayer import replay_chain
from field_shift.algorithm.chain.chain_scorer import score_chain
from field_shift.algorithm.chain.chain_search import delays_respected
from field_shift.algorithm.chain.chain_step import sheet_ids
from field_shift.algorithm.planning.cycle_plan import CyclePlan, Decision


def add_robustness(cycles: Sequence[CyclePlan]) -> None:
    """Fill `robustness` and `becomes_infeasible_later` of every adopted cycle (mutates them).

    A chain kept from the previous cycle is not adopted again: its robustness is that of the
    cycle where it was adopted."""
    for i, cycle in enumerate(cycles):
        cycle.robustness = None
        cycle.becomes_infeasible_later = False
        if cycle.chosen is None or (cycle.decision is Decision.KEEP and i > 0):
            continue
        ids = sheet_ids(cycle.chosen.chain)
        scores = [cycle.chosen.score]
        for later in cycles[i + 1 :]:
            chain = replay_chain(ids, later.context)
            if chain is not None and not delays_respected(chain, later.context, closed=True):
                chain = None  # becomes infeasible: its return delays no longer hold
            scores.append(score_chain(chain, later.context).score if chain else math.nan)
        cycle.becomes_infeasible_later = any(math.isnan(s) for s in scores)
        cycle.robustness = None if cycle.becomes_infeasible_later else min(scores)
