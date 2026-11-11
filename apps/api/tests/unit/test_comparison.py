from __future__ import annotations

import pytest

from fieldshift.domain.agronomy.crops import (
    Basis,
    Confidence,
    Crop,
    CropCatalog,
    CropCategory,
    HeatRequirement,
    HeatUnit,
    SeasonModel,
)
from fieldshift.domain.agronomy.farm import (
    Criterion,
    CropRotation,
    FarmerPriorities,
    FarmProfile,
    LocationPrecision,
    RotationOrigin,
)
from fieldshift.domain.agronomy.validation import InvalidRotationError, validate_rotation
from fieldshift.domain.climate.year_context import build_year_contexts
from fieldshift.domain.geo import GeoPoint
from fieldshift.domain.simulation.comparison import StrategyRole, compare_rotations
from fieldshift.domain.simulation.explanations import StatementKind
from tests.factories import make_year, seasonal

BASIS = Basis(("test",), Confidence.DOCUMENTED, "test")


def crop(id_: str, **kwargs: object) -> Crop:
    defaults: dict[str, object] = {
        "name_fr": id_,
        "name_en": id_,
        "scientific_name": id_,
        "category": CropCategory.ANNUAL,
        "botanical_families": ("Poaceae",),
        "fixes_nitrogen": False,
        "season_model": SeasonModel.COOL_SEASON,
        "heat_requirement": None,
        "frost_tolerance": None,
        "water_need": None,
        "context_indicator_ids": (),
        "not_modelled_fr": (),
    }
    defaults.update(kwargs)
    return Crop(id=id_, **defaults)  # type: ignore[arg-type]


CATALOG = CropCatalog(
    [
        crop("cereal", heat_requirement=HeatRequirement(HeatUnit.GDD_BASE_0, 1000, 1500, BASIS)),
        crop(
            "hot_crop",
            season_model=SeasonModel.WARM_SEASON,
            heat_requirement=HeatRequirement(HeatUnit.CROP_HEAT_UNITS, 9000, 9500, BASIS),
        ),
        crop(
            "legume_hay",
            category=CropCategory.PERENNIAL_FORAGE,
            season_model=SeasonModel.PERENNIAL,
            botanical_families=("Poaceae", "Fabaceae"),
            fixes_nitrogen=True,
        ),
        crop(
            "grass_hay",
            category=CropCategory.PERENNIAL_FORAGE,
            season_model=SeasonModel.PERENNIAL,
            fixes_nitrogen=None,
        ),
        crop("maple", category=CropCategory.PERENNIAL_WOODY, season_model=SeasonModel.PERENNIAL),
    ]
)


def rotation(id_: str, *crops: str) -> CropRotation:
    return CropRotation(id_, id_, crops, RotationOrigin.TEMPLATE, rationale_fr=f"Raison {id_}.")


FARM = FarmProfile(
    name="test",
    location=GeoPoint(48, -70),
    location_precision=LocationPrecision.EXACT,
    current_rotation=CropRotation(
        "current", "actuelle", ("cereal", "grass_hay"), RotationOrigin.DECLARED_BY_FARMER
    ),
)
CONTEXTS = build_year_contexts(48.0, [make_year(y, seasonal) for y in (2001, 2002, 2003)])
TEMPLATES = [
    rotation("hot", "hot_crop", "cereal"),
    rotation("legume", "cereal", "legume_hay", "legume_hay"),
    rotation("plain", "cereal", "cereal", "grass_hay"),
]


def test_blocking_constraints_come_first() -> None:
    result = compare_rotations(FARM, TEMPLATES, CATALOG, CONTEXTS)
    hot = next(c for c in result.considered if c.evaluated.rotation.id == "hot")
    assert not hot.evaluated.admissible
    assert "100 %" in hot.evaluated.blocking_reasons_fr[0]
    roles = [s.role for s in result.strategies]
    assert roles == [
        StrategyRole.CURRENT,
        StrategyRole.RESILIENCE_AND_SOIL,
        StrategyRole.FARMER_PRIORITIES,
    ]
    assert result.strategies[1].evaluated.rotation.id == "legume"


def test_unknown_benefits_are_not_credited_and_income_is_never_ranked() -> None:
    result = compare_rotations(FARM, TEMPLATES, CATALOG, CONTEXTS)
    current = result.strategies[0].evaluated
    assert current.soil.legume_share == 0 and current.soil.unknown_legume_share == 0.5
    used = {s.criterion: s.used_in_ranking for s in result.criteria_status}
    assert used[Criterion.POTENTIAL_INCOME] is False
    assert used[Criterion.WATER_CONSERVATION] is False  # no water need documented here


def test_explanations_only_state_existing_differences() -> None:
    result = compare_rotations(FARM, TEMPLATES, CATALOG, CONTEXTS)
    legume = result.strategies[1].explanation
    texts = " ".join(s.text_fr for s in legume.of_kind(StatementKind.BENEFIT))
    assert "légumineuse" in texts
    assert not any("Moins exposée" in s.text_fr for s in legume.statements)  # equal exposure


def test_user_can_pick_the_alternatives() -> None:
    result = compare_rotations(FARM, TEMPLATES, CATALOG, CONTEXTS, selected_template_ids=["plain"])
    assert [s.role for s in result.strategies] == [StrategyRole.CURRENT, StrategyRole.USER_SELECTED]


def test_farmer_priorities_drive_the_second_alternative() -> None:
    farm = FarmProfile(
        **{
            **{f: getattr(FARM, f) for f in FARM.__dataclass_fields__},
            "priorities": FarmerPriorities(0, 0, 3, 3),
        }
    )
    result = compare_rotations(farm, TEMPLATES, CATALOG, CONTEXTS)
    assert any("aucun critère évaluable" in n for n in result.notes_fr)


def test_woody_perennials_are_refused_in_a_rotation() -> None:
    with pytest.raises(InvalidRotationError, match="ligneuse"):
        validate_rotation(rotation("bad", "cereal", "maple"), CATALOG)
