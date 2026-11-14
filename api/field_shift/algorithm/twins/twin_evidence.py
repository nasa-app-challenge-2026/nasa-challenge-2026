"""What steps 4 to 7 hand to the chain building (step 9b) for one cycle.

The crops grown in the twins, the successions observed there (crop A one year → crop B the next),
the value of each previous crop (in %, or unknown) and the mean sigma.
"""

from __future__ import annotations

from collections.abc import Iterable


class TwinEvidence:
    """Crops and successions observed in the twin fields of a cycle."""

    def __init__(
        self,
        crops: Iterable[str],
        successions: Iterable[tuple[str, str, float | None]],
        sigma_mean: float | None = None,
        twins: Iterable = (),
        top_rotations: Iterable[tuple[str, float]] = (),
    ) -> None:
        self.crops = frozenset(crops)
        # (previous, next) → value in %, or None when seen in fewer than 20 fields
        self._precrop_values: dict[tuple[str, str], float | None] = {
            (previous, next_crop): value for previous, next_crop, value in successions
        }
        #: Mean sigma of the twin fields, None when no field counts.
        self.sigma_mean = sigma_mean
        self.twins = list(twins)
        self.top_rotations = list(top_rotations)

    def is_grown(self, crop_id: str) -> bool:
        return crop_id in self.crops

    def is_observed(self, previous: str, next_crop: str) -> bool:
        """Was "previous → next" seen in the twins? A crop after itself always counts as seen."""
        return previous == next_crop or (previous, next_crop) in self._precrop_values

    def precrop_value(self, previous: str, next_crop: str) -> float | None:
        """Value (%) of `previous` for `next_crop`, or None when unknown (never seen, or seen in
        fewer than 20 fields)."""
        return self._precrop_values.get((previous, next_crop))
