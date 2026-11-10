"""Multi-criteria assessment of rotations (étape C, classement).

1. **Blocking constraints** are applied first (``screen``): a candidate rotation containing a
   crop the farmer excluded, or an annual crop that lacked the documented minimum heat in
   more than half of the analysed years, is not admissible.
2. **Criteria** are then scored from 0 (least favourable) to 1, each from a transparent metric:

   * climate resilience: ``1 - mean share of fields meeting a documented constraint``;
   * soil health: mean of three practice indicators (perennial forage share, legume share,
     botanical diversity), *not* a measurement of the soil;
   * water conservation: indicative seasonal water need (FAO), lower is better;
   * potential income: not evaluated without economic data.

3. The **weighted score** uses the farmer's priorities (0 to 3) over the criteria that can be
   used for every compared rotation.

Unknown benefits are never credited; unknown risks are listed, never silently counted as
absent. All conventions below are configurable and documented in ``docs/methodology.md``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from statistics import fmean

from fieldshift.domain.agronomy.crops import CropCatalog, CropCategory
from fieldshift.domain.agronomy.farm import Criterion, CropRotation, FarmProfile
from fieldshift.domain.simulation.stress_test import CropClimateRecord, RotationStressTest


@dataclass(frozen=True, slots=True)
class ScreeningPolicy:
    max_heat_shortfall_frequency: float = 0.5
    """Above this frequency of years without the documented minimum heat, a candidate is not
    admissible. 0.5 mirrors the OMAFRA heat-unit rating, a value reached one year in two
    (source: omafra_93_119)."""
    high_risk_frequency: float = 0.2
    """Above this frequency (more than one year in five) a crop is flagged as high risk. The
    Québec agroclimatic atlas reports values reached "8 years out of 10" (source:
    bourgeois_2012); OMAFRA tabulates the same 1-in-5 risk level (source: omafra_93_119)."""


@dataclass(frozen=True, slots=True)
class ScoringPolicy:
    family_diversity_target: int = 3
    """Number of botanical families scored as full diversity. Project convention."""
    water_need_scale_mm: tuple[float, float] = (400.0, 1200.0)
    """Linear scale of the water score: 400 mm or less scores 1, 1200 mm or more scores 0.
    Project convention spanning the indicative needs of the crops in the catalogue."""


RESILIENCE_AND_SOIL_WEIGHTS: Mapping[Criterion, int] = {
    Criterion.CLIMATE_RESILIENCE: 1,
    Criterion.SOIL_HEALTH: 1,
    Criterion.WATER_CONSERVATION: 0,
    Criterion.POTENTIAL_INCOME: 0,
}
"""Fixed weights used to pick the alternative oriented toward resilience and soil health."""


# --- Practice profiles -------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SoilPracticeProfile:
    perennial_forage_share: float
    legume_share: float
    """Share of years with a crop known to fix nitrogen. Unknown composition is not credited."""
    unknown_legume_share: float
    botanical_families: tuple[str, ...]


def soil_practice_profile(rotation: CropRotation, catalog: CropCatalog) -> SoilPracticeProfile:
    crops = [catalog.get(crop_id) for crop_id in rotation.crop_ids]
    n = len(crops)
    families: list[str] = []
    for crop in crops:
        families.extend(crop.botanical_families)
    return SoilPracticeProfile(
        perennial_forage_share=sum(c.category is CropCategory.PERENNIAL_FORAGE for c in crops) / n,
        legume_share=sum(c.fixes_nitrogen is True for c in crops) / n,
        unknown_legume_share=sum(c.fixes_nitrogen is None for c in crops) / n,
        botanical_families=tuple(dict.fromkeys(families)),
    )


@dataclass(frozen=True, slots=True)
class WaterNeedProfile:
    documented_years: int
    total_years: int
    mean_need_mm: float | None
    """Mean of the midpoints of the indicative ranges, over documented years only."""
    undocumented_crop_ids: tuple[str, ...]

    @property
    def coverage(self) -> float:
        return self.documented_years / self.total_years


def water_need_profile(rotation: CropRotation, catalog: CropCatalog) -> WaterNeedProfile:
    crops = [catalog.get(crop_id) for crop_id in rotation.crop_ids]
    needs = [crop.water_need.midpoint_mm for crop in crops if crop.water_need is not None]
    return WaterNeedProfile(
        documented_years=len(needs),
        total_years=len(crops),
        mean_need_mm=fmean(needs) if needs else None,
        undocumented_crop_ids=tuple(
            dict.fromkeys(crop.id for crop in crops if crop.water_need is None)
        ),
    )


# --- Screening -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CropRiskFlag:
    crop_id: str
    heat_shortfall_frequency: float | None
    frost_exposure_frequency: float | None
    blocking: bool
    high_risk: bool


def crop_risk_flags(
    rotation: CropRotation,
    records: Mapping[str, CropClimateRecord],
    policy: ScreeningPolicy,
) -> tuple[CropRiskFlag, ...]:
    flags: list[CropRiskFlag] = []
    for crop_id in dict.fromkeys(rotation.crop_ids):
        record = records[crop_id]
        shortfall = record.heat_shortfall_frequency
        frost = record.frost_exposure_frequency
        blocking = shortfall is not None and shortfall > policy.max_heat_shortfall_frequency
        high_risk = record.problem_frequency > policy.high_risk_frequency
        flags.append(CropRiskFlag(crop_id, shortfall, frost, blocking, high_risk))
    return tuple(flags)


def blocking_reasons(
    rotation: CropRotation,
    farm: FarmProfile,
    catalog: CropCatalog,
    flags: Sequence[CropRiskFlag],
) -> tuple[str, ...]:
    reasons: list[str] = []
    for crop_id in dict.fromkeys(rotation.crop_ids):
        if crop_id in farm.excluded_crop_ids:
            reasons.append(f"{catalog.get(crop_id).name_fr} : exclue par l'agriculteur.")
    for flag in flags:
        if flag.blocking and flag.heat_shortfall_frequency is not None:
            reasons.append(
                f"{catalog.get(flag.crop_id).name_fr} : chaleur minimale documentée non atteinte "
                f"{_years_phrase(flag.heat_shortfall_frequency)} (plus d'une année sur deux)."
            )
    return tuple(reasons)


def _years_phrase(frequency: float) -> str:
    return f"{round(frequency * 100)} % des années analysées"


# --- Criteria ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CriterionScore:
    criterion: Criterion
    score: float | None
    """0 (least favourable) to 1. ``None`` when the criterion cannot be scored."""
    coverage: float
    """Share of the rotation's years for which the underlying data exist."""


