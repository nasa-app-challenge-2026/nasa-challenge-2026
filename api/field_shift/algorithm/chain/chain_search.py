"""Step 9b, the search: fill the positions one by one.

At each position, every candidate is tried after every partial chain; those that already break a
hard constraint are dropped, and the BEAM_WIDTH best partial chains are kept (beam search). At the
last position, the closure and the return delays over the whole cycle are checked. The 3 best
complete chains are returned.

Hard constraints: calendar and climate (`crop_placer`); every succession of sold crops observed in
the twins, the last one back to the first included; return delays; never two fallow positions in a
row; the first crop can be sown again after the last harvest (closure); the first crop follows the
crop in place.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TypeVar

from field_shift.algorithm.chain.chain_scorer import ScoredChain, score_chain
from field_shift.algorithm.chain.chain_step import (
    Chain,
    ChainStep,
    last_harvest,
    sheet_ids,
    to_occupations,
)
from field_shift.algorithm.chain.crop_placer import place_crop
from field_shift.algorithm.chain.cycle_context import CycleContext
from field_shift.algorithm.config.scoring import BEAM_WIDTH, BEST_CHAINS
from field_shift.algorithm.twins.twin_evidence import TwinEvidence
from field_shift.reference.crops import FALLOW_SHEET_ID, SHEETS, Role

T = TypeVar("T")


@dataclass(frozen=True)
class PartialChain:
    """A chain being built: its steps, the next position, the last harvest, the last sold sheet."""

    steps: tuple[ChainStep, ...]
    next_position: int
    harvest: float
    previous_sold: str | None


def succession_allowed(
    previous_sold_sheet: str | None, sheet_id: str, evidence: TwinEvidence
) -> bool:
    """Was this succession of sold crops observed in the twins? (Anything goes before a crop that
    is not sold, or after nothing.)"""
    if SHEETS[sheet_id].role is not Role.SOLD or previous_sold_sheet is None:
        return True
    return evidence.is_observed(SHEETS[previous_sold_sheet].crop_id, SHEETS[sheet_id].crop_id)


def delays_respected(chain: Chain, ctx: CycleContext, closed: bool) -> bool:
    """Return delays of a chain, with the history (and the next cycle if `closed`)."""
    return ctx.delays.is_allowed(to_occupations(chain, ctx.catalog), closed=closed)


def closes(chain: Chain, ctx: CycleContext) -> bool:
    """Can the chain start again: its first crops placed again after its last harvest."""
    sold = [step.sheet_id for step in chain if step.is_sold]
    if sold and not succession_allowed(sold[-1], sold[0], ctx.evidence):
        return False
    harvest = last_harvest(chain)
    previous = chain[-1].sheet_id
    for step in chain:
        position = ctx.first_position + ctx.positions + step.first_position
        placed = place_crop(step.sheet_id, position, harvest, previous, ctx.time, ctx.climate)
        if placed is None:
            return False
        if step.sheet_id != FALLOW_SHEET_ID:
            return True
        harvest = placed.harvest
        previous = step.sheet_id
    return True


def _best_first(items: Sequence[T], score_of: Callable[[T], float]) -> list[T]:
    """Highest score first; equal scores keep their order."""
    return sorted(items, key=lambda item: -score_of(item))


def best_chains(
    ctx: CycleContext, beam_width: int = BEAM_WIDTH, count: int = BEST_CHAINS
) -> list[ScoredChain]:
    """The best complete chains of the cycle, best first."""
    last_position_of_cycle = ctx.positions - 1
    beam = [PartialChain((), 0, ctx.entry_harvest, ctx.entry_sheet_id)]
    complete: list[tuple[ChainStep, ...]] = []
    while beam:
        extended_chains: list[PartialChain] = []
        for partial in beam:
            for sheet_id in ctx.candidates:
                previous_step = partial.steps[-1] if partial.steps else None
                if sheet_id == FALLOW_SHEET_ID and previous_step and previous_step.is_fallow:
                    continue  # no two empty positions in a row
                if not succession_allowed(partial.previous_sold, sheet_id, ctx.evidence):
                    continue
                previous = previous_step.sheet_id if previous_step else ctx.entry_sheet_id
                placed = place_crop(
                    sheet_id,
                    ctx.first_position + partial.next_position,
                    partial.harvest,
                    previous,
                    ctx.time,
                    ctx.climate,
                )
                if placed is None:
                    continue
                last = placed.last_position - ctx.first_position
                if last > last_position_of_cycle:
                    continue  # goes beyond the cycle
                steps = (
                    *partial.steps,
                    ChainStep(sheet_id, placed.sowing, placed.harvest, partial.next_position, last),
                )
                if last == last_position_of_cycle:
                    if closes(steps, ctx) and delays_respected(steps, ctx, closed=True):
                        complete.append(steps)
                elif delays_respected(steps, ctx, closed=False):
                    sold = sheet_id if SHEETS[sheet_id].role is Role.SOLD else partial.previous_sold
                    extended_chains.append(PartialChain(steps, last + 1, placed.harvest, sold))
        beam = _best_first(
            extended_chains, lambda p: score_chain(p.steps, ctx, partial=True).score
        )[:beam_width]
    return _distinct_best(complete, ctx, count)


def _distinct_best(
    complete: Sequence[tuple[ChainStep, ...]], ctx: CycleContext, count: int
) -> list[ScoredChain]:
    """The best chains that differ by their sequence of crops (the same sequence at other dates
    is the same chain)."""
    scored = _best_first(
        [score_chain(chain, ctx) for chain in complete], lambda result: result.score
    )
    distinct: list[ScoredChain] = []
    seen: set[tuple[str, ...]] = set()
    for result in scored:
        key = tuple(sheet_ids(result.chain))
        if key in seen:
            continue
        seen.add(key)
        distinct.append(result)
        if len(distinct) == count:
            break
    return distinct
