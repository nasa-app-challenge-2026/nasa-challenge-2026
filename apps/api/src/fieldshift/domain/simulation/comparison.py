"""Comparison of the current rotation with two alternatives (étapes C to E).

Selection, when the user does not pick the alternatives:

* **Alternative 1 — résilience et santé du sol**: highest score among admissible templates
  with equal weights on climate resilience and soil practices.
* **Alternative 2 — selon vos priorités**: highest score with the farmer's own weights among
  the remaining admissible templates.

Ties are broken by catalogue order, so the result is fully deterministic.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from fieldshift.domain.agronomy.crops import CropCatalog
from fieldshift.domain.agronomy.farm import Criterion, CropRotation, FarmProfile
from fieldshift.domain.agronomy.validation import validate_rotation
from fieldshift.domain.climate.indicators import INDICATORS_BY_ID, compute_indicator_series
from fieldshift.domain.climate.year_context import YearContext
from fieldshift.domain.simulation.assessment import (
    RESILIENCE_AND_SOIL_WEIGHTS,
    CriterionStatus,
    EvaluatedRotation,
    ScoringPolicy,
    ScreeningPolicy,
    criteria_status,
    evaluate_rotation,
    weighted_score,
)
from fieldshift.domain.simulation.explanations import (
    RecommendationExplanation,
    SiteFacts,
    explain,
)
from fieldshift.domain.simulation.stress_test import (
    CropClimateRecord,
    evaluate_crops,
    stress_test_rotation,
)

MAX_SELECTED_ALTERNATIVES = 2

CRITERION_LABELS_FR: Mapping[Criterion, str] = {
    Criterion.CLIMATE_RESILIENCE: "résilience climatique",
    Criterion.SOIL_HEALTH: "santé du sol",
    Criterion.WATER_CONSERVATION: "conservation de l'eau",
    Criterion.POTENTIAL_INCOME: "revenu potentiel",
}


class StrategyRole(StrEnum):
    CURRENT = "current"
    RESILIENCE_AND_SOIL = "resilience_and_soil"
    FARMER_PRIORITIES = "farmer_priorities"
    USER_SELECTED = "user_selected"


@dataclass(frozen=True, slots=True)
class Strategy:
    role: StrategyRole
    evaluated: EvaluatedRotation
    score_farmer_priorities: float | None
    score_resilience_and_soil: float | None
    explanation: RecommendationExplanation


@dataclass(frozen=True, slots=True)
class ConsideredAlternative:
    evaluated: EvaluatedRotation
    score_farmer_priorities: float | None
    score_resilience_and_soil: float | None
    selected_as: StrategyRole | None


@dataclass(frozen=True, slots=True)
class RotationComparison:
    strategies: tuple[Strategy, ...]
    """Current rotation first, then the alternatives."""
    considered: tuple[ConsideredAlternative, ...]
    criteria_status: tuple[CriterionStatus, ...]
    crop_records: tuple[CropClimateRecord, ...]
    site_facts: SiteFacts
    notes_fr: tuple[str, ...]


class UnknownTemplateError(LookupError):
    def __init__(self, template_id: str) -> None:
        super().__init__(f"unknown rotation template: {template_id!r}")
        self.template_id = template_id


def site_facts(contexts: Sequence[YearContext]) -> SiteFacts:
    hay = compute_indicator_series(INDICATORS_BY_ID["haymaking_days_june_july"], contexts)
    rain = compute_indicator_series(INDICATORS_BY_ID["precipitation_growing_season_mm"], contexts)
    return SiteFacts(
        years=len(contexts),
        haymaking_days_median=hay.summary.median if hay.summary else None,
        haymaking_days_p20=hay.summary.p20 if hay.summary else None,
        growing_season_precipitation_median_mm=rain.summary.median if rain.summary else None,
    )


def describe_weights(weights: Mapping[Criterion, int]) -> str:
    return ", ".join(f"{CRITERION_LABELS_FR[c]} {weights.get(c, 0)}" for c in Criterion)


def _pick(
    candidates: Sequence[tuple[int, EvaluatedRotation, float | None]],
) -> EvaluatedRotation | None:
    """Highest score, ties broken by catalogue order. Unscored candidates are never picked."""
    scored = [
        (score, -order, rotation) for order, rotation, score in candidates if score is not None
    ]
    if not scored:
        return None
    return max(scored, key=lambda item: (item[0], item[1]))[2]


def compare_rotations(
    farm: FarmProfile,
    templates: Sequence[CropRotation],
    catalog: CropCatalog,
    contexts: Sequence[YearContext],
    *,
    selected_template_ids: Sequence[str] | None = None,
    screening: ScreeningPolicy | None = None,
    scoring: ScoringPolicy | None = None,
) -> RotationComparison:
    if not contexts:
        raise ValueError("at least one analysed year is required")
    screening = screening or ScreeningPolicy()
    scoring = scoring or ScoringPolicy()
    templates_by_id = {template.id: template for template in templates}
    for template_id in selected_template_ids or ():
        if template_id not in templates_by_id:
            raise UnknownTemplateError(template_id)

    current_rotation = farm.current_rotation
    validate_rotation(current_rotation, catalog)
    candidates = [t for t in templates if t.crop_ids != current_rotation.crop_ids]
    for template in candidates:
        validate_rotation(template, catalog)

    all_crop_ids = [*current_rotation.crop_ids, *(c for t in candidates for c in t.crop_ids)]
    records = evaluate_crops(all_crop_ids, catalog, contexts)

    def evaluate(rotation: CropRotation, *, apply_blocking: bool) -> EvaluatedRotation:
        return evaluate_rotation(
            rotation,
            farm,
            catalog,
            records,
            stress_test_rotation(rotation, catalog, records),
            screening,
            scoring,
            apply_blocking=apply_blocking,
        )

    current = evaluate(current_rotation, apply_blocking=False)
    evaluated_templates = [evaluate(t, apply_blocking=True) for t in candidates]
    admissible = [e for e in evaluated_templates if e.admissible]
    statuses = criteria_status([current, *admissible], catalog)

    farmer_weights = farm.priorities.as_weights()

    def scores(rotation: EvaluatedRotation) -> tuple[float | None, float | None]:
        return (
            weighted_score(rotation, farmer_weights, statuses),
            weighted_score(rotation, RESILIENCE_AND_SOIL_WEIGHTS, statuses),
        )

    notes: list[str] = []
    selection: list[tuple[StrategyRole, EvaluatedRotation]] = []
    if selected_template_ids:
        by_id = {e.rotation.id: e for e in evaluated_templates}
        for template_id in list(dict.fromkeys(selected_template_ids))[:MAX_SELECTED_ALTERNATIVES]:
            if template_id in by_id:
                selection.append((StrategyRole.USER_SELECTED, by_id[template_id]))
            else:
                notes.append(
                    f"La rotation « {templates_by_id[template_id].name_fr} » est identique à la "
                    "rotation actuelle ; elle n'est pas comparée une seconde fois."
                )
    else:
        ordered = list(enumerate(admissible))
        first = _pick([(i, e, scores(e)[1]) for i, e in ordered])
        if first is not None:
            selection.append((StrategyRole.RESILIENCE_AND_SOIL, first))
        remaining = [(i, e) for i, e in ordered if e is not first]
        second = _pick([(i, e, scores(e)[0]) for i, e in remaining])
        if second is None and remaining:
            second = _pick([(i, e, scores(e)[1]) for i, e in remaining])
            notes.append(
                "Vos priorités ne portent sur aucun critère évaluable ; la deuxième alternative "
                "est choisie avec les poids résilience et santé du sol."
            )
        if second is not None:
            selection.append((StrategyRole.FARMER_PRIORITIES, second))
        if len(admissible) < MAX_SELECTED_ALTERNATIVES:
            notes.append(
                f"Seulement {len(admissible)} rotation(s) admissible(s) parmi "
                f"{len(evaluated_templates)} modèles évalués : les autres sont écartées par des "
                "contraintes bloquantes (voir la liste des rotations considérées)."
            )

    facts = site_facts(contexts)
    admissible_count = len(admissible)

    def why(role: StrategyRole, rotation: EvaluatedRotation) -> str:
        rationale = f" {rotation.rotation.rationale_fr}" if rotation.rotation.rationale_fr else ""
        if role is StrategyRole.CURRENT:
            return "Rotation déclarée par l'agriculteur : point de référence de la comparaison."
        if role is StrategyRole.RESILIENCE_AND_SOIL:
            return (
                f"Meilleur score parmi les {admissible_count} rotations admissibles quand la "
                f"résilience climatique et la santé du sol comptent à parts égales.{rationale}"
            )
        if role is StrategyRole.FARMER_PRIORITIES:
            return (
                "Meilleur score selon les priorités indiquées "
                f"({describe_weights(farmer_weights)}) parmi les rotations admissibles "
                f"restantes.{rationale}"
            )
        return f"Rotation choisie pour être comparée.{rationale}"

    strategies: list[Strategy] = []
    for role, rotation in [(StrategyRole.CURRENT, current), *selection]:
        farmer_score, fixed_score = scores(rotation)
        strategies.append(
            Strategy(
                role=role,
                evaluated=rotation,
                score_farmer_priorities=farmer_score,
                score_resilience_and_soil=fixed_score,
                explanation=explain(
                    rotation,
                    None if role is StrategyRole.CURRENT else current,
                    why(role, rotation),
                    farm,
                    catalog,
                    records,
                    facts,
                ),
            )
        )

    selected_roles = {id(rotation): role for role, rotation in selection}
    considered = tuple(
        ConsideredAlternative(
            evaluated=rotation,
            score_farmer_priorities=scores(rotation)[0] if rotation.admissible else None,
            score_resilience_and_soil=scores(rotation)[1] if rotation.admissible else None,
            selected_as=selected_roles.get(id(rotation)),
        )
        for rotation in evaluated_templates
    )
    return RotationComparison(
        strategies=tuple(strategies),
        considered=considered,
        criteria_status=statuses,
        crop_records=tuple(records.values()),
        site_facts=facts,
        notes_fr=tuple(notes),
    )
