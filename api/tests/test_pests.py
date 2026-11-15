"""The "ravageurs" criterion: the catalogue of organisms, the pressure model and the score.

The landmarks of algorithm/pests/README.md (monoculture ≈ 0, delay just respected ≈ 1 − ε,
varied rotation ≈ 1, shared disease between families, history, declared disease) are the tests
of the criterion.
"""

from __future__ import annotations

import random
from dataclasses import replace

import pytest

from field_shift.algorithm.delays.occupation import Occupation, OccupationSource
from field_shift.algorithm.delays.return_delay_checker import ReturnDelayChecker
from field_shift.algorithm.pests.pest_catalog import PestCatalog
from field_shift.algorithm.pests.pest_criterion import PestCriterion
from field_shift.algorithm.pests.pest_data import DEFAULT_SEVERITY, PESTS, PestType
from field_shift.algorithm.pests.pest_explanations import years_text
from field_shift.algorithm.pests.pest_settings import DEFAULT_PRESSURE_PARAMS
from field_shift.algorithm.pests.pressure_model import decay_per_year, pressure_by_year
from field_shift.reference.crops import CROP_NAMES
from field_shift.reference.return_delays import CROP_DELAYS, SOIL_DISEASES

EPSILON = DEFAULT_PRESSURE_PARAMS.acceptable
Y = 2030


def occ(crop: str, first: int, last: int | None = None, source=OccupationSource.CHAIN):
    return Occupation(crop, first, first if last is None else last, source)


def annual(*crops: str, start: int = Y) -> list[Occupation]:
    """One crop a year, in order."""
    return [occ(crop, start + i) for i, crop in enumerate(crops)]


def criterion(cycle_years: int, history=None, diseases=(), **params) -> PestCriterion:
    checker = ReturnDelayChecker(cycle_years, history, diseases)
    return PestCriterion(checker, params=replace(DEFAULT_PRESSURE_PARAMS, **params))


def score(chain, cycle_years, history=None, diseases=(), closed=True, **params) -> float:
    result = criterion(cycle_years, history, diseases, **params).evaluate(chain, closed)
    assert result is not None
    return result.score


# ------------------------------------------------------------------ the catalogue


class TestCatalogue:
    def test_every_organism_has_a_source_and_valid_numbers(self):
        for pest in PESTS.values():
            assert pest.sources, pest.id
            assert pest.years_without_host > 0, pest.id
            assert pest.severity > 0, pest.id
            assert pest.hosts, pest.id
            for host in pest.hosts:
                assert host.crop_id in CROP_NAMES, (pest.id, host.crop_id)
                assert 0 < host.sensitivity <= 1, (pest.id, host.crop_id)

    def test_the_20_soil_diseases_of_sare_are_all_there_with_the_high_end_of_their_range(self):
        for disease_id, disease in SOIL_DISEASES.items():
            pest = PESTS[disease_id]
            assert pest.years_without_host == disease.high
            assert {h.crop_id for h in pest.hosts} == set(disease.hosts)

    def test_a_crop_with_a_fruchtfolge_break_has_its_own_complex(self):
        for crop_id, row in CROP_DELAYS.items():
            pest = PESTS.get(f"fruchtfolge-{crop_id}")
            if row.fruchtfolge_years_without:
                assert pest is not None, crop_id
                assert pest.years_without_host == row.fruchtfolge_years_without
                assert pest.type is PestType.CROP_COMPLEX
            else:
                assert pest is None, crop_id  # hay (no break) and tomato (no value)

    def test_the_corn_rootworm_lives_on_corn_only_and_one_year_of_another_crop_breaks_it(self):
        pest = PESTS["chrysomele-racines-mais"]
        assert [h.crop_id for h in pest.hosts] == ["mais"]
        assert pest.years_without_host == 1
        assert pest.type is PestType.SOIL_INSECT

    def test_the_soybean_cyst_nematode_is_a_nematode(self):
        assert PESTS["nematode-kyste-soya"].type is PestType.NEMATODE

    def test_severity_is_neutral_until_the_sources_can_tell_organisms_apart(self):
        assert {p.severity for p in PESTS.values()} == {DEFAULT_SEVERITY}
        # The losses the sources report are kept for later, and are not used by the score.
        assert PESTS["nematode-kyste-soya"].reported_yield_loss == pytest.approx(0.30)
        assert PESTS["fusariose"].reported_yield_loss == pytest.approx(0.15)

    def test_a_crop_with_no_organism_is_known_as_such(self):
        catalog = PestCatalog()
        assert catalog.pests_of("foin") == ()
        assert {p.id for p in catalog.pests_of("mais")} >= {"fusariose", "chrysomele-racines-mais"}


# ------------------------------------------------------------------ the pressure model


