"""Return delays of a chain (hard constraint n° 4 and the "pests" criterion).

Checked between the crops of the chain; between what grew before (history or previous cycle) and
the start of the chain; between the end of the chain and its repetition in the next cycle. Two
crops of different families that share a soil disease (white mould, common scab) and come back
too fast give a warning, without changing the score.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from statistics import fmean

from field_shift.algorithm.delays.occupation import (
    Occupation,
    OccupationSource,
    years_between,
)
from field_shift.algorithm.delays.return_delay_catalog import (
    DEFAULT_DELAY_CATALOG,
    ReturnDelayCatalog,
)
from field_shift.algorithm.delays.return_delay_rules import RuleReason, delay_rules
from field_shift.reference.crops import CropSheet
from field_shift.reference.planning import MIN_HISTORY_YEARS

_CHAIN_OR_NEXT_CYCLE = (OccupationSource.CHAIN, OccupationSource.NEXT_CYCLE)


@dataclass(frozen=True)
class YearAndSource:
    year: int
    source: OccupationSource


@dataclass(frozen=True)
class DelayViolation:
    """A hard constraint that is not respected."""

    reason: RuleReason
    years_without: int
    minimum: int
    start: YearAndSource  # harvest of the earlier crop
    end: YearAndSource  # first year of the later crop


@dataclass(frozen=True)
class SharedDiseaseWarning:
    """Two crops of different families, hosts of the same soil disease, too close."""

    disease: str
    previous: str
    next: str
    years_without: int
    advised: int


@dataclass(frozen=True)
class DelayVerdict:
    ok: bool
    violations: list[DelayViolation]
    warnings: list[SharedDiseaseWarning]
    pest_score: float | None


@dataclass(frozen=True)
class ImpossibleCrop:
    """A crop that cannot come back every cycle: the years it needs, the years the cycle leaves."""

    required: int
    possible: int
    occupied_years: int


class ReturnDelayChecker:
    """Checks the return delays of the chains of a cycle.

    history  what grew before the cycle; None = the previous cycle was the same chain
    diseases soil diseases declared by the farmer
    """

    def __init__(
        self,
        cycle_years: int,
        history: Sequence[Occupation] | None = None,
        diseases: Sequence[str] = (),
        catalog: ReturnDelayCatalog = DEFAULT_DELAY_CATALOG,
    ) -> None:
        self.cycle_years = cycle_years
        self.history = None if history is None else list(history)
        self.diseases = tuple(diseases)
        self.catalog = catalog

    def timeline(self, occupations: Sequence[Occupation], closed: bool) -> list[Occupation]:
        """The chain with what precedes it and, for a complete chain, its repetition in the next
        cycle (the cycle starts again)."""
        chain = sorted(occupations, key=lambda o: o.first_year)
        if self.history is not None:
            before = [o.with_source(OccupationSource.HISTORY) for o in self.history]
        elif closed:
            before = [
                o.shifted_by(-self.cycle_years, OccupationSource.PREVIOUS_CYCLE) for o in chain
            ]
        else:
            before = []
        after = (
            [o.shifted_by(self.cycle_years, OccupationSource.NEXT_CYCLE) for o in chain]
            if closed
            else []
        )
        return sorted([*before, *chain, *after], key=lambda o: o.first_year)

    def _violations(
        self, occupations: Sequence[Occupation], closed: bool
    ) -> Iterator[DelayViolation]:
        timeline = self.timeline(occupations, closed)
        for j, later in enumerate(timeline):
            if later.source not in _CHAIN_OR_NEXT_CYCLE:
                continue
            for earlier in timeline[:j]:
                if earlier.source is OccupationSource.NEXT_CYCLE and (
                    later.source is OccupationSource.NEXT_CYCLE
                ):
                    continue  # two copies of the next cycle = a pair already seen
                gap = years_between(earlier, later)
                for rule in delay_rules(
                    self.catalog, earlier.crop_id, later.crop_id, self.diseases
                ):
                    if gap < rule.minimum:
                        yield DelayViolation(
                            reason=rule.reason,
                            years_without=gap,
                            minimum=rule.minimum,
                            start=YearAndSource(earlier.last_year, earlier.source),
                            end=YearAndSource(later.first_year, later.source),
                        )

    def violations(
        self, occupations: Sequence[Occupation], closed: bool = True
    ) -> list[DelayViolation]:
        """Hard constraints that are not respected, each reported once."""
        found: list[DelayViolation] = []
        seen: set[tuple] = set()
        for violation in self._violations(occupations, closed):
            key = (violation.reason.key, violation.start.year, violation.end.year)
            if key not in seen:
                seen.add(key)
                found.append(violation)
        return found

    def is_allowed(self, occupations: Sequence[Occupation], closed: bool = True) -> bool:
        """Hard constraints only (fast: stops at the first violation)."""
        return next(self._violations(occupations, closed), None) is None

    def check(self, occupations: Sequence[Occupation]) -> DelayVerdict:
        """Full verdict of a complete chain."""
        violations = self.violations(occupations)
        return DelayVerdict(
            ok=not violations,
            violations=violations,
            warnings=self.shared_disease_warnings(occupations),
            pest_score=self.pest_score(occupations),
        )

    def pest_score(self, occupations: Sequence[Occupation], closed: bool = True) -> float | None:
        """ "Pests" criterion (0 to 1): for each sold crop of the chain, the smallest ratio
        (years without + 1) ÷ (recommended delay + 1) with the crops before AND after it (same
        crop, same family, declared disease), capped at 1. Mean over the crops."""
        timeline = self.timeline(occupations, closed)
        scores = []
        for j, crop in enumerate(timeline):
            if crop.source is not OccupationSource.CHAIN:
                continue
            score = 1.0
            for i, other in enumerate(timeline):
                if i == j:
                    continue
                before, after = (other, crop) if i < j else (crop, other)
                gap = years_between(before, after)
                for rule in delay_rules(self.catalog, before.crop_id, after.crop_id, self.diseases):
                    if rule.recommended > 0:
                        score = min(score, max(0.0, (gap + 1) / (rule.recommended + 1)))
            scores.append(score)
        return fmean(scores) if scores else None

    def shared_disease_warnings(
        self, occupations: Sequence[Occupation]
    ) -> list[SharedDiseaseWarning]:
        """Crops of different families hosting the same undeclared disease, too close in time."""
        timeline = self.timeline(occupations, closed=True)
        worst: dict[tuple, SharedDiseaseWarning] = {}
        for disease, info in self.catalog.diseases.items():
            if not info.cross_family or disease in self.diseases:
                continue
            hosts = [
                o
                for o in timeline
                if (delay := self.catalog.get(o.crop_id)) is not None and delay.id in info.hosts
            ]
            for j, later in enumerate(hosts):
                if later.source not in _CHAIN_OR_NEXT_CYCLE:
                    continue
                for earlier in hosts[:j]:
                    a, b = self.catalog.get(earlier.crop_id), self.catalog.get(later.crop_id)
                    if a.family == b.family:
                        continue  # already covered by the family rule
                    gap = years_between(earlier, later)
                    key = (disease, frozenset((a.id, b.id)))
                    if gap < info.low and (key not in worst or gap < worst[key].years_without):
                        worst[key] = SharedDiseaseWarning(disease, a.id, b.id, gap, info.low)
        return list(worst.values())


def impossible_crops(
    cycle_years: int,
    sheets: Sequence[CropSheet],
    declared_diseases: Sequence[str] = (),
    catalog: ReturnDelayCatalog = DEFAULT_DELAY_CATALOG,
) -> dict[str, ImpossibleCrop]:
    """Sheets that cannot come back every cycle of `cycle_years` years: a crop present once per
    cycle has at most C − (years it occupies) years without it. Below its minimum, it is removed."""
    impossible: dict[str, ImpossibleCrop] = {}
    for sheet in sheets:
        delay = catalog.get(sheet.crop_id)
        if delay is None:
            continue
        required = max(
            delay.minimum, catalog.declared_disease_delay(sheet.crop_id, declared_diseases)
        )
        possible = cycle_years - sheet.years_occupied
        if possible < required:
            impossible[sheet.id] = ImpossibleCrop(required, possible, sheet.years_occupied)
    return impossible


def history_depth(
    crop_ids: Sequence[str],
    declared_diseases: Sequence[str] = (),
    minimum: int = MIN_HISTORY_YEARS,
    catalog: ReturnDelayCatalog = DEFAULT_DELAY_CATALOG,
) -> int:
    """Years of history to ask the farmer: the longest recommended delay (at least `minimum`)."""
    delays = [d.recommended for c in crop_ids if (d := catalog.get(c)) is not None]
    diseases = [catalog.diseases[d].high for d in declared_diseases if d in catalog.diseases]
    return max([minimum, *delays, *diseases])
