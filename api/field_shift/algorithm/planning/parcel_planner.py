"""Step 10: the plan of one field, cycle after cycle.

Before the first cycle: the field becomes free when the crop in place is harvested; cycle 1 starts
at the next position. The history (crop in place and previous years) checks the return delays from
cycle 1. The reference is the farmer's current rotation, continued on its own path and scored with
the same rules; it is never discarded (its broken delays become alerts).

For each cycle, in order: years → climate, twins and water (steps 3 to 7) → risks and weights (8) →
the 3 best chains (9b) → keep or change. The chain in place (the farmer's rotation in cycle 1, then
the chain kept at the previous cycle) is kept if it respects the return delays, its crops are still
grown in the twins and its score is at most 5 points below the best chain; otherwise the best chain
replaces it. The next cycle starts from the last harvest and the last sold crop of the chosen chain,
which joins the history.

After the last cycle: robustness of each adopted chain (`robustness_analyzer.py`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from field_shift.algorithm.chain.candidate_sheets import candidate_sheets
from field_shift.algorithm.chain.chain_replayer import replay_chain
from field_shift.algorithm.chain.chain_scorer import score_chain
from field_shift.algorithm.chain.chain_search import best_chains, delays_respected
from field_shift.algorithm.chain.chain_step import (
    Chain,
    ChainStep,
    last_harvest,
    last_sold_sheet,
    sheet_ids,
    to_occupations,
)
from field_shift.algorithm.chain.cycle_context import CycleContext
from field_shift.algorithm.config.scoring import KEEP_THRESHOLD_POINTS, REFERENCE_LENGTH_FACTOR
from field_shift.algorithm.config.timing import EPOCH_YEAR, MONTHS_PER_YEAR
from field_shift.algorithm.delays.field_history import CropInPlace, field_history
from field_shift.algorithm.delays.occupation import Occupation
from field_shift.algorithm.delays.return_delay_catalog import (
    DEFAULT_DELAY_CATALOG,
    ReturnDelayCatalog,
)
from field_shift.algorithm.delays.return_delay_checker import DelayViolation
from field_shift.algorithm.planning.criteria_weights import weights_for_cycle
from field_shift.algorithm.planning.cycle_plan import (
    CycleDataSource,
    CyclePlan,
    Decision,
    ParcelPlan,
)
from field_shift.algorithm.planning.farmer_profile import FarmerProfile
from field_shift.algorithm.planning.parcel import Parcel
from field_shift.algorithm.planning.robustness_analyzer import add_robustness
from field_shift.algorithm.planning.time_settings import TimeSettings
from field_shift.algorithm.timeline import month_time
from field_shift.reference.crops import FALLOW_SHEET_ID, SHEETS


@dataclass
class _PlanState:
    """Where the field stands at the start of the next cycle."""

    entry_harvest: float
    entry_sheet_id: str | None
    history: list[Occupation]
    in_place: Chain | None = None  # the chain chosen at the previous cycle


@dataclass
class _ReferenceState:
    """Where the farmer's own rotation stands: it goes on along its own path."""

    sequence: list[str]
    entry_harvest: float
    entry_sheet_id: str | None
    history: list[Occupation]
    index: int = 0


