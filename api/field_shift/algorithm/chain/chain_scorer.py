"""Step 9b, the score of a chain: the four priorities from 0 to 1, then their weighted mean on 100.

  rendement       precrop values (step 7) of each succession, from the crop in place to the
                  return to the start of the cycle (the twins, else the regional yield model);
                  same crop twice = its regional value, else 0 %; unknown value = the value of an
                  unmeasured pair (0 % in v5.1, unfavourable for the yield model) and a gap is
                  reported. −16 %…+16 % become 0…1.
  eau             water score of the whole chain, covers included: a daily soil water balance on
                  the weather of the cycle (`CycleContext.water`); unknown for a partial chain
  protection_sol  share of the time the soil is covered by a living crop (covers included)
  ravageurs       pressure of the soil diseases, nematodes and insects the crops meet, year after
                  year, with the history and the declared diseases of the field (`algorithm/pests`);
                  unknown when the catalogue knows none of the crops
An unknown criterion is left out of the mean. The seeds the farmer does not own are listed "to
buy" whatever the criteria.

The criteria scored are the keys of the weights of the cycle. The nine criteria of field_shift.py
v5.1 (reference tests) add:
  fourrage, azote, matiere_org   sheet values weighted by the time each crop holds the field
  marche          mean of the sold crops (a perennial counts once per year)
  delais_retour   recommended return delays (see ReturnDelayChecker.pest_score)
  reserve         share of the sowings of the 1st cycle made with seeds the farmer owns
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
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
from field_shift.algorithm.delays.occupation import Occupation
from field_shift.algorithm.delays.return_delay_checker import SharedDiseaseWarning
from field_shift.algorithm.numerics.ratios import clamp01
from field_shift.algorithm.pests.pest_catalog import DEFAULT_PEST_CATALOG
from field_shift.algorithm.pests.pest_result import PestResult
from field_shift.algorithm.twins.twin_evidence import TwinEvidence
from field_shift.algorithm.water.water_model import WaterScore
from field_shift.reference.criteria import (
    PESTS_CRITERION,
    SOIL_CRITERION,
    TIME_WEIGHTED_CRITERIA,
    V51_PESTS_CRITERION,
    WATER_CRITERION,
    YIELD_CRITERION,
)
from field_shift.reference.crops import CropSheet, Role

#: The criteria of field_shift.py v5.1 that are not a priority (reference tests).
MARKET_CRITERION = "marche"
RESERVE_CRITERION = "reserve"


@dataclass(frozen=True)
class ScoredChain:
    """A chain with its score and everything the plan says about it.

    score         0 to 100
    criteria      the criteria of the cycle (the four priorities), 0 to 1 (None = unknown)
    gaps          successions whose precrop value is unknown
    gap_value     what each of them counts in the yield criterion (%)
    seeds_to_buy  seeds the farmer does not own yet
    covers        cover steps placed automatically between the crops
    water         the water score behind the criterion `eau`, with its readable numbers
    warnings      soil diseases shared by two crops (complete chains only)
    pests         the pests criterion behind `ravageurs`, with its sentences (complete chains)
    """

    chain: tuple[ChainStep, ...]
    score: float
    criteria: dict[str, float | None]
    gaps: list[tuple[str, str]]
    seeds_to_buy: list[str]
    covers: list[ChainStep]
    warnings: list[SharedDiseaseWarning]
    water: WaterScore | None = None
    pests: ChainPests | None = None
    gap_value: float = 0.0


@dataclass(frozen=True)
class ChainPests:
    """The pests of a complete chain, for the plan.

    score               0 to 1 (the criterion `ravageurs`)
    confidence          share of the crops of the chain the catalogue knows an organism for
    crops_without_data  crops of the chain the catalogue knows nothing about (counted without risk)
    sentences           the most exposed crops, for the farmer
    """

    score: float
    confidence: float
    crops_without_data: tuple[str, ...]
    sentences: tuple[str, ...]


def _pest_result(
    occupations: Sequence[Occupation], ctx: CycleContext, partial: bool
) -> PestResult | None:
    """The pests criterion of the chain; None when it has no crop, or no crop the catalogue
    knows (a score of 1 would then mean "unknown", not "safe")."""
    result = ctx.pests.evaluate(occupations, closed=not partial, explain=not partial)
    if result is None or not result.confidence:
        return None
    return result


def _chain_pests(result: PestResult, occupations: Sequence[Occupation]) -> ChainPests:
    without_data = dict.fromkeys(
        o.crop_id for o in occupations if not DEFAULT_PEST_CATALOG.pests_of(o.crop_id)
    )
    return ChainPests(
        score=result.score,
        confidence=result.confidence or 0.0,
        crops_without_data=tuple(without_data),
        sentences=tuple(result.explanations),
    )


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
            same = evidence.same_crop_value(previous)
            values.append(0.0 if same is None else same)
            continue
        value = evidence.precrop_value(previous, next_crop)
        # Unknown: what an unmeasured pair counts, and reported.
        values.append(evidence.unmeasured_value if value is None else value)
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


def best_possible_score(scored: ScoredChain, weights: Mapping[str, float]) -> float:
    """The highest score a chain scored without its water can reach once the water is known
    (a water score of 1). Equal to its score when the water is already in it, or not scored."""
    if WATER_CRITERION not in weights or scored.criteria.get(WATER_CRITERION) is not None:
        return scored.score
    known = sum(weights[c] for c, value in scored.criteria.items() if value is not None)
    water = weights[WATER_CRITERION]
    return (scored.score * known + SCORE_SCALE * water) / (known + water)


def score_chain(
    chain: Chain, ctx: CycleContext, partial: bool = False, with_water: bool = True
) -> ScoredChain:
    """Score a chain. A partial chain is scored up to its last harvest.

    `with_water=False` leaves the water criterion out (unknown): the water score is a long
    simulation, and the search only asks for it when a chain can still be among the best (see
    `best_possible_score`)."""
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

    water = (
        ctx.water.score(steps, start, end, irrigated=ctx.irrigated, partial=partial)
        if with_water and WATER_CRITERION in ctx.weights
        else None
    )
    time_weighted: dict[str, float] = {}
    if any(c in ctx.weights for c in TIME_WEIGHTED_CRITERIA):
        time_weighted = _time_weighted_values(steps, start)
    pests = _pest_result(occupations, ctx, partial) if PESTS_CRITERION in ctx.weights else None
    # Only the criteria of the cycle are computed (the keys of its weights).
    measures: dict[str, Callable[[], float | None]] = {
        YIELD_CRITERION: lambda: yield_criterion(values),
        WATER_CRITERION: lambda: None if water is None else water.note,
        SOIL_CRITERION: lambda: min(1.0, _living_cover_months(steps, end) / duration),
        PESTS_CRITERION: lambda: None if pests is None else pests.score,
        V51_PESTS_CRITERION: lambda: ctx.delays.pest_score(occupations, closed=not partial),
        MARKET_CRITERION: lambda: _market_value([step.sheet for step in sold]),
        RESERVE_CRITERION: lambda: reserve_share,
        **{c: (lambda c=c: time_weighted[c]) for c in TIME_WEIGHTED_CRITERIA},
    }
    criteria: dict[str, float | None] = {c: measures[c]() for c in ctx.weights}
    known = [c for c, value in criteria.items() if value is not None]
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
        water=water,
        pests=None if partial or pests is None else _chain_pests(pests, occupations),
        gap_value=ctx.evidence.unmeasured_value,
    )