def score_climate(stress_test: RotationStressTest) -> CriterionScore:
    return CriterionScore(
        Criterion.CLIMATE_RESILIENCE, 1.0 - stress_test.mean_exposed_share, coverage=1.0
    )


def score_soil(profile: SoilPracticeProfile, policy: ScoringPolicy) -> CriterionScore:
    diversity = min(
        1.0,
        (len(profile.botanical_families) - 1) / max(1, policy.family_diversity_target - 1),
    )
    score = fmean([profile.perennial_forage_share, profile.legume_share, diversity])
    return CriterionScore(Criterion.SOIL_HEALTH, score, coverage=1.0)


def score_water(profile: WaterNeedProfile, policy: ScoringPolicy) -> CriterionScore:
    if profile.mean_need_mm is None:
        return CriterionScore(Criterion.WATER_CONSERVATION, None, coverage=0.0)
    low, high = policy.water_need_scale_mm
    score = 1.0 - (profile.mean_need_mm - low) / (high - low)
    return CriterionScore(
        Criterion.WATER_CONSERVATION, min(1.0, max(0.0, score)), coverage=profile.coverage
    )


def score_income() -> CriterionScore:
    return CriterionScore(Criterion.POTENTIAL_INCOME, None, coverage=0.0)


# --- Evaluated rotation --------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EvaluatedRotation:
    rotation: CropRotation
    stress_test: RotationStressTest
    soil: SoilPracticeProfile
    water: WaterNeedProfile
    criteria: tuple[CriterionScore, ...]
    risk_flags: tuple[CropRiskFlag, ...]
    blocking_reasons_fr: tuple[str, ...] = field(default=())

    @property
    def admissible(self) -> bool:
        return not self.blocking_reasons_fr

    def criterion(self, criterion: Criterion) -> CriterionScore:
        return next(score for score in self.criteria if score.criterion is criterion)


