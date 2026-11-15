"""Place an imposed sequence of crops in a cycle.

Used for the farmer's current rotation, for a chain kept from one cycle to the next, and for the
robustness test.

With `fill_gaps` (the reference rotation, never discarded): a perennial too long for the end of the
cycle is shortened (Luzerne ×3 → ×2); a crop that does not fit leaves an empty position and is
tried again at the next one.
"""

from __future__ import annotations

from collections.abc import Sequence

from field_shift.algorithm.chain.chain_step import ChainStep, fallow_step
from field_shift.algorithm.chain.crop_placer import Placement, place_crop
from field_shift.algorithm.chain.cycle_context import CycleContext
from field_shift.reference.crops import CROP_SHEETS, SHEETS, CropSheet


def _shorter_versions(sheet_id: str) -> list[CropSheet]:
    """Shorter versions of a perennial sheet, longest first."""
    sheet = SHEETS[sheet_id]
    shorter = [
        s
        for s in CROP_SHEETS
        if s.crop_id == sheet.crop_id and 0 < s.production_years < sheet.production_years
    ]
    return sorted(shorter, key=lambda s: -s.production_years)


def replay_chain(
    sheet_ids: Sequence[str], ctx: CycleContext, fill_gaps: bool = False
) -> list[ChainStep] | None:
    """The sequence placed in the cycle, or None when it does not fill it."""
    positions = ctx.positions
    chain: list[ChainStep] = []
    position = 0
    harvest = ctx.entry_harvest
    index = 0

    def fits(placed: Placement | None) -> bool:
        return placed is not None and placed.last_position - ctx.first_position < positions

    def try_place(candidate: str, previous: str | None) -> Placement | None:
        # Reads `position` and `harvest` as they are when it is called.
        return place_crop(
            candidate, ctx.first_position + position, harvest, previous, ctx.time, ctx.climate
        )

    while position < positions and index < len(sheet_ids):
        sheet_id = sheet_ids[index]
        previous = chain[-1].sheet_id if chain else ctx.entry_sheet_id
        placed = try_place(sheet_id, previous)
        if fill_gaps and not fits(placed) and SHEETS[sheet_id].is_perennial:
            for shorter in _shorter_versions(sheet_id):
                attempt = try_place(shorter.id, previous)
                if fits(attempt):
                    sheet_id, placed = shorter.id, attempt
                    break
        if not fits(placed):
            if not fill_gaps:
                return None
            chain.append(fallow_step(harvest, position))
            position += 1
            continue
        last = placed.last_position - ctx.first_position
        chain.append(ChainStep(sheet_id, placed.sowing, placed.harvest, position, last))
        harvest, position, index = placed.harvest, last + 1, index + 1
    while fill_gaps and position < positions:
        chain.append(fallow_step(harvest, position))
        position += 1
    return chain if position == positions else None
