"""Ranks the candidate rotations of one section.

For every rotation, each measure gives a score from 0 to 1. The score of the rotation is their
weighted sum, on 100:

    score = 100 × Σ weight(m) × score(m) / Σ weight(m)        over the measures m available

A measure that is not computed yet is left out, and the weights of the others are scaled up so
they still add up to 1: with only the soil protection written, the score is the soil protection
score, whatever the priorities. The rotations are then sorted, the best first; rotations with the
same score keep the order they were given in.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from field_shift.algorithm.config.scoring import SCORE_SCALE
from field_shift.algorithm.ranking.measures import (
    Measure,
    MeasureNotImplementedError,
    MeasureResult,
    SectionContext,
    all_measures,
)
from field_shift.algorithm.rotation.rotation import Rotation


@dataclass(frozen=True)
class RankedRotation:
    """A rotation with its rank on a section.

    rank     1 for the best rotation of the section
    score    weighted sum of the available measures, on 100; None when no available measure has
             a weight (nothing to rank on)
    results  the result of each of the four measures, by measure id
    weights  the weight each measure really had in the score (0 for the unavailable ones); they
             add up to 1 unless the score is None
    """

    rank: int
    rotation: Rotation
    score: float | None
    results: Mapping[str, MeasureResult]
    weights: Mapping[str, float]


def evaluate_measures(
    rotation: Rotation, context: SectionContext, measures: Sequence[Measure]
) -> dict[str, MeasureResult]:
    """The result of every measure for one rotation; "not available" for those not written."""
    results: dict[str, MeasureResult] = {}
    for measure in measures:
        try:
            results[measure.id] = measure.evaluate(rotation, context)
        except MeasureNotImplementedError as error:
            results[measure.id] = MeasureResult.unavailable(measure.id, str(error))
    return results


def effective_weights(
    weights: Mapping[str, float], results: Mapping[str, MeasureResult]
) -> dict[str, float]:
    """The weights scaled so the available measures add up to 1; 0 for the others.

    All zeros when no available measure has a weight.
    """
    usable = {
        measure: weights.get(measure, 0.0) if result.available else 0.0
        for measure, result in results.items()
    }
    total = sum(usable.values())
    if total <= 0:
        return dict.fromkeys(usable, 0.0)
    return {measure: weight / total for measure, weight in usable.items()}


def total_score(results: Mapping[str, MeasureResult], weights: Mapping[str, float]) -> float | None:
    """Score on 100 of a rotation from its results and their effective weights."""
    if not any(weights.values()):
        return None
    total = sum(
        weight * results[measure].score for measure, weight in weights.items() if weight > 0
    )
    return SCORE_SCALE * total


def rank_rotations(
    rotations: Sequence[Rotation],
    context: SectionContext,
    weights: Mapping[str, float],
    measures: Sequence[Measure] | None = None,
) -> list[RankedRotation]:
    """The rotations of a section, the best first (see the module documentation).

    `weights` gives the weight of each measure (see `measure_weights`); `measures` defaults to the
    four measures of the ranking.
    """
    measures = all_measures() if measures is None else measures
    scored = []
    for rotation in rotations:
        results = evaluate_measures(rotation, context, measures)
        used_weights = effective_weights(weights, results)
        scored.append((rotation, total_score(results, used_weights), results, used_weights))
    # sorted() is stable: equal scores keep the order of the request.
    scored.sort(key=lambda item: -1.0 if item[1] is None else item[1], reverse=True)
    return [
        RankedRotation(rank, rotation, score, results, used_weights)
        for rank, (rotation, score, results, used_weights) in enumerate(scored, start=1)
    ]
