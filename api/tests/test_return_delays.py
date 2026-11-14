"""Return delays (part B) and weights (step 1) against the reference (field_shift.py v5.1)."""

from __future__ import annotations

import pytest

from field_shift.algorithm.chain.chain_step import ChainStep
from field_shift.algorithm.delays.field_history import CropInPlace, PastCrop, field_history
from field_shift.algorithm.delays.occupation import Occupation, OccupationSource
from field_shift.algorithm.delays.return_delay_catalog import DEFAULT_DELAY_CATALOG as CATALOG
from field_shift.algorithm.delays.return_delay_checker import (
    ReturnDelayChecker,
    history_depth,
    impossible_crops,
)
from field_shift.algorithm.planning.priorities import weights_from_ranking
from field_shift.algorithm.report.messages import (
    impossible_text,
    rule_reason_text,
    shared_disease_text,
)
from field_shift.reference.crops import SHEETS
from tests.helpers.reference_names import crop_id_of, disease_id_of, fixture, id_of, plain

REF = fixture("delays.json")


def occupations(raw: list) -> list[Occupation]:
    return [
        Occupation(crop_id_of(crop), first, last, OccupationSource(source))
        for crop, first, last, source in raw
    ]


def assert_same_violations(actual, expected) -> None:
    assert [plain(rule_reason_text(v.reason)) for v in actual] == [
        plain(v["raison"]) for v in expected
    ]
    assert [
        (
            v.years_without,
            v.minimum,
            v.start.year,
            v.start.source.value,
            v.end.year,
            v.end.source.value,
        )
        for v in actual
    ] == [
        (v["annees_sans"], v["minimum"], v["de"][0], v["de"][1], v["a"][0], v["a"][1])
        for v in expected
    ]


def test_every_crop_has_the_reference_minimum_and_recommended_delay():
    for name, delay in REF["delays"].items():
        mine = CATALOG.get(crop_id_of(name))
        assert (mine.minimum, mine.recommended, mine.family, mine.perennial) == (
            delay["minimum"],
            delay["recommande"],
            delay["famille"],
            delay["perenne"],
        ), name


@pytest.mark.parametrize("case", REF["cases"], ids=lambda c: c["name"])
def test_a_chain_is_checked_like_the_reference(case):
    checker = ReturnDelayChecker(
        cycle_years=case["C"],
        history=occupations(case["historique"]) if case["historique"] is not None else None,
        diseases=[disease_id_of(m) for m in case["maladies"]],
    )
    chain = occupations(case["occs"])
    verdict = checker.check(chain)

    assert verdict.ok is case["ok"]
    assert_same_violations(verdict.violations, case["violations"])
    assert [plain(shared_disease_text(w)) for w in verdict.warnings] == [
        plain(v) for v in case["vigilances"]
    ]
    assert verdict.pest_score == pytest.approx(case["note_ravageurs"], rel=1e-12)

    partial = chain[:2]
    assert_same_violations(checker.violations(partial, closed=False), case["partial"]["violations"])
    assert checker.pest_score(partial, closed=False) == pytest.approx(
        case["partial_note"], rel=1e-12
    )
    assert checker.is_allowed(partial, closed=False) is case["partial"]["ok"]


def test_crops_whose_delay_does_not_fit_in_the_cycle_are_removed():
    sheets = [SHEETS[i] for i in ("mais", "soya", "canola", "luzerne-2", "luzerne-3", "foin-3")]
    for case in REF["impossible"]:
        cycle_years = case["C"]
        removed = impossible_crops(
            cycle_years, sheets, [disease_id_of(m) for m in case["maladies"]]
        )
        expected = {id_of(name): plain(text) for name, text in case["result"].items()}
        for sheet_id, text in expected.items():
            if sheet_id in SHEETS:
                assert plain(impossible_text(sheet_id, removed[sheet_id], cycle_years)) == text
        assert set(removed) == {i for i in expected if i in SHEETS}


def test_history_depth_is_the_longest_delay_and_at_least_3_years():
    for case in REF["history_depth"]:
        crops = [crop_id_of(c) for c in case["cultures"]]
        diseases = [disease_id_of(m) for m in case["maladies"]]
        assert history_depth(crops, diseases) == case["depth"]


def test_the_history_of_a_field_is_rebuilt_like_the_reference():
    for case in REF["history"]:
        sheet = SHEETS[id_of(case["culture_en_place"])]
        free_year = 2000 + int(case["libre"] // 12)
        past = list(case["historique"])
        # The last year given, when it is the annual crop in place, is that crop itself.
        if past and not sheet.is_perennial and crop_id_of(past[-1]) == sheet.crop_id:
            past = past[:-1]
        entries = [
            PastCrop(free_year - 1 - i, crop_id_of(name)) for i, name in enumerate(reversed(past))
        ]
        history = field_history(
            CropInPlace(sheet.crop_id, sheet.production_years), free_year, entries
        )
        assert [(o.crop_id, o.first_year, o.last_year) for o in history] == [
            (crop_id_of(c), first, last) for c, first, last, _ in case["result"]
        ]


def test_a_crop_not_in_the_sheets_still_counts_in_the_history():
    history = field_history(CropInPlace("pomme-de-terre"), 2026, [PastCrop(2025, "mais")])
    assert [(o.crop_id, o.first_year, o.last_year) for o in history] == [
        ("mais", 2025, 2025),
        ("pomme-de-terre", 2026, 2026),
    ]


def test_weights_follow_the_rank_order_centroid():
    for case in REF["weights"]:
        weights = weights_from_ranking(case["classement"])
        assert weights == pytest.approx(case["base"], rel=1e-12)


def test_five_ranked_criteria_weigh_46_26_16_9_4_percent():
    ranking = ["rendement", "eau", "azote", "erosion", "marche"]
    weights = weights_from_ranking(ranking)
    assert [round(weights[c], 2) for c in ranking] == [0.46, 0.26, 0.16, 0.09, 0.04]
    assert weights["reserve"] == pytest.approx(0.25 * weights["marche"])


def test_a_chain_step_knows_its_sheet():
    step = ChainStep("luzerne-3", 40.0, 80.0, 1, 3)
    assert step.sheet.is_perennial and step.is_sold and not step.is_cover and not step.is_fallow
