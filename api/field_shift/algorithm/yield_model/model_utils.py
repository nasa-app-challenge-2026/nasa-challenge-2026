"""Evidence, physical bounds and bounded rotation expansion shared by the engines."""

from __future__ import annotations

from field_shift.algorithm.yield_model.config import CONFIG, CROPS, is_finite, is_integer, js_round
from field_shift.algorithm.yield_model.rotation import to_slots

MAX_ROTATION_YEARS = 6
CONFIDENCES = ("faible", "moyenne", "elevee")
_MISSING = object()


def validate_physical_effect_pct(value, label="Effet relatif"):
    if not is_finite(value) or value < -100:
        raise ValueError(
            f"{label} invalide : valeur finie supérieure ou égale à -100 % attendue."
        )
    return value


def physical_effect_interval(mean_effect_pct, interval_pct) -> list:
    """Truncate only the uncertainty envelope at zero physical relative vigor."""
    validate_physical_effect_pct(mean_effect_pct)
    if (
        not isinstance(interval_pct, list)
        or len(interval_pct) != 2
        or not all(is_finite(value) for value in interval_pct)
        or interval_pct[0] > mean_effect_pct
        or interval_pct[1] < mean_effect_pct
    ):
        raise ValueError("Intervalle de paire non fini ou incohérent.")
    return [max(-100, interval_pct[0]), interval_pct[1]]


def validate_current_crop(current_crop):
    if current_crop is not None and (
        not isinstance(current_crop, str) or current_crop not in CROPS
    ):
        raise ValueError(f"Culture actuelle invalide (currentCrop={current_crop}).")


def validated_rotation_slots(rotation) -> list[dict]:
    """Validate durations before expansion, so unbounded allocations cannot occur."""
    if not isinstance(rotation, list) or len(rotation) > MAX_ROTATION_YEARS:
        raise ValueError("Rotation invalide : tableau de 6 entrées maximum attendu.")
    total = 0
    for entry in rotation:
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("crop"), str)
            or entry["crop"] not in CROPS
        ):
            raise ValueError("Culture inconnue dans la rotation.")
        years = entry.get("years")
        if years is None:
            years = 1
        if (
            not is_integer(years)
            or years < 1
            or years > MAX_ROTATION_YEARS
            or total + years > MAX_ROTATION_YEARS
        ):
            raise ValueError("Durée de rotation invalide : entiers positifs, 6 ans maximum.")
        info = CROPS[entry["crop"]]
        if info["years"] > 1 and years != info["years"]:
            raise ValueError(f"La {entry['crop']} doit occuper un bloc de {info['years']} ans.")
        total += years
    return to_slots(rotation)


def _confidence_index(value) -> int:
    return CONFIDENCES.index(value) if value in CONFIDENCES else 0


def min_confidence(*values) -> str:
    return CONFIDENCES[min((_confidence_index(value) for value in values), default=0)]


def downgrade_confidence(value) -> str:
    return CONFIDENCES[max(0, _confidence_index(value) - 1)]


def confidence_from_counts(sample_count, effective_years_count) -> str:
    if (
        sample_count >= CONFIG["sampling"]["minSamplesHighConfidence"]
        and effective_years_count >= 3
    ):
        return "elevee"
    if (
        sample_count >= CONFIG["sampling"]["minSamplesMediumConfidence"]
        and effective_years_count >= 2
    ):
        return "moyenne"
    return "faible"


def resolve_pair_evidence(stat: dict, regime="all") -> dict:
    sub = (stat.get("byRegime") or {}).get(regime) if regime != "all" else None
    evidence = sub if sub is not None else stat
    mean_effect_pct = validate_physical_effect_pct(evidence.get("meanEffectPct"))
    interval = evidence.get("intervalPct")
    if interval is None:
        interval = stat.get("intervalPct")
    interval_pct = physical_effect_interval(mean_effect_pct, interval)
    sample_count = evidence.get("sampleCount")
    if not is_integer(sample_count) or sample_count < 1:
        raise ValueError("Statistique de paire invalide ou intervalle incohérent.")
    std_error_pct = evidence.get("stdErrorPct", _MISSING)
    if std_error_pct is _MISSING or std_error_pct is None:
        std_error_pct = stat.get("stdErrorPct", _MISSING)
    effective_years_count = evidence.get("effectiveYearsCount")
    if effective_years_count is None:
        effective_years_count = 0
    if (
        not is_integer(effective_years_count)
        or effective_years_count < 0
        or effective_years_count > min(86, sample_count)
        or (
            std_error_pct is not _MISSING
            and (not is_finite(std_error_pct) or std_error_pct < 0)
        )
    ):
        raise ValueError("Effectif temporel ou incertitude de paire invalide.")
    confidence = min_confidence(
        stat.get("confidence"), confidence_from_counts(sample_count, effective_years_count)
    )
    if regime != "all" and sub is None:
        confidence = "faible"
    result = {
        "meanEffectPct": mean_effect_pct,
        "intervalPct": interval_pct,
        "sampleCount": sample_count,
        "effectiveYearsCount": effective_years_count,
        "confidence": confidence,
        "regimeSampleCount": sub.get("sampleCount", 0) if sub is not None else 0,
    }
    if std_error_pct is not _MISSING:
        result["stdErrorPct"] = std_error_pct
    return result


def relative_gain_pct(effect, baseline_effect):
    """Effects share a reference index of 100; a difference is not a ratio."""
    if not is_finite(effect) or not is_finite(baseline_effect):
        return None
    validate_physical_effect_pct(effect)
    validate_physical_effect_pct(baseline_effect, "Référence relative")
    if baseline_effect == -100:
        return None
    gain = 100 * ((1 + effect / 100) / (1 + baseline_effect / 100) - 1)
    return validate_physical_effect_pct(js_round(gain, 2), "Gain relatif")
