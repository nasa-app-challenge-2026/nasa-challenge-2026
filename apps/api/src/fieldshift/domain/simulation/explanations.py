"""Plain-language explanations (étape E).

Every sentence is generated from a computed number or a cited property, and carries the
identifiers of the sources it relies on. A sentence is emitted only when the underlying
difference exists; there is no generic praise and no generated text without a calculation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from fieldshift.domain.agronomy.crops import Confidence, CropCatalog, CropCategory
from fieldshift.domain.agronomy.farm import Criterion, FarmProfile, ObservationTopic
from fieldshift.domain.simulation.assessment import EvaluatedRotation
from fieldshift.domain.simulation.stress_test import CropClimateRecord

SOURCE_FORAGES = "quebec_forages"
SOURCE_DIVERSITY = "fao_conservation_agriculture"
SOURCE_WATER = "fao_irrigation_water_needs"
SOURCE_HAY = "cqpf_hay_guide_2002"
MATERIAL_EXPOSURE_DIFFERENCE = 0.01
"""Differences in mean exposure below one percentage point are not worth a sentence."""

METHOD_LIMITS_FR: tuple[str, ...] = (
    "Stress test rétrospectif : il compte les années où des seuils documentés auraient été "
    "atteints. Il ne reconstitue pas de rendements et ne prédit pas les années à venir.",
    "Les dates de semis sont inconnues : la saison de chaque culture est déduite de la météo de "
    "l'année (début de la saison de croissance, ou début du cumul des UTM pour le soya et le "
    "maïs).",
    "Les besoins en chaleur des céréales et du pois viennent d'essais en Saskatchewan : ils "
    "sont à valider pour les variétés et la région.",
    "Climat : réanalyse MERRA-2 (NASA) sur une cellule d'environ 50 km, sans mesure à la ferme.",
    "Sol non analysé : fertilité, drainage, pH et pierrosité ne sont pas pris en compte.",
    "Revenu non évalué : aucun prix, rendement ni coût n'est utilisé.",
    "Ces résultats servent à préparer une discussion avec un agronome ; ils ne remplacent pas "
    "son avis et ne garantissent aucun rendement.",
)
"""Limits that apply to every comparison, shown with the results."""


class StatementKind(StrEnum):
    BENEFIT = "benefit"
    TRADEOFF = "tradeoff"
    UNCERTAINTY = "uncertainty"
    TO_VALIDATE = "to_validate"


@dataclass(frozen=True, slots=True)
class Statement:
    kind: StatementKind
    text_fr: str
    criterion: Criterion | None = None
    source_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RecommendationExplanation:
    why_fr: str
    statements: tuple[Statement, ...]
    source_ids: tuple[str, ...]
    """Every source behind this strategy's numbers and sentences."""

    def of_kind(self, kind: StatementKind) -> tuple[Statement, ...]:
        return tuple(statement for statement in self.statements if statement.kind is kind)


@dataclass(frozen=True, slots=True)
class SiteFacts:
    """Site-level numbers quoted in explanations."""

    years: int
    haymaking_days_median: float | None
    haymaking_days_p20: float | None
    growing_season_precipitation_median_mm: float | None


def pct(fraction: float) -> str:
    return f"{round(fraction * 100)} %"


def _years_of(count: int, total: int) -> str:
    return f"{count} année{'s' if count > 1 else ''} sur {total}"