def trace(host_years, first, last, years_without_host=4, growth=1.0, start=0.0, floor_at=None):
    return pressure_by_year(
        host_years, first, last, years_without_host, EPSILON, growth, start, floor_at
    )


class TestPressureModel:
    def test_after_the_delay_without_a_host_a_full_pressure_falls_to_epsilon(self):
        for years in (1, 2, 4, 7):
            states = trace({}, 0, years - 1, years, start=1.0)
            assert states[years].pressure == pytest.approx(EPSILON)
            assert decay_per_year(years, EPSILON) ** years == pytest.approx(EPSILON)

    def test_a_longer_delay_means_a_slower_decay(self):
        assert decay_per_year(7, EPSILON) > decay_per_year(2, EPSILON)

    def test_a_year_of_main_host_fills_the_pressure_at_g_1_and_never_goes_over_1(self):
        states = trace({0: (1.0, "soya"), 1: (1.0, "soya")}, 0, 3)
        assert states[0].pressure == 0
        assert states[1].pressure == 1.0
        assert states[2].pressure == 1.0
        assert states[3].pressure == pytest.approx(decay_per_year(4, EPSILON))

    def test_a_secondary_host_or_a_slow_growth_raises_it_less(self):
        assert trace({0: (0.5, "x")}, 0, 1)[1].pressure == pytest.approx(0.5)
        assert trace({0: (1.0, "x")}, 0, 1, growth=0.5)[1].pressure == pytest.approx(0.5)

    def test_the_last_host_is_remembered_until_another_one(self):
        states = trace({1: (1.0, "soya"), 4: (1.0, "pois")}, 0, 6)
        assert states[1].last_host is None
        assert states[3].last_host == ("soya", 1)
        assert states[6].last_host == ("pois", 4)

    def test_a_declared_disease_raises_the_pressure_to_the_floor_and_is_nobodys_fault(self):
        states = trace({}, 0, 3, floor_at={2: 1.0})
        assert states[1].pressure < 1.0
        assert states[2].pressure == 1.0
        assert states[2].last_host is None
        assert states[3].pressure == pytest.approx(decay_per_year(4, EPSILON))

    def test_a_delay_of_zero_is_refused(self):
        with pytest.raises(ValueError, match="at least one year"):
            decay_per_year(0, EPSILON)


# ------------------------------------------------------------------ the landmarks


class TestLandmarks:
    def test_a_monoculture_of_a_crop_with_organisms_scores_about_0(self):
        assert score(annual("mais", "mais", "mais", "mais"), 4) < 0.05

    def test_the_recommended_delay_just_respected_scores_1_minus_epsilon(self):
        # Celery: its two organisms both ask 2 years without a host; the cycle leaves exactly 2.
        assert score([occ("celeri", Y)], 3) == pytest.approx(1 - EPSILON)

    def test_every_year_of_break_beyond_helps(self):
        scores = [score([occ("celeri", Y)], cycle) for cycle in (1, 2, 3, 4, 6)]
        assert scores == sorted(scores)
        assert scores[0] == pytest.approx(0.0, abs=0.01)
        assert scores[-1] > 0.99

    def test_a_long_rotation_of_five_families_scores_above_0_9(self):
        chain = annual("mais", "soya", "betterave", "orge", "celeri")
        assert score(chain, 5) >= 0.9
        assert score(chain, 5) > score(annual("mais", "mais", "soya", "soya", "celeri"), 5)

    def test_two_crops_of_different_families_that_share_a_disease_cost_points(self):
        # White mould hosts both soybean and canola. The return delays only gave a warning.
        close = [occ("soya", Y), occ("canola", Y + 1)]
        far = [occ("soya", Y), occ("sarrasin", Y + 1), occ("canola", Y + 2)]
        assert score(close, 6, closed=False) < score(far, 6, closed=False)
        checker = ReturnDelayChecker(6)
        assert checker.pest_score(close, closed=False) == checker.pest_score(far, closed=False)

    def test_wheat_after_corn_is_a_risk_although_grasses_are_exempt_from_the_family_rule(self):
        assert score(annual("mais", "ble-automne", "soya", "canola"), 4) < score(
            annual("mais", "soya", "ble-automne", "canola"), 4
        )

    def test_what_grew_before_counts(self):
        chain = annual("canola", "orge", "mais")
        after_canola = [occ("canola", Y - 1, source=OccupationSource.HISTORY)]
        after_barley = [occ("orge", Y - 1, source=OccupationSource.HISTORY)]
        assert score(chain, 3, after_canola) < score(chain, 3, after_barley) - 0.05

    def test_a_disease_the_farmer_declares_is_more_severe_than_the_same_without_it(self):
        chain = annual("mais", "canola", "orge", "soya", "ble-automne", "mais", "pois", "orge")
        without = score(chain, 8)
        declared = score(chain, 8, diseases=("hernie-cruciferes",))
        assert declared < without
        # The mean over the organisms of a crop dilutes one of them; the worst case does not.
        gap = without - declared
        assert (
            score(chain, 8, worst_case_weight=0.3)
            - score(chain, 8, diseases=("hernie-cruciferes",), worst_case_weight=0.3)
        ) > gap

    def test_a_crop_with_no_known_organism_has_no_risk_and_a_lower_confidence(self):
        only_hay = criterion(3).evaluate([occ("foin", Y, Y + 2)])
        assert (only_hay.score, only_hay.confidence) == (1.0, 0.0)
        mixed = criterion(4).evaluate([occ("foin", Y, Y + 1), occ("mais", Y + 2)])
        assert mixed.confidence == pytest.approx(0.5)

    def test_no_crop_no_score(self):
        assert criterion(3).evaluate([]) is None


