"""The years the pest pressure is followed on: what grew before, the chain, the chain repeated.

Same rule as `ReturnDelayChecker.timeline` (algorithm/delays), with one difference: without a
history, the chain is played `previous_cycles` times before it (not once), so that the pressure
reaches the level of a chain that has been repeating for years. Kept here so the "ravageurs"
criterion does not change the delay checker.
"""

from __future__ import annotations

from collections.abc import Sequence

from field_shift.algorithm.delays.occupation import Occupation, OccupationSource


def field_timeline(
    occupations: Sequence[Occupation],
    closed: bool,
    cycle_years: int,
    history: Sequence[Occupation] | None,
    previous_cycles: int,
) -> list[Occupation]:
    """The chain with what precedes it and, for a complete chain, its repetition at the next cycle.

    closed           True for a complete chain (it repeats), False for a partial one (beam search)
    history          what grew before the cycle; None = the previous cycles were the same chain
    previous_cycles  copies of the chain played before it when there is no history
    """
    chain = sorted(occupations, key=lambda occupation: occupation.first_year)
    if history is not None:
        before = [occupation.with_source(OccupationSource.HISTORY) for occupation in history]
    elif closed:
        before = [
            occupation.shifted_by(-copy * cycle_years, OccupationSource.PREVIOUS_CYCLE)
            for copy in range(previous_cycles, 0, -1)
            for occupation in chain
        ]
    else:
        before = []
    after = (
        [occupation.shifted_by(cycle_years, OccupationSource.NEXT_CYCLE) for occupation in chain]
        if closed
        else []
    )
    return sorted([*before, *chain, *after], key=lambda occupation: occupation.first_year)