def _climate_statements(
    rotation: EvaluatedRotation,
    baseline: EvaluatedRotation | None,
    catalog: CropCatalog,
    records: Mapping[str, CropClimateRecord],
) -> list[Statement]:
    statements: list[Statement] = []
    test = rotation.stress_test
    if baseline is not None:
        difference = test.mean_exposed_share - baseline.stress_test.mean_exposed_share
        comparison = (
            f"en moyenne {pct(test.mean_exposed_share)} des champs touchés par une contrainte "
            f"documentée chaque année, contre {pct(baseline.stress_test.mean_exposed_share)} "
            f"pour la rotation actuelle ({test.years} années analysées)."
        )
        if difference <= -MATERIAL_EXPOSURE_DIFFERENCE:
            statements.append(
                Statement(
                    StatementKind.BENEFIT,
                    f"Moins exposée aux manques de chaleur et aux gels dommageables : {comparison}",
                    Criterion.CLIMATE_RESILIENCE,
                )
            )
        elif difference >= MATERIAL_EXPOSURE_DIFFERENCE:
            statements.append(
                Statement(
                    StatementKind.TRADEOFF,
                    f"Plus exposée aux manques de chaleur et aux gels dommageables : {comparison}",
                    Criterion.CLIMATE_RESILIENCE,
                )
            )

    for flag in rotation.risk_flags:
        if not flag.high_risk:
            continue
        record = records[flag.crop_id]
        crop = catalog.get(flag.crop_id)
        details: list[str] = []
        if record.heat_evaluated:
            details.append(
                f"chaleur minimale non atteinte {_years_of(record.heat_shortfall_years, record.years)}"
            )
        if record.frost_evaluated and record.frost_exposed_years:
            details.append(
                f"gel au seuil de dommage après le début de saison "
                f"{_years_of(record.frost_exposed_years, record.years)}"
            )
        sources = tuple(
            source
            for rule in (crop.heat_requirement, crop.frost_tolerance)
            if rule is not None
            for source in rule.basis.source_ids
        )
        statements.append(
            Statement(
                StatementKind.TRADEOFF,
                f"{crop.name_fr} : contrainte documentée plus d'une année sur cinq "
                f"({'; '.join(details)}).",
                Criterion.CLIMATE_RESILIENCE,
                sources,
            )
        )
        recent = [outcome for outcome in record.outcomes[-5:] if outcome.has_documented_problem]
        if record.heat_evaluated and record.outcomes and not recent:
            statements.append(
                Statement(
                    StatementKind.UNCERTAINTY,
                    f"{crop.name_fr} : aucune contrainte documentée au cours des 5 dernières "
                    "années analysées, contrairement à la période complète. Une série courte "
                    "ne suffit pas à conclure à un changement durable.",
                    Criterion.CLIMATE_RESILIENCE,
                )
            )
    return statements


def _soil_statements(
    rotation: EvaluatedRotation, baseline: EvaluatedRotation | None
) -> list[Statement]:
    if baseline is None:
        return []
    statements: list[Statement] = []
    new, old = rotation.soil, baseline.soil

    def compare(new_value: float, old_value: float, better: str, worse: str, source: str) -> None:
        if new_value > old_value:
            statements.append(
                Statement(StatementKind.BENEFIT, better, Criterion.SOIL_HEALTH, (source,))
            )
        elif new_value < old_value:
            statements.append(
                Statement(StatementKind.TRADEOFF, worse, Criterion.SOIL_HEALTH, (source,))
            )

    perennial = f"{pct(new.perennial_forage_share)} contre {pct(old.perennial_forage_share)}"
    compare(
        new.perennial_forage_share,
        old.perennial_forage_share,
        f"Plus d'années en prairie pérenne ({perennial}). Les plantes fourragères pérennes "
        "augmentent la teneur en matière organique et améliorent la structure du sol.",
        f"Moins d'années en prairie pérenne ({perennial}), une pratique reconnue pour la "
        "matière organique et la structure du sol.",
        SOURCE_FORAGES,
    )
    legumes = f"{pct(new.legume_share)} contre {pct(old.legume_share)}"
    compare(
        new.legume_share,
        old.legume_share,
        f"Plus d'années avec une légumineuse ({legumes}). Les légumineuses fixent l'azote de "
        "l'air et réduisent le besoin d'engrais azoté.",
        f"Moins d'années avec une légumineuse ({legumes}).",
        SOURCE_FORAGES,
    )
    families = f"{len(new.botanical_families)} contre {len(old.botanical_families)}"
    compare(
        float(len(new.botanical_families)),
        float(len(old.botanical_families)),
        f"Plus de familles botaniques dans le cycle ({families}) : la diversification des "
        "espèces est un principe de l'agriculture de conservation.",
        f"Moins de familles botaniques dans le cycle ({families}).",
        SOURCE_DIVERSITY,
    )
    return statements


