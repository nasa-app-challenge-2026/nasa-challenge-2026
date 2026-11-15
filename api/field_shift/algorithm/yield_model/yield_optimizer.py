"""Multi-crop rotation yield evaluation and combinatorial optimizer."""

from __future__ import annotations

import math

from field_shift.algorithm.yield_model.climate_twins import forecast_future_rotation_yield
from field_shift.algorithm.yield_model.config import CONFIG, CROP_IDS, CROPS, is_finite, is_integer, js_round
from field_shift.algorithm.yield_model.model_utils import (
    MAX_ROTATION_YEARS,
    min_confidence,
    physical_effect_interval,
    relative_gain_pct,
    resolve_pair_evidence,
    validate_current_crop,
    validate_physical_effect_pct,
    validated_rotation_slots,
)
from field_shift.algorithm.yield_model.rotation import (
    current_crop_conflict,
    normalize_cycle_offset,
    rotation_errors,
)

ALLOWED_REGIMES = frozenset({"all", "normal", "sec", "chaud"})


def _sum(values) -> float:
    total = 0.0
    for v in values:
        total += v
    return total


def validate_cycle_years(cycle_years) -> int:
    try:
        n = float(cycle_years)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"Paramètre cycleYears invalide ({cycle_years}) : entier entre 2 et 6 ans attendu."
        ) from error
    if not is_integer(n) or n < 2 or n > MAX_ROTATION_YEARS:
        raise ValueError(
            f"Paramètre cycleYears invalide ({cycle_years}) : entier entre 2 et 6 ans attendu."
        )
    return int(n)


def validate_regime(regime) -> str:
    r = "all" if regime is None else str(regime)
    if r not in ALLOWED_REGIMES:
        raise ValueError(f"Régime climatique invalide ({regime}).")
    return r


def compute_unobserved_pair_penalty(pair_matrix: dict | None) -> float:
    pairs = (pair_matrix or {}).get("pairs") if isinstance(pair_matrix, dict) else None
    effects = sorted(
        p["meanEffectPct"]
        for p in (pairs or {}).values()
        if isinstance(p, dict) and is_finite(p.get("meanEffectPct"))
    )
    if not effects:
        return -2.5
    raw_penalty = min(
        CONFIG["hyperparameters"]["maxUnobservedPairPenaltyPct"],
        effects[math.floor(len(effects) * 0.25)],
    )
    return validate_physical_effect_pct(
        js_round(raw_penalty, 2), "Pénalité de paire inconnue"
    )


