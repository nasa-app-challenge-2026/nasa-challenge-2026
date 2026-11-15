"""Automatic cover crops (one crop a year).

A rye is sown in every gap long enough between a harvest and the next sowing (corn harvested in
October, soybean sown in May). With 6 or 4 months per position, rye is a crop like the others and
takes its own position instead.
"""

from __future__ import annotations

import math

from field_shift.algorithm.chain.chain_step import Chain, ChainStep
from field_shift.algorithm.climate.cycle_climate import CycleClimate
from field_shift.algorithm.config.timing import MONTHS_PER_YEAR, SOWING_DELAY_MONTHS
from field_shift.reference.crops import COVER_SHEETS


def cover_crops(
    chain: Chain, entry_harvest: float, climate: CycleClimate, enabled: bool
) -> list[ChainStep]:
    """The cover steps (no position) sown between the crops of a chain."""
    if not enabled:
        return []
    covers: list[ChainStep] = []
    previous_harvest = entry_harvest
    for following in (step for step in chain if step.sowing is not None):
        for cover in COVER_SHEETS:
            if (
                cover.january_minimum_c is not None
                and climate.january_minimum_c < cover.january_minimum_c
            ):
                continue
            assert cover.sowing_window is not None and cover.harvest_month is not None
            year_start = math.floor(previous_harvest / MONTHS_PER_YEAR) * MONTHS_PER_YEAR
            sowing = max(
                year_start + cover.sowing_window[0], previous_harvest + SOWING_DELAY_MONTHS
            )
            if sowing > year_start + cover.sowing_window[1]:
                continue
            end = (
                year_start + MONTHS_PER_YEAR + cover.harvest_month - climate.harvest_advance_months
            )
            if end <= following.sowing - SOWING_DELAY_MONTHS:
                covers.append(ChainStep(cover.id, sowing, end))
                break
        previous_harvest = following.harvest
    return covers
