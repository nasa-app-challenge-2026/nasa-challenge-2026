"""Step 9b, the score of a chain: 9 criteria from 0 to 1, then their weighted mean on 100.

  rendement     precrop values (step 7) of each succession, from the crop in place to the return
                to the start of the cycle; same crop twice = 0 %; unknown value = 0 % and a gap is
                reported. −16 %…+16 % become 0…1.
  erosion       share of the time the soil is covered by a living crop (covers included)
  eau, fourrage, azote, matiere_org   sheet values weighted by the time each crop holds the field
  marche        mean of the sold crops (a perennial counts once per year)
  ravageurs     return delays (see ReturnDelayChecker.pest_score)
  reserve       share of the sowings of the 1st cycle made with seeds the farmer owns; the other
                seeds are listed "to buy"
An unknown criterion is left out of the mean.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise
from statistics import fmean

from field_shift.algorithm.chain.chain_step import Chain, ChainStep, to_occupations
from field_shift.algorithm.chain.cover_crop_planner import cover_crops
from field_shift.algorithm.chain.cycle_context import CycleContext
from field_shift.algorithm.config.scoring import (
    MIN_DURATION_MONTHS,
    PRECROP_VALUE_RANGE_PCT,
    SCORE_SCALE,
)
from field_shift.algorithm.delays.return_delay_checker import SharedDiseaseWarning
from field_shift.algorithm.numerics.ratios import clamp01
from field_shift.algorithm.twins.twin_evidence import TwinEvidence
from field_shift.reference.criteria import CRITERIA_IDS, TIME_WEIGHTED_CRITERIA
from field_shift.reference.crops import CropSheet, Role


@dataclass(frozen=True)
class ScoredChain:
    """A chain with its score and everything the plan says about it.

    score         0 to 100
    criteria      the 9 criteria, 0 to 1 (None = unknown)
    gaps          successions whose precrop value is unknown
    seeds_to_buy  seeds the farmer does not own yet
    covers        cover steps placed automatically between the crops
    warnings      soil diseases shared by two crops (complete chains only)
    """

    chain: tuple[ChainStep, ...]
    score: float
    criteria: dict[str, float | None]
    gaps: list[tuple[str, str]]
    seeds_to_buy: list[str]
    covers: list[ChainStep]
    warnings: list[SharedDiseaseWarning]


def yield_criterion(
    values: Sequence[float], value_range: float = PRECROP_VALUE_RANGE_PCT
) -> float | None:
    """Precrop values (%) → 0..1 (None when there is no succession at all)."""
    if not values:
        return None
    return clamp01((fmean(values) + value_range) / (2 * value_range))


def successions(
    crops: Sequence[str], entry_crop_id: str | None, complete: bool
) -> list[tuple[str, str]]:
    """The successions of sold crops: from the crop in place, along the chain, and — for a complete
    chain — from the last crop back to the first (the cycle starts again)."""
    sequence = ([entry_crop_id] if entry_crop_id else []) + list(crops)
    pairs = list(pairwise(sequence))
    if complete and len(crops) > 1:
        pairs.append((crops[-1], crops[0]))
    return pairs


def _precrop_values(
    pairs: Sequence[tuple[str, str]], evidence: TwinEvidence
) -> tuple[list[float], list[tuple[str, str]]]:
    values: list[float] = []
    gaps: list[tuple[str, str]] = []
    for previous, next_crop in pairs:
        if previous == next_crop:
            values.append(0.0)
            continue
        value = evidence.precrop_value(previous, next_crop)
        values.append(0.0 if value is None else value)  # unknown: neutral (0 %), and reported
        if value is None and (previous, next_crop) not in gaps:
            gaps.append((previous, next_crop))
    return values, gaps


def _in_harvest_order(steps: Sequence[ChainStep]) -> list[ChainStep]:
    """Chain and covers in harvest order (a cover first on a tie)."""
    return sorted(steps, key=lambda step: (step.harvest, not step.is_cover))


def _living_cover_months(steps: Sequence[ChainStep], end: float) -> float:
    return sum(
        min(step.harvest, end) - step.sowing
        for step in steps
        if step.sowing is not None and step.sheet.role is not Role.FALLOW
    )


def _time_weighted_values(steps: Sequence[ChainStep], start: float) -> dict[str, float]:
    """Sheet values weighted by the time each crop holds the field."""
    spans: list[tuple[CropSheet, float]] = []
    previous = start
    for step in steps:
        spans.append((step.sheet, max(step.harvest - previous, 0.0)))
        previous = step.harvest
    total = sum(span for _, span in spans) or MIN_DURATION_MONTHS
    return {
        criterion: sum(sheet.values[criterion] * span for sheet, span in spans) / total
        for criterion in TIME_WEIGHTED_CRITERIA
    }


def _market_value(sold_sheets: Sequence[CropSheet]) -> float:
    """Mean market value of the sold crops (a perennial counts once per year)."""
    weights = [sheet.years_occupied for sheet in sold_sheets]
    if not weights:
        return 0.0
    return sum(s.values["marche"] * w for s, w in zip(sold_sheets, weights, strict=True)) / sum(
        weights
    )


def _reserve_share(
    steps: Sequence[ChainStep], reserve: frozenset[str]
) -> tuple[float | None, list[str]]:
    """Share of the sowings made with seeds the farmer owns, and the seeds to buy."""
    sown = sorted(
        (s for s in steps if s.sowing is not None and s.sheet.role is not Role.FALLOW),
        key=lambda step: step.sowing,
    )
    to_buy: list[str] = []
    owned: list[float] = []
    for step in sown:
        seed = step.sheet.seed_id
        if seed not in reserve and seed not in to_buy:
            to_buy.append(seed)
        owned.append(1.0 if seed in reserve else 0.0)
    return (fmean(owned) if owned else None), to_buy


def score_chain(chain: Chain, ctx: CycleContext, partial: bool = False) -> ScoredChain:
    """Score a chain. A partial chain is scored up to its last harvest."""
    covers = cover_crops(chain, ctx.entry_harvest, ctx.climate, ctx.covers_enabled)
    steps = _in_harvest_order([*chain, *covers])
    start = ctx.entry_harvest
    end = chain[-1].harvest if partial else start + ctx.cycle_months
    duration = max(end - start, MIN_DURATION_MONTHS)

    sold = [step for step in chain if step.is_sold]
    pairs = successions([s.sheet.crop_id for s in sold], ctx.entry_crop_id, complete=not partial)
    values, gaps = _precrop_values(pairs, ctx.evidence)
    occupations = to_occupations(chain, ctx.catalog)
    reserve_share, seeds_to_buy = (
        _reserve_share(steps, ctx.reserve) if ctx.reserve is not None else (None, [])
    )

    criteria: dict[str, float | None] = {
        "rendement": yield_criterion(values),
        "erosion": min(1.0, _living_cover_months(steps, end) / duration),
        **_time_weighted_values(steps, start),
        "marche": _market_value([step.sheet for step in sold]),
        "ravageurs": ctx.delays.pest_score(occupations, closed=not partial),
        "reserve": reserve_share,
    }
    known = [c for c in CRITERIA_IDS if criteria.get(c) is not None]
    weight_sum = sum(ctx.weights[c] for c in known)
    score = SCORE_SCALE * sum(ctx.weights[c] * criteria[c] for c in known) / weight_sum
    return ScoredChain(
        chain=tuple(chain),
        score=score,
        criteria=criteria,
        gaps=gaps,
        seeds_to_buy=seeds_to_buy,
        covers=covers,
        warnings=[] if partial else ctx.delays.shared_disease_warnings(occupations),
    )
