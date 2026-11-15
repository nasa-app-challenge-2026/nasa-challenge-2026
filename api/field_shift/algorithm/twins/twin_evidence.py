"""What steps 4 to 7 hand to the chain building (step 9b) for one cycle.

The crops grown in the twins, the successions observed there (crop A one year → crop B the next),
the value of each previous crop (in %, or unknown) and the mean sigma.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping


class TwinEvidence:
    """Crops and successions observed in the twin fields of a cycle."""

    def __init__(
        self,
        crops: Iterable[str],
        successions: Iterable[tuple[str, str, float | None]],
        sigma_mean: float | None = None,
        twins: Iterable = (),
        top_rotations: Iterable[tuple[str, float]] = (),
        unmeasured_value: float = 0.0,
        same_crop_values: Mapping[str, float] | None = None,
    ) -> None:
        self.crops = frozenset(crops)
        #: What an unknown succession counts in the yield criterion (%): neutral in
        #: field_shift.py v5.1; the regional yield model counts a pair it never saw as unfavourable.
        self.unmeasured_value = unmeasured_value
        # Crop → value (%) of the crop after itself, when the region measured it.
        self._same_crop_values = dict(same_crop_values or {})
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

    def same_crop_value(self, crop_id: str) -> float | None:
        """Value (%) of a crop after itself, when it is measured (else the rule of field_shift.py
        v5.1: the same crop twice counts 0 %)."""
        return self._same_crop_values.get(crop_id)

    def with_precrop_values(
        self, values: Mapping[tuple[str, str], float], unmeasured_value: float = 0.0
    ) -> TwinEvidence:
        """The same evidence, where an observed succession whose value is unknown here takes the
        value of `values` when it has one (the regional yield model, `data_access/yield_precrops`);
        what is still unknown counts `unmeasured_value`. A known value is kept; the successions
        observed do not change."""
        return TwinEvidence(
            self.crops,
            [
                (previous, next_crop, value if value is not None else values.get(pair))
                for pair, value in self._precrop_values.items()
                for previous, next_crop in (pair,)
            ],
            self.sigma_mean,
            self.twins,
            self.top_rotations,
            unmeasured_value=unmeasured_value,
            same_crop_values={p: v for (p, n), v in values.items() if p == n},
        )