def evaluate_rotation(
    rotation: CropRotation,
    farm: FarmProfile,
    catalog: CropCatalog,
    records: Mapping[str, CropClimateRecord],
    stress_test: RotationStressTest,
    screening: ScreeningPolicy,
    scoring: ScoringPolicy,
    *,
    apply_blocking: bool,
) -> EvaluatedRotation:
    soil = soil_practice_profile(rotation, catalog)
    water = water_need_profile(rotation, catalog)
    flags = crop_risk_flags(rotation, records, screening)
    return EvaluatedRotation(
        rotation=rotation,
        stress_test=stress_test,
        soil=soil,
        water=water,
        criteria=(
            score_climate(stress_test),
            score_soil(soil, scoring),
            score_water(water, scoring),
            score_income(),
        ),
        risk_flags=flags,
        blocking_reasons_fr=(
            blocking_reasons(rotation, farm, catalog, flags) if apply_blocking else ()
        ),
    )


# --- Which criteria can rank ---------------------------------------------------


@dataclass(frozen=True, slots=True)
class CriterionStatus:
    criterion: Criterion
    used_in_ranking: bool
    reason_fr: str


def criteria_status(
    evaluated: Sequence[EvaluatedRotation], catalog: CropCatalog
) -> tuple[CriterionStatus, ...]:
    """A criterion ranks rotations only if it is fully scored for every compared rotation."""
    statuses: list[CriterionStatus] = []
    for criterion in Criterion:
        scores = [rotation.criterion(criterion) for rotation in evaluated]
        if criterion is Criterion.POTENTIAL_INCOME:
            statuses.append(
                CriterionStatus(
                    criterion,
                    used_in_ranking=False,
                    reason_fr=(
                        "Non évalué : aucun prix, rendement ni coût n'est renseigné. Le module "
                        "économique (phase 2) produira des fourchettes conditionnelles."
                    ),
                )
            )
        elif all(score.score is not None and score.coverage == 1.0 for score in scores):
            statuses.append(
                CriterionStatus(criterion, used_in_ranking=True, reason_fr="Évalué pour toutes.")
            )
        else:
            missing = sorted(
                {
                    catalog.get(crop_id).name_fr
                    for rotation in evaluated
                    for crop_id in rotation.water.undocumented_crop_ids
                }
            )
            statuses.append(
                CriterionStatus(
                    criterion,
                    used_in_ranking=False,
                    reason_fr=(
                        "Non utilisé dans le classement : besoin en eau non documenté pour "
                        f"{', '.join(missing)}. Comparer des moyennes partielles serait trompeur."
                    ),
                )
            )
    return tuple(statuses)


def weighted_score(
    rotation: EvaluatedRotation,
    weights: Mapping[Criterion, int],
    statuses: Sequence[CriterionStatus],
) -> float | None:
    """Weighted mean of the usable criteria, ``None`` when no usable criterion has weight."""
    usable = {status.criterion for status in statuses if status.used_in_ranking}
    total_weight = 0
    total = 0.0
    for criterion in usable:
        score = rotation.criterion(criterion).score
        weight = weights.get(criterion, 0)
        if score is None or weight == 0:
            continue
        total_weight += weight
        total += weight * score
    return total / total_weight if total_weight else None