def evaluate_rotation_yield_from_pairs(
    *,
    rotation=None,
    pair_matrix=None,
    current_crop=None,
    offset=0,
    regime="all",
    **kwargs,
) -> dict:
    """Evaluate relative annual vigor/yield effect of a rotation from pair_matrix."""
    if pair_matrix is None and "pairMatrix" in kwargs:
        pair_matrix = kwargs["pairMatrix"]
    if current_crop is None and "currentCrop" in kwargs:
        current_crop = kwargs["currentCrop"]

    valid_regime = validate_regime(regime)
    validate_current_crop(current_crop)
    slots = validated_rotation_slots(rotation)
    cycle_len = len(slots)
    safe_offset = normalize_cycle_offset(offset, cycle_len)
    pairs = (pair_matrix or {}).get("pairs") if isinstance(pair_matrix, dict) else None
    pairs = pairs if isinstance(pairs, dict) else {}
    penalty = compute_unobserved_pair_penalty(pair_matrix)
    half_width = CONFIG["hyperparameters"]["unobservedHalfWidthPct"]
    transitions = []
    previous = (
        current_crop
        or (slots[(safe_offset - 1 + cycle_len) % cycle_len]["crop"] if cycle_len else None)
    )

    for i in range(cycle_len):
        crop = slots[(safe_offset + i) % cycle_len]["crop"]
        pair_key = f"{previous}>{crop}"
        stat = pairs.get(pair_key) if pair_key in pairs else None
        resolved = (
            resolve_pair_evidence(stat, valid_regime)
            if stat is not None
            else {
                "meanEffectPct": penalty,
                "intervalPct": physical_effect_interval(
                    penalty, [penalty - half_width, penalty + half_width]
                ),
                "sampleCount": 0,
                "effectiveYearsCount": 0,
                "confidence": "faible",
            }
        )
        mono_key = f"{crop}>{crop}"
        mono = (
            resolve_pair_evidence(pairs[mono_key], valid_regime)
            if mono_key in pairs and pairs[mono_key] is not None
            else None
        )
        transition_entry = {
            "step": i + 1,
            "from": previous,
            "to": crop,
            "pairKey": pair_key,
            "observed": bool(stat),
            **resolved,
            "isMultiYearContinuation": previous == crop and CROPS[crop]["years"] > 1,
            "gainVsMonoculturePct": (
                relative_gain_pct(resolved["meanEffectPct"], mono["meanEffectPct"])
                if mono is not None
                else None
            ),
            "monocultureEffectPct": mono["meanEffectPct"] if mono is not None else None,
        }
        if isinstance(stat, dict) and stat.get("calibratedYield"):
            transition_entry["calibratedYield"] = stat["calibratedYield"]
        transitions.append(transition_entry)
        previous = crop

    def _mean(fn) -> float:
        return _sum(fn(t) for t in transitions) / max(1, cycle_len)

    mono_available = cycle_len > 0 and all(
        t["monocultureEffectPct"] is not None for t in transitions
    )
    mean_yield_gain_pct = validate_physical_effect_pct(
        js_round(_mean(lambda t: t["meanEffectPct"]), 2), "Moyenne du cycle"
    )
    return {
        "meanYieldGainPct": mean_yield_gain_pct,
        "gainVsMonocultureCyclePct": (
            relative_gain_pct(
                _mean(lambda t: t["meanEffectPct"]),
                _mean(lambda t: t["monocultureEffectPct"]),
            )
            if mono_available
            else None
        ),
        "yieldGainRangePct": physical_effect_interval(
            mean_yield_gain_pct,
            [
                min(mean_yield_gain_pct, js_round(_mean(lambda t: t["intervalPct"][0]), 1)),
                max(mean_yield_gain_pct, js_round(_mean(lambda t: t["intervalPct"][1]), 1)),
            ],
        ),
        "openingTransition": (transitions[0] if transitions else None)
        if current_crop
        else None,
        "observedShare": js_round(_mean(lambda t: 1 if t["observed"] else 0), 2),
        "minSampleInCycle": min(t["sampleCount"] for t in transitions) if cycle_len else 0,
        "confidence": (
            min_confidence(*(t["confidence"] for t in transitions))
            if cycle_len
            else "faible"
        ),
        "evaluationBasis": (
            "first_cycle_from_current_crop" if current_crop else "closed_cycle"
        ),
        "aggregation": "equal_weight_annual_relative_vigor",
        "transitions": transitions,
    }