class ParcelPlanner:
    """Plans the cycles of one field."""

    def __init__(
        self,
        time: TimeSettings,
        farmer: FarmerProfile,
        data: CycleDataSource,
        today: float,
        keep_threshold: float = KEEP_THRESHOLD_POINTS,
        catalog: ReturnDelayCatalog = DEFAULT_DELAY_CATALOG,
    ) -> None:
        self._time = time
        self._farmer = farmer
        self._data = data
        self._today = today
        self._keep_threshold = keep_threshold
        self._catalog = catalog

    def plan(self, parcel: Parcel) -> ParcelPlan:
        time = self._time
        free_at = parcel.in_place_harvest if parcel.in_place_harvest is not None else self._today
        first_position = (
            math.floor((free_at - time.position_start_month) / time.frequency_months) + 1
        )
        history = field_history(
            self._crop_in_place(parcel), month_time.year_of(free_at), parcel.past, self._catalog
        )
        state = _PlanState(free_at, parcel.in_place_sheet_id, history)
        reference = _ReferenceState(
            sequence=parcel.reference_sequence(
                REFERENCE_LENGTH_FACTOR * time.positions_per_cycle * time.cycle_count
            ),
            entry_harvest=free_at,
            entry_sheet_id=parcel.in_place_sheet_id,
            history=list(history),
        )
        cycles: list[CyclePlan] = []
        for k in range(time.cycle_count):
            first = first_position + k * time.positions_per_cycle
            cycle = self._plan_cycle(parcel, k, first, state, reference)
            cycles.append(cycle)
            if cycle.decision is Decision.NONE:
                break  # nothing is feasible: the next cycles would have no start
        add_robustness(cycles)
        return ParcelPlan(parcel.id, free_at, month_time.to_date(free_at), history, cycles)

    @staticmethod
    def _crop_in_place(parcel: Parcel) -> CropInPlace | None:
        if not parcel.in_place or parcel.in_place == FALLOW_SHEET_ID:
            return None
        sheet = SHEETS.get(parcel.in_place)
        if sheet is None:
            return CropInPlace(parcel.in_place)
        return CropInPlace(sheet.crop_id, sheet.production_years)

    def _plan_cycle(
        self,
        parcel: Parcel,
        k: int,
        first_position: int,
        state: _PlanState,
        reference: _ReferenceState,
    ) -> CyclePlan:
        time, farmer = self._time, self._farmer
        first_year = EPOCH_YEAR + math.floor(
            (time.position_start_month + first_position * time.frequency_months) / MONTHS_PER_YEAR
        )
        years = (first_year, first_year + time.cycle_years - 1)
        data = self._data.cycle_data(*years)
        water_pressure = data.water.pressure
        risks = parcel.diagnostic.risks_for(water_pressure)
        candidates = candidate_sheets(
            data.evidence,
            farmer,
            time.frequency_months,
            time.cycle_years,
            parcel.diseases,
            self._catalog,
        )
        ctx = CycleContext(
            time=time,
            first_position=first_position,
            entry_harvest=state.entry_harvest,
            entry_sheet_id=state.entry_sheet_id,
            climate=data.climate,
            evidence=data.evidence,
            weights=weights_for_cycle(farmer.base_weights, risks, farmer.livestock),
            reserve=farmer.seeds if k == 0 else None,
            history=tuple(state.history),
            diseases=parcel.diseases,
            candidates=candidates.sheet_ids,
            covers_enabled=time.frequency_months >= MONTHS_PER_YEAR and farmer.covers_allowed(),
            water=data.water,
            irrigated=parcel.diagnostic.irrigated,
            catalog=self._catalog,
        )

        reference_chain, reference_ctx, alerts = self._continue_reference(ctx, reference)
        top = best_chains(ctx)
        best = top[0] if top else None
        in_place = reference_chain if k == 0 else self._replay_in_place(state.in_place, ctx)
        if in_place is not None and not delays_respected(in_place, ctx, closed=True):
            in_place = None
        kept = score_chain(in_place, ctx) if in_place is not None else None
        keep = kept is not None and (
            best is None or best.score - kept.score <= self._keep_threshold
        )
        chosen = kept if keep else best

        cycle = CyclePlan(
            index=k + 1,
            years=years,
            decision=self._decision(chosen is not None, keep),
            climate=data.climate,
            evidence=data.evidence,
            risks=risks,
            weights=dict(ctx.weights),
            removed=candidates.removed,
            chosen=chosen,
            reference=score_chain(reference_chain, reference_ctx) if reference_chain else None,
            reference_alerts=alerts,
            alternatives=[
                c for c in top if chosen is None or sheet_ids(c.chain) != sheet_ids(chosen.chain)
            ][:2],
            context=ctx,
            water_pressure=water_pressure,
        )
        if chosen is not None:
            state.in_place = chosen.chain
            state.history = [*state.history, *to_occupations(chosen.chain, self._catalog)]
            state.entry_harvest = last_harvest(chosen.chain)
            state.entry_sheet_id = last_sold_sheet(chosen.chain, state.entry_sheet_id)
        return cycle

    @staticmethod
    def _decision(has_chain: bool, keep: bool) -> Decision:
        if not has_chain:
            return Decision.NONE
        return Decision.KEEP if keep else Decision.CHANGE

    def _continue_reference(
        self, ctx: CycleContext, reference: _ReferenceState
    ) -> tuple[list[ChainStep] | None, CycleContext, list[DelayViolation]]:
        """The farmer's rotation goes on along its own path; its delay problems become alerts."""
        reference_ctx = ctx.with_changes(
            entry_harvest=reference.entry_harvest,
            entry_sheet_id=reference.entry_sheet_id,
            history=tuple(reference.history),
        )
        chain = replay_chain(reference.sequence[reference.index :], reference_ctx, fill_gaps=True)
        if chain is None:
            return None, reference_ctx, []
        occupations = to_occupations(chain, self._catalog)
        alerts = reference_ctx.delays.violations(occupations, closed=True)
        reference.history = [*reference.history, *occupations]
        reference.index += sum(1 for step in chain if not step.is_fallow)
        reference.entry_harvest = last_harvest(chain)
        reference.entry_sheet_id = last_sold_sheet(chain, reference.entry_sheet_id)
        return chain, reference_ctx, alerts

    @staticmethod
    def _replay_in_place(chain: Chain | None, ctx: CycleContext) -> list[ChainStep] | None:
        """The chain kept at the previous cycle, placed again if its crops are still grown in the
        twins."""
        if chain is None:
            return None
        still_grown = all(not s.is_sold or ctx.evidence.is_grown(s.sheet.crop_id) for s in chain)
        return replay_chain(sheet_ids(chain), ctx) if still_grown else None
