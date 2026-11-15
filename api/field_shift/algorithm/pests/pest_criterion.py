"""The "ravageurs" criterion of a chain, from 0 (worst) to 1 (best).

The pressure of every organism is followed year after year on the timeline of the field (what grew
before, the chain, the chain again at the next cycle: `pest_timeline.field_timeline`). A crop is
exposed to the organisms it hosts, at the pressure they have when it starts:

    risk of a crop   R = Σ_p sev_p × s_p × P_p / Σ_p sev_p × s_p      (over the organisms it hosts)
    score            S = 1 − mean of R over the crops of the chain

The score only measures what the hard constraints allow: the minimum return delays stay a filter
(`ReturnDelayChecker.is_allowed`), a chain that breaks one never gets here.

Two passes are measured and averaged: the chain after the history the farmer gave (the real one),
and the chain repeated at the next cycle (what it becomes if it goes on). Without history the
previous cycle is the same chain, played several times first to reach its steady state.

A crop that no organism of the catalogue is known to host has a risk of 0 and lowers the
confidence: nothing is invented.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from statistics import fmean
from typing import Final

from field_shift.algorithm.delays.occupation import Occupation, OccupationSource
from field_shift.algorithm.delays.return_delay_checker import ReturnDelayChecker
from field_shift.algorithm.numerics.ratios import clamp01
from field_shift.algorithm.pests.pest_catalog import DEFAULT_PEST_CATALOG, PestCatalog
from field_shift.algorithm.pests.pest_data import Pest, PestType
from field_shift.algorithm.pests.pest_explanations import exposure_sentence
from field_shift.algorithm.pests.pest_result import PestResult
from field_shift.algorithm.pests.pest_settings import DEFAULT_PRESSURE_PARAMS, PressureParams
from field_shift.algorithm.pests.pest_timeline import field_timeline
from field_shift.algorithm.pests.pressure_model import PressureState, pressure_by_year

#: At most this many sentences for the farmer, the most exposed crops first.
MAX_SENTENCES: Final = 6
#: Cache size (partial chains of the beam search come by the tens of thousands).
MAX_CACHED: Final = 50_000
#: A crop of the next cycle repeats the sentence of its twin when its risk is this close.
SAME_RISK: Final = 0.05

_CHAIN: Final = OccupationSource.CHAIN
_NEXT_CYCLE: Final = OccupationSource.NEXT_CYCLE


@dataclass(frozen=True, slots=True)
class _Exposure:
    """One crop of the timeline and the pressure it meets."""

    crop_id: str
    year: int
    risk: float
    known: bool
    worst_pressure: float
    by_type: dict[PestType, float]
    main_pest: Pest | None
    main_state: PressureState | None


class PestCriterion:
    """Scores the chains of one field (its history, its cycle length, its declared diseases)."""

    def __init__(
        self,
        checker: ReturnDelayChecker,
        catalog: PestCatalog = DEFAULT_PEST_CATALOG,
        params: PressureParams = DEFAULT_PRESSURE_PARAMS,
    ) -> None:
        self._checker = checker
        self._catalog = catalog
        self._params = params
        self._cache: dict[tuple, PestResult | None] = {}

    def evaluate(
        self, occupations: Sequence[Occupation], closed: bool = True, explain: bool = True
    ) -> PestResult | None:
        """The criterion of a chain (a partial one when `closed` is False); None without any crop.

        explain  False skips the sentences (the beam search scores far more chains than it shows)
        """
        key = (tuple(occupations), closed, explain)
        if key not in self._cache:
            if len(self._cache) >= MAX_CACHED:
                self._cache.clear()
            self._cache[key] = self._evaluate(occupations, closed, explain)
        return self._cache[key]

    def _evaluate(
        self, occupations: Sequence[Occupation], closed: bool, explain: bool
    ) -> PestResult | None:
        if not occupations:
            return None
        timeline = field_timeline(
            occupations,
            closed,
            cycle_years=self._checker.cycle_years,
            history=self._checker.history,
            previous_cycles=self._params.warmup_cycles,
        )
        measured = [o for o in timeline if o.source in (_CHAIN, _NEXT_CYCLE)]
        traces = self._pressures(timeline, measured)
        exposures = [self._exposure(o, traces) for o in measured]
        first = [e for e, o in zip(exposures, measured, strict=True) if o.source is _CHAIN]
        repeated = [e for e, o in zip(exposures, measured, strict=True) if o.source is _NEXT_CYCLE]

        risk = self._blend([e.risk for e in first], [e.risk for e in repeated])
        details = {
            f"pression_{kind.value.replace('-', '_')}": self._blend(
                [e.by_type[kind] for e in first if kind in e.by_type],
                [e.by_type[kind] for e in repeated if kind in e.by_type],
            )
            for kind in PestType
        }
        details["pire_cas"] = max((e.worst_pressure for e in exposures), default=0.0)
        details["diversite_familles"] = float(self._families(occupations))
        return PestResult(
            score=clamp01(1.0 - risk),
            details=details,
            explanations=self._sentences(first, repeated) if explain else [],
            confidence=fmean(1.0 if e.known else 0.0 for e in first),
        )

    def _blend(self, first: Sequence[float], repeated: Sequence[float]) -> float:
        """Mean of the first pass and of the repeated one, weighted (0 for a missing pass)."""
        if not repeated:
            return fmean(first) if first else 0.0
        weight = self._params.first_pass_weight
        return weight * (fmean(first) if first else 0.0) + (1 - weight) * fmean(repeated)

    def _pressures(
        self, timeline: Sequence[Occupation], measured: Sequence[Occupation]
    ) -> dict[str, dict[int, PressureState]]:
        """The pressure of every organism a measured crop hosts, over the whole timeline."""
        params = self._params
        pests: dict[str, Pest] = {}
        for occupation in measured:
            for pest in self._catalog.pests_of(occupation.crop_id):
                pests.setdefault(pest.id, pest)
        first_year = min(o.first_year for o in timeline)
        last_year = max(o.last_year for o in timeline)
        chain_start = min(o.first_year for o in timeline if o.source is _CHAIN)
        declared = set(self._checker.diseases)
        traces: dict[str, dict[int, PressureState]] = {}
        for pest in pests.values():
            host_years: dict[int, tuple[float, str]] = {}
            for occupation in timeline:
                sensitivity = pest.sensitivity_of(occupation.crop_id)
                if sensitivity <= 0:
                    continue
                for year in range(occupation.first_year, occupation.last_year + 1):
                    if year not in host_years or sensitivity > host_years[year][0]:
                        host_years[year] = (sensitivity, occupation.crop_id)
            traces[pest.id] = pressure_by_year(
                host_years,
                first_year,
                last_year,
                pest.years_without_host,
                params.acceptable,
                params.growth,
                floor_at={chain_start: 1.0} if pest.id in declared else None,
            )
        return traces

    def _exposure(
        self, occupation: Occupation, traces: dict[str, dict[int, PressureState]]
    ) -> _Exposure:
        crop_id, year = occupation.crop_id, occupation.first_year
        total = weighted = worst_pressure = 0.0
        by_type: dict[PestType, list[tuple[float, float]]] = {}
        main: tuple[float, Pest, PressureState] | None = None
        for pest in self._catalog.pests_of(crop_id):
            weight = self._catalog.weight(pest, crop_id)
            if weight <= 0:
                continue
            state = traces[pest.id][year]
            total += weight
            weighted += weight * state.pressure
            worst_pressure = max(worst_pressure, pest.sensitivity_of(crop_id) * state.pressure)
            by_type.setdefault(pest.type, []).append((weight, state.pressure))
            if main is None or weight * state.pressure > main[0]:
                main = (weight * state.pressure, pest, state)
        if total <= 0:
            return _Exposure(crop_id, year, 0.0, False, 0.0, {}, None, None)
        lam = self._params.worst_case_weight
        return _Exposure(
            crop_id=crop_id,
            year=year,
            risk=(1 - lam) * weighted / total + lam * worst_pressure,
            known=True,
            worst_pressure=worst_pressure,
            by_type={
                kind: sum(w * p for w, p in pairs) / sum(w for w, _ in pairs)
                for kind, pairs in by_type.items()
            },
            main_pest=main[1] if main else None,
            main_state=main[2] if main else None,
        )

    def _families(self, occupations: Sequence[Occupation]) -> int:
        catalog = self._checker.catalog
        return len({d.family for o in occupations if (d := catalog.get(o.crop_id)) is not None})

    def _sentences(self, first: Sequence[_Exposure], repeated: Sequence[_Exposure]) -> list[str]:
        """The most exposed crops, one sentence each; a crop of the next cycle only when it is not
        a copy of what the first pass already says."""
        threshold = self._params.explain_from_risk
        candidates: list[tuple[float, _Exposure, bool]] = [(e.risk, e, False) for e in first]
        candidates += [
            (twin_after.risk, twin_after, True)
            for twin_before, twin_after in zip(first, repeated, strict=False)
            if abs(twin_after.risk - twin_before.risk) >= SAME_RISK
        ]
        worst_first = sorted(candidates, key=lambda c: -c[0])
        return [
            exposure_sentence(
                e.crop_id,
                e.year,
                e.main_pest,
                e.main_state.pressure,
                e.main_state.last_host,
                next_cycle,
            )
            for risk, e, next_cycle in worst_first
            if risk >= threshold and e.main_pest is not None and e.main_state is not None
        ][:MAX_SENTENCES]
