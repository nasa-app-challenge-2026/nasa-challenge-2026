"""A chain in one line: "(seigle) → Jachère → Soya (+ seigle) → Jachère → Blé d’automne".

"[2 pos.]" = a crop on several positions; "(+ seigle)" = a cover sown after the crop; "(seigle)" at
the start = a cover sown before the first crop.
"""

from __future__ import annotations

from collections.abc import Sequence

from field_shift.algorithm.chain.chain_step import Chain, ChainStep
from field_shift.algorithm.config.timing import COVER_ATTACH_EPSILON
from field_shift.reference.crops import crop_name


def chain_label(chain: Chain, covers: Sequence[ChainStep] = ()) -> str:
    cover_after: dict[int, str] = {}
    cover_first: str | None = None
    for cover in covers:
        name = crop_name(cover.sheet.crop_id).lower()
        last_before = None  # the crop harvested last before the cover is sown
        for i, step in enumerate(chain):
            if step.sowing is None or step.harvest > cover.sowing + COVER_ATTACH_EPSILON:
                continue
            if last_before is None or step.harvest > chain[last_before].harvest:
                last_before = i
        if last_before is None:
            cover_first = name
        else:
            cover_after[last_before] = name
    parts = [f"({cover_first})"] if cover_first else []
    for i, step in enumerate(chain):
        span = step.last_position - step.first_position + 1
        text = step.sheet.name + (f" [{span} pos.]" if span > 1 else "")
        if i in cover_after:
            text += f" (+ {cover_after[i]})"
        parts.append(text)
    return " → ".join(parts)
