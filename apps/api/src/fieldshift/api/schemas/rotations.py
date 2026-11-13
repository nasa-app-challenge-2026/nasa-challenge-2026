"""Contracts of ``POST /api/v1/rotations/compare`` (comparison and historical stress test)."""

from __future__ import annotations

from pydantic import Field

from fieldshift.api.schemas.catalog import (
    FarmProfileModel,
    PrioritiesModel,
    RotationOut,
    priorities_dict,
    rotation_out,
)
from fieldshift.api.schemas.common import (
    ApiModel,
    PeriodOut,
    ProvenanceOut,
    QualityOut,
    RequestModel,
    period_out,
    provenance_out,
    quality_out,
)
from fieldshift.application.rotation_comparison import FarmAnalysis
from fieldshift.domain.agronomy.farm import Criterion, FarmerPriorities
from fieldshift.domain.agronomy.suitability import FrostStatus, HeatStatus
from fieldshift.domain.simulation.assessment import EvaluatedRotation
from fieldshift.domain.simulation.comparison import (
    CRITERION_LABELS_FR,
    MAX_SELECTED_ALTERNATIVES,
    StrategyRole,
)
from fieldshift.domain.simulation.explanations import (
    METHOD_LIMITS_FR,
    RecommendationExplanation,
    StatementKind,
)
from fieldshift.domain.simulation.stress_test import CropClimateRecord


class RotationCompareRequest(RequestModel):
    farm: FarmProfileModel
    first_year: int | None = Field(default=None, ge=1900, le=2100)
    last_year: int | None = Field(default=None, ge=1900, le=2100)
    selected_template_ids: list[str] | None = Field(
        default=None,
        max_length=MAX_SELECTED_ALTERNATIVES,
        description="Modèles à comparer à la place de la sélection automatique (1 ou 2).",
    )


class CriterionScoreOut(ApiModel):
    criterion: Criterion
    label_fr: str
    score: float | None
    coverage: float


class CriterionStatusOut(ApiModel):
    criterion: Criterion
    label_fr: str
    used_in_ranking: bool
    reason_fr: str


class SoilPracticeOut(ApiModel):
    perennial_forage_share: float
    legume_share: float
    unknown_legume_share: float
    botanical_families: list[str]


class WaterNeedProfileOut(ApiModel):
    documented_years: int
    total_years: int
    mean_need_mm: float | None
    undocumented_crop_ids: list[str]


class YearExposureOut(ApiModel):
    year: int
    exposed_share: float
    exposed_crop_ids: list[str]


class HazardOut(ApiModel):
    crop_id: str
    description_fr: str


class StressTestOut(ApiModel):
    years: int
    mean_exposed_share: float
    p80_exposed_share: float
    max_exposed_share: float
    years_with_exposure: int
    worst_years: list[int]
    yearly: list[YearExposureOut]
    unevaluated_hazards: list[HazardOut]


class RiskFlagOut(ApiModel):
    crop_id: str
    heat_shortfall_frequency: float | None
    frost_exposure_frequency: float | None
    blocking: bool
    high_risk: bool


class EvaluatedRotationOut(ApiModel):
    rotation: RotationOut
    admissible: bool
    blocking_reasons_fr: list[str]
    criteria: list[CriterionScoreOut]
    soil: SoilPracticeOut
    water: WaterNeedProfileOut
    stress_test: StressTestOut
    risk_flags: list[RiskFlagOut]


class StatementOut(ApiModel):
    kind: StatementKind
    text_fr: str
    criterion: Criterion | None
    source_ids: list[str]


class ExplanationOut(ApiModel):
    why_fr: str
    statements: list[StatementOut]
    source_ids: list[str]


class StrategyOut(ApiModel):
    role: StrategyRole
    evaluation: EvaluatedRotationOut
    score_farmer_priorities: float | None
    score_resilience_and_soil: float | None
    explanation: ExplanationOut


class ConsideredOut(ApiModel):
    evaluation: EvaluatedRotationOut
    score_farmer_priorities: float | None
    score_resilience_and_soil: float | None
    selected_as: StrategyRole | None


class CropYearOut(ApiModel):
    year: int
    heat_status: HeatStatus
    heat_available: float | None
    frost_status: FrostStatus
    damaging_frost_days: int | None
    first_damaging_frost_doy: int | None


class CropRecordOut(ApiModel):
    crop_id: str
    years: int
    heat_evaluated: bool
    frost_evaluated: bool
    heat_shortfall_years: int
    heat_tight_years: int
    frost_exposed_years: int
    problem_years: int
    yearly: list[CropYearOut]


class SiteFactsOut(ApiModel):
    years: int
    haymaking_days_median: float | None
    haymaking_days_p20: float | None
    growing_season_precipitation_median_mm: float | None


class RotationComparisonOut(ApiModel):
    period: PeriodOut
    provenance: ProvenanceOut
    quality: QualityOut
    priorities: PrioritiesModel
    criteria_status: list[CriterionStatusOut]
    strategies: list[StrategyOut]
    considered: list[ConsideredOut]
    crop_records: list[CropRecordOut]
    site_facts: SiteFactsOut
    notes_fr: list[str]
    method_limits_fr: list[str]