def find_best_multi_crop_rotations_for_yield(
    *,
    pair_matrix=None,
    cycle_years=4,
    available_crops=None,
    current_crop=None,
    offset=0,
    min_distinct_crops=2,
    regime="all",
    top_k=5,
    projected_seasons=None,
    twin_match=None,
    local_baseline_stats=None,
    **kwargs,
) -> list[dict]:
    """Enumerate and rank valid multi-crop rotations by empirical and projected yield."""
    if pair_matrix is None and "pairMatrix" in kwargs:
        pair_matrix = kwargs["pairMatrix"]
    if "cycleYears" in kwargs:
        cycle_years = kwargs["cycleYears"]
    if available_crops is None:
        available_crops = kwargs.get("availableCrops", CROP_IDS)
    if current_crop is None and "currentCrop" in kwargs:
        current_crop = kwargs["currentCrop"]
    if "minDistinctCrops" in kwargs:
        min_distinct_crops = kwargs["minDistinctCrops"]
    if "topK" in kwargs:
        top_k = kwargs["topK"]
    if projected_seasons is None and "projectedSeasons" in kwargs:
        projected_seasons = kwargs["projectedSeasons"]
    if twin_match is None and "twinMatch" in kwargs:
        twin_match = kwargs["twinMatch"]
    if local_baseline_stats is None and "localBaselineStats" in kwargs:
        local_baseline_stats = kwargs["localBaselineStats"]

    valid_cycle_years = validate_cycle_years(cycle_years)
    valid_regime = validate_regime(regime)
    validate_current_crop(current_crop)
    safe_offset = normalize_cycle_offset(offset, valid_cycle_years)

    try:
        top_k_num = float(top_k) if top_k is not None else 5.0
    except (TypeError, ValueError):
        top_k_num = 5.0
    if not is_finite(top_k_num) or top_k_num == 0:
        top_k_num = 5.0
    safe_top_k = max(1, min(50, math.floor(top_k_num)))

    if (
        not is_integer(min_distinct_crops)
        or min_distinct_crops < 1
        or min_distinct_crops > len(CROP_IDS)
    ):
        raise ValueError("minDistinctCrops doit être un entier entre 1 et 6.")
    if not isinstance(available_crops, list) or len(available_crops) > 1000:
        raise TypeError("availableCrops doit être un tableau de 1000 identifiants maximum.")

    pool = list(
        dict.fromkeys(
            c for c in available_crops if isinstance(c, str) and c in CROPS
        )
    )
    candidates = []
    seq: list[str] = []

    def _evaluate_candidate() -> None:
        rotation = [
            {"crop": crop, "years": CROPS[crop]["years"], "cover": None}
            for crop in seq
        ]
        if (
            rotation_errors(rotation)
            or current_crop_conflict(
                {"rotation": rotation, "currentCrop": current_crop, "offset": safe_offset}
            )
            or len(set(seq)) < min_distinct_crops
        ):
            return

        evaluation = evaluate_rotation_yield_from_pairs(
            rotation=rotation,
            pair_matrix=pair_matrix,
            current_crop=current_crop,
            offset=safe_offset,
            regime=valid_regime,
        )
        if evaluation["observedShare"] < 0.5:
            return

        future_forecast = (
            forecast_future_rotation_yield(
                rotation=rotation,
                current_crop=current_crop,
                offset=safe_offset,
                projected_seasons=projected_seasons,
                local_pair_matrix=pair_matrix,
                twin_match=twin_match,
                local_baseline_stats=local_baseline_stats,
                unobserved_penalty_pct=compute_unobserved_pair_penalty(pair_matrix),
                historical_confidence=evaluation["confidence"],
            )
            if projected_seasons and local_baseline_stats
            else None
        )

        candidate = {
            "rotation": rotation,
            "cropsSequence": list(seq),
            "distinctCrops": len(set(seq)),
            "rankingScore": (
                future_forecast["meanFutureYieldGainPct"]
                if future_forecast is not None
                else evaluation["meanYieldGainPct"]
            ),
            **evaluation,
        }
        if future_forecast is not None:
            candidate["futureForecast"] = future_forecast
        candidates.append(candidate)

    def _walk(years_used: int) -> None:
        if years_used == valid_cycle_years:
            _evaluate_candidate()
            return
        for crop in pool:
            crop_years = CROPS[crop]["years"]
            if years_used + crop_years > valid_cycle_years:
                continue
            seq.append(crop)
            _walk(years_used + crop_years)
            seq.pop()

    _walk(0)
    candidates.sort(
        key=lambda c: (
            -(1 if c["observedShare"] == 1 else 0),
            -c["rankingScore"],
            -c["observedShare"],
        )
    )
    return candidates[:safe_top_k]