def _water_statements(
    rotation: EvaluatedRotation, catalog: CropCatalog, facts: SiteFacts
) -> list[Statement]:
    precipitation = facts.growing_season_precipitation_median_mm
    if precipitation is None:
        return []
    statements: list[Statement] = []
    for crop_id in dict.fromkeys(rotation.rotation.crop_ids):
        need = catalog.get(crop_id).water_need
        if need is None or need.minimum_mm <= precipitation:
            continue
        statements.append(
            Statement(
                StatementKind.TRADEOFF,
                f"{catalog.get(crop_id).name_fr} : besoin en eau indicatif de "
                f"{need.minimum_mm:.0f} à {need.maximum_mm:.0f} mm par saison, au-dessus des "
                f"précipitations médianes d'avril à octobre ici ({precipitation:.0f} mm). La "
                "différence doit venir de la réserve du sol ou de l'irrigation.",
                Criterion.WATER_CONSERVATION,
                need.basis.source_ids,
            )
        )
    return statements


def _hay_statements(
    rotation: EvaluatedRotation,
    baseline: EvaluatedRotation | None,
    facts: SiteFacts,
) -> list[Statement]:
    if facts.haymaking_days_median is None or facts.haymaking_days_p20 is None:
        return []
    windows = (
        f"fenêtres d'au moins 3 jours consécutifs sans pluie, qui ont ouvert en médiane "
        f"{facts.haymaking_days_median:.0f} jours de fauche possibles en juin et juillet "
        f"(moins de {facts.haymaking_days_p20:.0f} jours une année sur cinq)"
    )
    share = rotation.soil.perennial_forage_share
    if baseline is None:
        if share == 0:
            return []
        return [
            Statement(
                StatementKind.TRADEOFF,
                f"{pct(share)} des champs en foin chaque année : la récolte de foin sec dépend "
                f"de {windows}.",
                Criterion.CLIMATE_RESILIENCE,
                (SOURCE_HAY,),
            )
        ]
    old_share = baseline.soil.perennial_forage_share
    if share > old_share:
        return [
            Statement(
                StatementKind.TRADEOFF,
                f"Plus de champs en foin ({pct(share)} contre {pct(old_share)}) : davantage de "
                f"récoltes dépendent de {windows}.",
                Criterion.CLIMATE_RESILIENCE,
                (SOURCE_HAY,),
            )
        ]
    if share < old_share:
        return [
            Statement(
                StatementKind.BENEFIT,
                f"Moins de champs en foin ({pct(share)} contre {pct(old_share)}) : moins de "
                f"récoltes dépendent de {windows}.",
                Criterion.CLIMATE_RESILIENCE,
                (SOURCE_HAY,),
            )
        ]
    return []


