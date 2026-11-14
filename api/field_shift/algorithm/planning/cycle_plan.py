"""The results of the planning of a field: one `CyclePlan` per cycle."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Protocol

from field_shift.algorithm.chain.chain_scorer import ScoredChain
from field_shift.algorithm.chain.cycle_context import CycleContext
from field_shift.algorithm.climate.cycle_climate import CycleClimate
from field_shift.algorithm.delays.occupation import Occupation
from field_shift.algorithm.delays.return_delay_checker import DelayViolation, ImpossibleCrop
from field_shift.algorithm.diagnostic.parcel_diagnostic import Risks
from field_shift.algorithm.twins.twin_evidence import TwinEvidence


class Decision(StrEnum):
    """What to do with the chain in place at the start of a cycle."""

    KEEP = "garder"
    CHANGE = "changer"
    NONE = "aucune"  # no chain respects the constraints


@dataclass(frozen=True)
class CycleData:
    """What steps 3 to 7 give for one cycle: its climate and what the twins grow."""

    climate: CycleClimate
    evidence: TwinEvidence


class CycleDataSource(Protocol):
    """Where the planner gets the climate and the twin evidence of a cycle."""

    def cycle_data(self, first_year: int, last_year: int) -> CycleData: ...


@dataclass
class CyclePlan:
    """The plan of one cycle of one field.

    chosen            the chain kept or chosen (None when no chain is feasible)
    reference         the farmer's rotation continued, scored with the same rules
    reference_alerts  return delays that the farmer's rotation does not respect
    alternatives      up to 2 other good chains
    removed           crops removed because their delay does not fit in the cycle
    robustness        worst score of the adopted chain in the later cycles (None = not computed)
    """

    index: int
    years: tuple[int, int]
    decision: Decision
    climate: CycleClimate
    evidence: TwinEvidence
    risks: Risks
    weights: dict[str, float]
    removed: dict[str, ImpossibleCrop]
    chosen: ScoredChain | None
    reference: ScoredChain | None
    reference_alerts: list[DelayViolation]
    alternatives: list[ScoredChain]
    context: CycleContext
    robustness: float | None = None
    becomes_infeasible_later: bool = False


@dataclass(frozen=True)
class ParcelPlan:
    """The plan of one field, cycle after cycle."""

    parcel_id: str
    free_at: float
    free_on: date
    history: Sequence[Occupation]
    cycles: list[CyclePlan]