# ------------------------------------------------------------------ what the module gives back


class TestResult:
    def test_the_result_gives_sub_scores_sentences_and_confidence(self):
        chain = [occ("soya", Y), occ("canola", Y + 1), occ("orge", Y + 2), occ("mais", Y + 3)]
        result = criterion(4).evaluate(chain)
        assert 0 <= result.score <= 1
        assert set(result.details) >= {
            "pression_maladie_sol",
            "pression_nematode",
            "pression_insecte_sol",
            "pression_complexe_culture",
            "pire_cas",
            "diversite_familles",
        }
        # Soybean, canola, and two grasses (barley, corn): 3 families.
        assert result.details["diversite_familles"] == 3
        assert result.confidence == 1.0
        text = " ".join(result.explanations)
        assert "Soya" in text
        assert "moisissure blanche" in text
        assert "pour 5 conseillés" in text

    def test_the_years_without_a_host_are_written_in_good_french(self):
        # 0 and 1 take the singular in French: "0 an sans hôte", not "0 ans".
        assert [years_text(n) for n in (0, 1, 2, 5)] == ["0 an", "1 an", "2 ans", "5 ans"]

    def test_a_disease_the_farmer_declared_says_so(self):
        chain = annual("mais", "canola", "orge", "soya")
        result = criterion(4, diseases=("hernie-cruciferes",)).evaluate(chain)
        assert any("déclarée" in s for s in result.explanations)

    def test_the_sentences_are_left_out_on_request_and_for_nobody_to_read_twice(self):
        chain = annual("mais", "mais", "mais", "mais")
        quiet = criterion(4).evaluate(chain, explain=False)
        assert quiet.explanations == []
        loud = criterion(4).evaluate(chain)
        assert 0 < len(loud.explanations) <= 6
        assert len(set(loud.explanations)) == len(loud.explanations)

    def test_the_cycle_that_repeats_is_told_apart_when_it_is_worse_than_the_first(self):
        history = [occ("orge", Y - 1, source=OccupationSource.HISTORY)]
        result = criterion(3, history).evaluate(annual("canola", "orge", "mais"))
        assert any(s.startswith("Au cycle suivant") for s in result.explanations)

    def test_the_same_chain_gives_the_same_object(self):
        crit = criterion(4)
        chain = annual("mais", "soya", "orge", "canola")
        assert crit.evaluate(chain) is crit.evaluate(chain)

    def test_a_partial_chain_is_scored_without_its_repetition(self):
        crit = criterion(4)
        partial = annual("soya", "mais")
        assert crit.evaluate(partial, closed=False).score != crit.evaluate(partial).score

    def test_the_score_of_any_chain_is_between_0_and_1(self):
        rnd = random.Random(7)
        crops = [c for c in CROP_DELAYS if c not in {"foin", "luzerne"}]
        for _ in range(200):
            years = rnd.randint(2, 7)
            chain = annual(*(rnd.choice(crops) for _ in range(years)))
            diseases = tuple(rnd.sample(sorted(SOIL_DISEASES), rnd.randint(0, 2)))
            history = (
                [occ(rnd.choice(crops), Y - 1, source=OccupationSource.HISTORY)]
                if rnd.random() < 0.5
                else None
            )
            result = criterion(years, history, diseases).evaluate(chain)
            assert 0.0 <= result.score <= 1.0
            assert 0.0 <= result.details["pire_cas"] <= 1.0

    def test_a_perennial_raises_the_pressure_during_all_its_years(self):
        # Alfalfa 3 years then alfalfa again: the second stand starts on a soil it just left.
        close = [occ("luzerne", Y, Y + 2), occ("mais", Y + 3), occ("luzerne", Y + 4, Y + 6)]
        far = [occ("luzerne", Y, Y + 2), occ("mais", Y + 3), occ("soya", Y + 4), occ("orge", Y + 5)]
        assert score(close, 7, closed=False) < score(far, 7, closed=False)