def _uncertainty_statements(
    rotation: EvaluatedRotation,
    baseline: EvaluatedRotation | None,
    catalog: CropCatalog,
    records: Mapping[str, CropClimateRecord],
) -> list[Statement]:
    statements: list[Statement] = []
    for crop_id in dict.fromkeys(rotation.rotation.crop_ids):
        crop = catalog.get(crop_id)
        record = records[crop_id]
        for rule in (crop.heat_requirement, crop.frost_tolerance, crop.water_need):
            if rule is not None and rule.basis.confidence is Confidence.PROVISIONAL:
                statements.append(
                    Statement(
                        StatementKind.UNCERTAINTY,
                        f"{crop.name_fr} : valeur provisoire. {rule.basis.note_fr}",
                        source_ids=rule.basis.source_ids,
                    )
                )
        if record.heat_tight_years:
            statements.append(
                Statement(
                    StatementKind.UNCERTAINTY,
                    f"{crop.name_fr} : chaleur seulement dans la fourchette documentée "
                    f"{_years_of(record.heat_tight_years, record.years)} ; ces années-là, "
                    "seules les variétés les plus hâtives auraient pu mûrir.",
                    Criterion.CLIMATE_RESILIENCE,
                )
            )
        if crop.fixes_nitrogen is None:
            statements.append(
                Statement(
                    StatementKind.UNCERTAINTY,
                    f"{crop.name_fr} : composition non précisée, aucune fixation d'azote n'est "
                    "créditée.",
                    Criterion.SOIL_HEALTH,
                )
            )

    def unevaluated(evaluated: EvaluatedRotation) -> float:
        crops = [catalog.get(crop_id) for crop_id in evaluated.rotation.crop_ids]
        return sum(not crop.is_annual for crop in crops) / len(crops)

    if baseline is not None and unevaluated(rotation) > unevaluated(baseline):
        statements.append(
            Statement(
                StatementKind.UNCERTAINTY,
                "Une plus grande part de cette rotation est en cultures pérennes, dont les "
                "risques propres (survie à l'hiver, météo de fenaison) ne sont pas chiffrés : "
                "son exposition climatique peut être sous-estimée.",
                Criterion.CLIMATE_RESILIENCE,
            )
        )
    return statements


def _to_validate_statements(
    rotation: EvaluatedRotation,
    baseline: EvaluatedRotation | None,
    catalog: CropCatalog,
    farm: FarmProfile,
) -> list[Statement]:
    statements: list[Statement] = []
    current_crops = set(farm.current_rotation.crop_ids)
    for crop_id in dict.fromkeys(rotation.rotation.crop_ids):
        if crop_id in current_crops:
            continue
        crop = catalog.get(crop_id)
        what = (
            "espèces du mélange, implantation et survie à l'hiver"
            if crop.category is CropCategory.PERENNIAL_FORAGE
            else "variété adaptée à la région, débouchés et coûts"
        )
        statements.append(
            Statement(StatementKind.TO_VALIDATE, f"{crop.name_fr} : nouvelle culture ; {what}.")
        )
    topics = {observation.topic for observation in farm.observations}
    if ObservationTopic.WEEDS in topics and baseline is not None:
        statements.append(
            Statement(
                StatementKind.TO_VALIDATE,
                "Effet de cette rotation sur les mauvaises herbes signalées (chiendent) : non "
                "évalué par l'outil, à discuter avec un agronome.",
            )
        )
    if ObservationTopic.MARKET in topics and baseline is not None:
        statements.append(
            Statement(
                StatementKind.TO_VALIDATE,
                "Accès aux marchés et coût du transport pour les cultures vendues : non évalués.",
                Criterion.POTENTIAL_INCOME,
            )
        )
    return statements


def explain(
    rotation: EvaluatedRotation,
    baseline: EvaluatedRotation | None,
    why_fr: str,
    farm: FarmProfile,
    catalog: CropCatalog,
    records: Mapping[str, CropClimateRecord],
    facts: SiteFacts,
) -> RecommendationExplanation:
    """Explanation of ``rotation``; ``baseline`` is the current rotation (``None`` for itself)."""
    statements = [
        *_climate_statements(rotation, baseline, catalog, records),
        *_hay_statements(rotation, baseline, facts),
        *_soil_statements(rotation, baseline),
        *_water_statements(rotation, catalog, facts),
        *_uncertainty_statements(rotation, baseline, catalog, records),
        *_to_validate_statements(rotation, baseline, catalog, farm),
    ]
    sources = ["nasa_power"]
    for crop_id in dict.fromkeys(rotation.rotation.crop_ids):
        crop = catalog.get(crop_id)
        for rule in (crop.heat_requirement, crop.frost_tolerance, crop.water_need):
            if rule is not None:
                sources.extend(rule.basis.source_ids)
    sources.extend(rotation.rotation.source_ids)
    for statement in statements:
        sources.extend(statement.source_ids)
    return RecommendationExplanation(
        why_fr=why_fr,
        statements=tuple(statements),
        source_ids=tuple(dict.fromkeys(sources)),
    )
