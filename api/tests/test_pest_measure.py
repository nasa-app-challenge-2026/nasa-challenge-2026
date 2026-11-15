"""The "ravageurs" measure of the rotation ranking: from a `Rotation` (months) to the criterion
(years), and its place among the measures (see algorithm/pests/README.md)."""

from __future__ import annotations

import pytest

from field_shift.algorithm.delays.occupation import Occupation
from field_shift.algorithm.delays.return_delay_checker import ReturnDelayChecker
from field_shift.algorithm.pests.pest_criterion import PestCriterion
from field_shift.algorithm.pests.pest_measure import (
    cycles_for_whole_years,
    evaluate_pests,
    rotation_occupations,
)
from field_shift.algorithm.ranking.measures import PestsMeasure, SectionContext
from field_shift.algorithm.rotation.rotation import Rotation, RotationStep
from tests.helpers.site_stub import BASE_SITE


def rotation(*steps: str | tuple[str | None, float]) -> Rotation:
    """A rotation from crop ids ("mais") or (crop or None, months) pairs."""
    return Rotation.from_steps(
        "R1",
        [RotationStep(*step) if isinstance(step, tuple) else RotationStep(step) for step in steps],
    )


def years(rotation_to_read: Rotation, cycles: int = 1) -> list[tuple[str, int, int]]:
    return [
        (o.crop_id, o.first_year, o.last_year)
        for o in rotation_occupations(rotation_to_read, cycles)
    ]


def context(simulation_months: float = 48) -> SectionContext:
    # The measure reads the rotation only; the site is the soil protection test site.
    return SectionContext("A", 45.5, -73.0, BASE_SITE, simulation_months=simulation_months)


class TestFromMonthsToYears:
    def test_one_crop_a_year_gives_one_year_each(self):
        assert years(rotation("mais", "soya", "ble-automne")) == [
            ("mais", 0, 0),
            ("soya", 1, 1),
            ("ble-automne", 2, 2),
        ]

    def test_a_perennial_counts_from_its_sowing_to_its_last_harvest(self):
        assert years(rotation("luzerne-3", "mais")) == [("luzerne", 0, 2), ("mais", 3, 3)]

    def test_cover_crops_bare_soil_and_fallow_are_years_without_a_host(self):
        written = rotation(("ble-automne", 10), ("seigle", 8), (None, 2), ("mais", 4), "jachere")
        assert [crop for crop, _, _ in years(written)] == ["ble-automne", "mais"]

    def test_a_crop_counts_as_its_species(self):
        assert years(rotation(("ble-automne", 8), ("soya-2e", 4)))[1][0] == "soya"

    def test_a_cycle_of_18_months_is_played_twice_to_make_3_years(self):
        assert cycles_for_whole_years(18) == 2
        assert cycles_for_whole_years(24) == 1
        assert cycles_for_whole_years(30) == 2


class TestTheMeasure:
    def test_it_is_the_criterion_of_the_crops_of_the_field(self):
        written = rotation("mais", "soya", "ble-automne", "canola")
        expected = PestCriterion(ReturnDelayChecker(4)).evaluate(
            [Occupation(crop, year, year) for year, crop in enumerate(written.crop_ids)]
        )
        assert evaluate_pests(written).result == expected

    def test_a_monoculture_scores_0_and_a_long_rotation_scores_better(self):
        monoculture = evaluate_pests(rotation("mais")).result.score
        short = evaluate_pests(rotation("mais", "soya")).result.score
        long = evaluate_pests(rotation("mais", "soya", "ble-automne", "canola", "luzerne")).result
        assert monoculture == pytest.approx(0.0)
        assert monoculture < short < long.score <= 1

    def test_a_rotation_with_no_known_crop_has_no_score_rather_than_a_perfect_one(self):
        result = PestsMeasure().evaluate(rotation("foin"), context())
        assert not result.available and result.score is None and "Foin" in result.note

    def test_a_rotation_of_cover_crops_only_has_no_score(self):
        result = PestsMeasure().evaluate(rotation(("seigle", 12)), context())
        assert not result.available and "pas de culture récoltée" in result.note

    def test_the_note_names_the_crops_without_data_and_says_why_a_crop_is_exposed(self):
        result = PestsMeasure().evaluate(rotation("mais", "soya", "foin"), context())
        assert result.available and 0 <= result.score <= 1
        assert result.note.startswith("Aucune donnée de ravageurs pour : Foin")
        assert "sans hôte" in result.note

    def test_the_length_of_the_simulation_does_not_change_it(self):
        written = rotation("mais", "soya", "ble-automne")
        short = context(simulation_months=12)
        assert PestsMeasure().evaluate(written, short) == PestsMeasure().evaluate(
            written, context()
        )
