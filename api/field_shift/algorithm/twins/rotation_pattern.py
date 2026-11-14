"""Step 6: reduce the 8 years of crops of a field to its rotation.

Cycles of 2, 3 and 4 years are tried, with the most frequent crop at each position of the cycle; at
most one atypical year is tolerated. The rotation is written the same way whatever the year it
started: "Maïs → Soya", "Luzerne ×3 → Maïs". A field that always grows the same crop is a
monoculture; an irregular field has no rotation (None).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from field_shift.algorithm.config.twins import (
    ATYPICAL_YEARS_ALLOWED,
    LONGEST_ROTATION_YEARS,
    SHORTEST_ROTATION_YEARS,
)


def _most_frequent(values: Sequence[str]) -> str:
    """Most frequent value; on a tie, the one seen first."""
    return Counter(values).most_common(1)[0][0]


def _canonical_start(cycle: Sequence[str]) -> list[str]:
    """The rotation of the cycle that starts with the smallest crop name (same start for all)."""
    turns = (list(cycle[i:]) + list(cycle[:i]) for i in range(len(cycle)))
    return min(turns, key=tuple)


def _write_blocks(cycle: Sequence[str]) -> str:
    """ "Luzerne, Luzerne, Maïs" → "Luzerne ×2 → Maïs"."""
    blocks: list[list] = []
    for crop in cycle:
        if blocks and blocks[-1][0] == crop:
            blocks[-1][1] += 1
        else:
            blocks.append([crop, 1])
    return " → ".join(crop if count == 1 else f"{crop} ×{count}" for crop, count in blocks)


def rotation_of(
    sequence: Sequence[str],
    longest: int = LONGEST_ROTATION_YEARS,
    atypical_years: int = ATYPICAL_YEARS_ALLOWED,
) -> str | None:
    """The rotation of the crops of successive years, or None if the field has none."""
    if len(set(sequence)) == 1:
        return f"{sequence[0]} (monoculture)"
    best: tuple[int, list[str]] | None = None
    for period in range(SHORTEST_ROTATION_YEARS, longest + 1):
        cycle = [_most_frequent(sequence[j::period]) for j in range(period)]
        if len(set(cycle)) == 1:
            continue
        errors = sum(crop != cycle[i % period] for i, crop in enumerate(sequence))
        if best is None or errors < best[0]:  # on a tie, the shortest cycle
            best = (errors, cycle)
    if best is None or best[0] > atypical_years:
        return None
    return _write_blocks(_canonical_start(best[1]))