def evaluated_out(evaluated: EvaluatedRotation) -> EvaluatedRotationOut:
    test = evaluated.stress_test
    return EvaluatedRotationOut(
        rotation=rotation_out(evaluated.rotation),
        admissible=evaluated.admissible,
        blocking_reasons_fr=list(evaluated.blocking_reasons_fr),
        criteria=[
            CriterionScoreOut(
                criterion=c.criterion,
                label_fr=CRITERION_LABELS_FR[c.criterion],
                score=c.score,
                coverage=c.coverage,
            )
            for c in evaluated.criteria
        ],
        soil=SoilPracticeOut(
            perennial_forage_share=evaluated.soil.perennial_forage_share,
            legume_share=evaluated.soil.legume_share,
            unknown_legume_share=evaluated.soil.unknown_legume_share,
            botanical_families=list(evaluated.soil.botanical_families),
        ),
        water=WaterNeedProfileOut(
            documented_years=evaluated.water.documented_years,
            total_years=evaluated.water.total_years,
            mean_need_mm=evaluated.water.mean_need_mm,
            undocumented_crop_ids=list(evaluated.water.undocumented_crop_ids),
        ),
        stress_test=StressTestOut(
            years=test.years,
            mean_exposed_share=test.mean_exposed_share,
            p80_exposed_share=test.p80_exposed_share,
            max_exposed_share=test.max_exposed_share,
            years_with_exposure=test.years_with_exposure,
            worst_years=list(test.worst_years),
            yearly=[
                YearExposureOut(
                    year=y.year,
                    exposed_share=y.exposed_share,
                    exposed_crop_ids=list(y.exposed_crop_ids),
                )
                for y in test.yearly
            ],
            unevaluated_hazards=[
                HazardOut(crop_id=h.crop_id, description_fr=h.description_fr)
                for h in test.unevaluated_hazards
            ],
        ),
        risk_flags=[
            RiskFlagOut(
                crop_id=f.crop_id,
                heat_shortfall_frequency=f.heat_shortfall_frequency,
                frost_exposure_frequency=f.frost_exposure_frequency,
                blocking=f.blocking,
                high_risk=f.high_risk,
            )
            for f in evaluated.risk_flags
        ],
    )


def explanation_out(explanation: RecommendationExplanation) -> ExplanationOut:
    return ExplanationOut(
        why_fr=explanation.why_fr,
        statements=[
            StatementOut(
                kind=s.kind,
                text_fr=s.text_fr,
                criterion=s.criterion,
                source_ids=list(s.source_ids),
            )
            for s in explanation.statements
        ],
        source_ids=list(explanation.source_ids),
    )


def crop_record_out(record: CropClimateRecord) -> CropRecordOut:
    return CropRecordOut(
        crop_id=record.crop_id,
        years=record.years,
        heat_evaluated=record.heat_evaluated,
        frost_evaluated=record.frost_evaluated,
        heat_shortfall_years=record.heat_shortfall_years,
        heat_tight_years=record.heat_tight_years,
        frost_exposed_years=record.frost_exposed_years,
        problem_years=record.problem_years,
        yearly=[
            CropYearOut(
                year=o.year,
                heat_status=o.heat.status,
                heat_available=o.heat.available,
                frost_status=o.frost.status,
                damaging_frost_days=o.frost.damaging_frost_days,
                first_damaging_frost_doy=(
                    o.frost.first_damaging_frost_index + 1
                    if o.frost.first_damaging_frost_index is not None
                    else None
                ),
            )
            for o in record.outcomes
        ],
    )


def comparison_out(analysis: FarmAnalysis, priorities: FarmerPriorities) -> RotationComparisonOut:
    comparison = analysis.comparison
    facts = comparison.site_facts
    return RotationComparisonOut(
        period=period_out(analysis.climate.quality),
        provenance=provenance_out(analysis.climate.provenance),
        quality=quality_out(analysis.climate.quality),
        priorities=PrioritiesModel(**priorities_dict(priorities)),
        criteria_status=[
            CriterionStatusOut(
                criterion=s.criterion,
                label_fr=CRITERION_LABELS_FR[s.criterion],
                used_in_ranking=s.used_in_ranking,
                reason_fr=s.reason_fr,
            )
            for s in comparison.criteria_status
        ],
        strategies=[
            StrategyOut(
                role=s.role,
                evaluation=evaluated_out(s.evaluated),
                score_farmer_priorities=s.score_farmer_priorities,
                score_resilience_and_soil=s.score_resilience_and_soil,
                explanation=explanation_out(s.explanation),
            )
            for s in comparison.strategies
        ],
        considered=[
            ConsideredOut(
                evaluation=evaluated_out(c.evaluated),
                score_farmer_priorities=c.score_farmer_priorities,
                score_resilience_and_soil=c.score_resilience_and_soil,
                selected_as=c.selected_as,
            )
            for c in comparison.considered
        ],
        crop_records=[crop_record_out(r) for r in comparison.crop_records],
        site_facts=SiteFactsOut(
            years=facts.years,
            haymaking_days_median=facts.haymaking_days_median,
            haymaking_days_p20=facts.haymaking_days_p20,
            growing_season_precipitation_median_mm=facts.growing_season_precipitation_median_mm,
        ),
        notes_fr=list(comparison.notes_fr),
        method_limits_fr=list(METHOD_LIMITS_FR),
    )
