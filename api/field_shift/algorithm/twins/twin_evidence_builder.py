"""Steps 6 and 7 on the fields kept by the soil filter (step 5).

What the farmers of the twins really grow, field by field (USDA Crop Sequence Boundaries in the
U.S., AAFC annual crop inventory in Canada). Weight of a field = area × (1 − σ/2), σ being the
climate distance of its cell: a field of a cell at σ of 2 or more does not count.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from statistics import fmean

from field_shift.algorithm.config.climate import GOOD_TWIN_MAX_SIGMA
from field_shift.algorithm.config.twins import TOP_ROTATIONS
from field_shift.algorithm.twins.precrop_value import FieldYear, precrop_value
from field_shift.algorithm.twins.rotation_pattern import rotation_of
from field_shift.algorithm.twins.twin_evidence import TwinEvidence


@dataclass(frozen=True)
class TwinField:
    """A field of a twin cell: its crops of the last years, its area, the σ of its cell."""

    sequence: Sequence[str]
    area_ha: float
    sigma: float


def build_twin_evidence(
    fields: Iterable[TwinField],
    field_years: Sequence[FieldYear],
    twins: Iterable = (),
) -> TwinEvidence:
    """Crops, successions, precrop values and frequent rotations of the twin fields."""
    rotation_weights: defaultdict[str, float] = defaultdict(float)
    crops: set[str] = set()
    pairs: dict[tuple[str, str], None] = {}
    sigmas: list[float] = []
    for field_ in fields:
        weight = field_.area_ha * max(0.0, 1 - field_.sigma / GOOD_TWIN_MAX_SIGMA)
        if weight <= 0:
            continue
        sigmas.append(field_.sigma)
        rotation = rotation_of(field_.sequence)
        if rotation:
            rotation_weights[rotation] += weight
        crops.update(field_.sequence)
        for previous, next_crop in zip(field_.sequence, field_.sequence[1:], strict=False):
            if previous != next_crop:
                pairs[(previous, next_crop)] = None
    successions = [
        (previous, next_crop, precrop_value(field_years, previous, next_crop))
        for previous, next_crop in pairs
    ]
    top_rotations = sorted(rotation_weights.items(), key=lambda item: -item[1])[:TOP_ROTATIONS]
    return TwinEvidence(
        crops=crops,
        successions=successions,
        sigma_mean=fmean(sigmas) if sigmas else None,
        twins=twins,
        top_rotations=top_rotations,
    )
