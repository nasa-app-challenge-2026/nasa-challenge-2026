"""What the farmer told the app once for the whole farm (step 1).

His ranking of the four priorities, missing equipment, and his seed reserve (a list of seeds,
without quantities) with its mode.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from typing import Final

from field_shift.algorithm.planning.priorities import weights_from_ranking
from field_shift.reference.criteria import CRITERIA_IDS
from field_shift.reference.crops import SEED_IDS
from field_shift.reference.planning import ReserveMode

#: The cover crop the app sows automatically: needed in the reserve in "reserve only" mode.
AUTOMATIC_COVER_SEED: Final = "seigle"


@dataclass(frozen=True)
class FarmerProfile:
    """The farmer's choices for the whole farm.

    criteria   what the chains are scored on: the four priorities. The reference tests give the
               nine criteria of field_shift.py v5.1 (`V51_CRITERIA_IDS`) and, with them, whether
               the farm has livestock (it lowers the weight of the forage criterion).
    """

    ranking: tuple[str, ...]
    livestock: bool = False
    missing_equipment: frozenset[str] = frozenset()
    seeds: frozenset[str] = field(default_factory=lambda: frozenset(SEED_IDS))
    reserve_mode: ReserveMode = ReserveMode.PREFERRED
    criteria: tuple[str, ...] = CRITERIA_IDS

    @cached_property
    def base_weights(self) -> dict[str, float]:
        """Weights of the criteria from the ranking (rank order centroid)."""
        return weights_from_ranking(self.ranking, self.criteria)

    def covers_allowed(self) -> bool:
        """Automatic rye covers: always, unless "reserve only" without rye seeds."""
        return self.reserve_mode is not ReserveMode.ONLY or AUTOMATIC_COVER_SEED in self.seeds
