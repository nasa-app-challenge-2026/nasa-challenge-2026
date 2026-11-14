"""The soil protection measure: rotations, the Rotation Protection Index, RUSLE, infiltration."""

from __future__ import annotations

import math

import pytest

from field_shift.algorithm.config.soil_protection import (
    CONSOLIDATED_SOIL_LOSS_RATIO,
    SOIL_LOSS_TOLERANCE_T_HA_YEAR,
)
from field_shift.algorithm.rotation.rotation import Rotation, RotationStep, generate_rotations
from field_shift.algorithm.soil_protection.erosion import (
    bare_soil_loss_ratio,
    consolidation_subfactor,
    cover_management_factor,
    erodibility_from_texture,
    erosivity_from_annual_rain,
    estimate_erosion,
    slope_length_factor,
    slope_steepness_factor,
    topographic_factor,
)
from field_shift.algorithm.soil_protection.infiltration import (
    estimate_infiltration,
    moisture_factor,
    rotation_multiplier,
)
from field_shift.algorithm.soil_protection.protection_index import (
    ProtectionClass,
    protection_class,
    protection_index,
)
from field_shift.algorithm.soil_protection.soil_protection import evaluate_soil_protection
from field_shift.reference.crops import CROP_NAMES
from field_shift.reference.soil_protection import SOIL_PROTECTION_PROFILES
from tests.helpers.site_stub import site

SITE = site()


def rotation(*steps: str | tuple[str | None, float]) -> Rotation:
    """A rotation from crop ids ("mais") and (crop, months) pairs."""
    parsed = [RotationStep(s) if isinstance(s, str) else RotationStep(*s) for s in steps]
    return Rotation.from_steps("R", parsed)


class TestRotation:
    def test_a_crop_alone_takes_its_season_then_leaves_the_soil_bare_until_the_year_ends(self):
        phases = rotation("mais", "soya").phases
        assert [(p.crop_id, p.months) for p in phases] == [
            ("mais", 6),
            (None, 6),
            ("soya", 5),
            (None, 7),
        ]

    def test_given_months_are_kept_as_written(self):
        cycle = rotation(("ble-automne", 10), ("seigle", 8), ("mais", 6))
        assert cycle.cycle_months == 24 and all(p.crop_id for p in cycle.phases)

    def test_a_perennial_kept_several_years_is_one_stand(self):
        by_sheet = rotation("luzerne-3", "mais")
        by_years = rotation("luzerne", "luzerne", "luzerne", "mais")
        assert by_sheet.phases == by_years.phases
        assert by_sheet.phases[0].months == 36 and by_sheet.name == "Luzerne ×3 → Maïs"

    def test_the_timeline_repeats_the_cycle_and_stops_with_the_simulation(self):
        timeline = rotation("mais", "soya").timeline(30)
        assert sum(p.months for p in timeline) == 30
        assert [p.crop_id for p in timeline] == ["mais", None, "soya", None, "mais"]

    @pytest.mark.parametrize(
        "steps, message",
        [
            ([RotationStep("riz")], "culture inconnue"),
            ([RotationStep(None, 6)], "au moins une culture"),
            ([RotationStep(None)], "sol nu"),
            ([RotationStep("mais", 0)], "positive"),
            ([], "au moins une culture"),
        ],
    )
    def test_a_rotation_that_cannot_be_is_refused(self, steps, message):
        with pytest.raises(ValueError, match=message):
            Rotation.from_steps("R", steps)

    def test_generated_rotations_give_each_cycle_once(self):
        rotations = generate_rotations(["mais", "soya"], 2, limit=10)
        assert [r.crop_ids for r in rotations] == [
            ("mais", "mais"),
            ("mais", "soya"),
            ("soya", "soya"),
        ]
        assert [r.id for r in rotations] == ["R1", "R2", "R3"]

    def test_too_many_generated_rotations_are_refused(self):
        with pytest.raises(ValueError, match="plus de 5 rotations"):
            generate_rotations(["mais", "soya", "orge"], 4, limit=5)


class TestProtectionIndex:
    def test_every_crop_has_a_soil_protection_sheet(self):
        assert set(SOIL_PROTECTION_PROFILES) == set(CROP_NAMES)

    def test_the_examples_of_the_matrix(self):
        scores = {
            crop: (p.infiltration, p.residue, p.cover)
            for crop, p in SOIL_PROTECTION_PROFILES.items()
        }
        assert scores["soya"][:2] == (1, 1)  # short taproot, low residue
        assert scores["mais"][:2] == (3, 4)  # deep taproot, high residue
        assert scores["ble-automne"][1:] == (3, 3)
        assert scores["luzerne"][0] == 5 and scores["foin"] == (5, 5, 5)
        assert scores["pomme-de-terre"] == (1, 1, 1)

    def test_the_rpi_is_the_scores_weighted_by_the_months(self):
        # Maize: SC = (3 + 4 + 2) / 3 = 3 for 6 months; bare soil: 1 for 6 months.
        index = protection_index(rotation("mais").timeline(12), SITE)
        assert index.rpi == pytest.approx(3 * 6 / 12 + 1 * 6 / 12)
        assert sum(p.weighted for p in index.phases) == pytest.approx(index.rpi)

    def test_the_bounds_of_the_rpi(self):
        assert protection_index(rotation("jachere").timeline(12), SITE).rpi == 1
        assert protection_index(rotation("foin").timeline(12), SITE).rpi == 5

    def test_the_three_classes(self):
        assert protection_class(2.49) is ProtectionClass.HIGH_RISK
        assert protection_class(2.5) is ProtectionClass.MODERATE
        assert protection_class(3.99) is ProtectionClass.MODERATE
        assert protection_class(4.0) is ProtectionClass.EXCELLENT

    def test_a_weak_canopy_lowers_the_adjusted_index_only(self):
        timeline = rotation("foin").timeline(12)
        healthy = protection_index(timeline, site(ndvi=0.85, root_activity=1))
        weak = protection_index(timeline, site(ndvi=0.3, root_activity=0.5))
        assert healthy.adjusted_rpi == healthy.rpi == weak.rpi == 5
        assert 1 < weak.adjusted_rpi < 5

    def test_the_simulation_length_changes_what_the_field_goes_through(self):
        cycle = rotation("luzerne-3", "mais", "soya")
        short = protection_index(cycle.timeline(36), SITE)  # only the alfalfa
        full = protection_index(cycle.timeline(60), SITE)
        assert short.rpi > full.rpi


class TestErosion:
    def test_the_unit_plot_has_an_ls_of_one(self):
        assert slope_length_factor(22.13, 9) == pytest.approx(1)
        assert slope_steepness_factor(9) == pytest.approx(1, abs=0.01)
        assert topographic_factor(9, 22.13) == pytest.approx(1, abs=0.01)

    def test_ls_grows_with_the_slope_and_with_its_length(self):
        assert topographic_factor(2, 60) < topographic_factor(6, 60) < topographic_factor(12, 60)
        assert topographic_factor(6, 30) < topographic_factor(6, 120)
        # Flat land: the length hardly matters (interrill erosion only).
        assert slope_length_factor(200, 0) == pytest.approx(1)

    def test_the_slope_is_bounded_to_what_rusle_accepts(self):
        assert topographic_factor(250, 60) == topographic_factor(100, 60)
        assert topographic_factor(6, 5000) == topographic_factor(6, 304.8)

    def test_erosivity_grows_with_the_rain_and_is_continuous_enough_at_850_mm(self):
        assert erosivity_from_annual_rain(0) == 0
        assert erosivity_from_annual_rain(400) < erosivity_from_annual_rain(800)
        below, above = erosivity_from_annual_rain(850), erosivity_from_annual_rain(850.1)
        assert above == pytest.approx(below, rel=0.05)
        assert erosivity_from_annual_rain(1000) == pytest.approx(3473.8)

    def test_silt_erodes_most_and_organic_matter_protects(self):
        silt_loam = erodibility_from_texture(20, 65, 15, 3)
        sand = erodibility_from_texture(90, 5, 5, 3)
        clay = erodibility_from_texture(20, 20, 60, 3)
        assert silt_loam > clay and silt_loam > sand
        assert erodibility_from_texture(40, 40, 20, 1) > erodibility_from_texture(40, 40, 20, 6)
        assert 0 < silt_loam < 0.1  # SI units
        assert erodibility_from_texture(100, 0, 0, 0) == 0  # pure sand: no division by zero

    def test_bare_tilled_soil_has_a_c_of_one(self):
        assert cover_management_factor(rotation("jachere").timeline(12)) == 1

    def test_residue_protects_the_soil_after_the_harvest_then_decays(self):
        assert bare_soil_loss_ratio(0, 6) == 1
        assert bare_soil_loss_ratio(65, 1) < bare_soil_loss_ratio(65, 12) < 1

    def test_c_orders_the_rotations_as_agronomy_does(self):
        def c_factor(cycle: Rotation) -> float:
            return cover_management_factor(cycle.timeline(cycle.cycle_months * 4))

        hay, alfalfa_maize = c_factor(rotation("foin")), c_factor(rotation("luzerne-3", "mais"))
        maize_soy, potato = c_factor(rotation("mais", "soya")), c_factor(rotation("pomme-de-terre"))
        assert 0 < hay < alfalfa_maize < maize_soy < potato < 1

    def test_a_cover_crop_lowers_c(self):
        without = rotation(("mais", 6), (None, 6))
        with_rye = rotation(("mais", 6), ("seigle", 6))
        assert cover_management_factor(with_rye.timeline(24)) < cover_management_factor(
            without.timeline(24)
        )

    def test_a_weak_canopy_raises_c(self):
        timeline = rotation("mais", "soya").timeline(24)
        assert cover_management_factor(timeline, vigour=0.3) > cover_management_factor(timeline)

    def test_consolidation_takes_seven_years(self):
        assert consolidation_subfactor(0) == 1
        assert consolidation_subfactor(3) > consolidation_subfactor(7)
        assert consolidation_subfactor(7) == pytest.approx((1 + CONSOLIDATED_SOIL_LOSS_RATIO) / 2)
        assert consolidation_subfactor(1000) == pytest.approx(
            CONSOLIDATED_SOIL_LOSS_RATIO, abs=0.01
        )

    def test_the_soil_loss_is_the_product_of_the_five_factors(self):
        timeline = rotation("mais", "soya").timeline(24)
        conditions = site(r_factor=2000, k_factor=0.03, support_practice_factor=0.5)
        erosion = estimate_erosion(timeline, conditions)
        assert (erosion.r_factor, erosion.k_factor, erosion.p_factor) == (2000, 0.03, 0.5)
        assert erosion.soil_loss_t_ha_year == pytest.approx(
            2000 * 0.03 * erosion.ls_factor * erosion.c_factor * 0.5
        )
        assert erosion.score == pytest.approx(
            1 / (1 + erosion.soil_loss_t_ha_year / SOIL_LOSS_TOLERANCE_T_HA_YEAR)
        )


class TestInfiltration:
    def test_the_gains_of_the_meta_analysis(self):
        assert rotation_multiplier(rotation("mais", "soya").timeline(24)) == 1
        assert rotation_multiplier(rotation("foin").timeline(12)) == pytest.approx(1.592)
        assert rotation_multiplier(rotation(("seigle", 12)).timeline(12)) == pytest.approx(1.348)
        # Half of the time under a perennial: half of the gain.
        half = rotation(("luzerne", 12), ("mais", 12)).timeline(24)
        assert rotation_multiplier(half) == pytest.approx(1 + 0.592 / 2)

    def test_idle_roots_give_less(self):
        timeline = rotation("foin").timeline(12)
        assert rotation_multiplier(timeline, root_vigour=0.5) == pytest.approx(1 + 0.592 / 2)

    def test_a_saturated_soil_takes_almost_nothing(self):
        assert moisture_factor(0) == 1
        assert moisture_factor(1) == pytest.approx(0.1)

    def test_the_share_of_the_storm_that_enters_the_soil(self):
        timeline = rotation("foin").timeline(12)
        loam = estimate_infiltration(timeline, site(ksat_mm_h=10))
        assert loam.effective_mm_h == pytest.approx(15.92)
        assert loam.infiltrated_share == pytest.approx(15.92 / 25)
        sand = estimate_infiltration(timeline, site(ksat_mm_h=100))
        assert sand.infiltrated_share == 1  # the whole storm
        wet = estimate_infiltration(timeline, site(ksat_mm_h=10, soil_saturation=0.5))
        assert wet.effective_mm_h == pytest.approx(15.92 * 0.55)


class TestSoilProtection:
    def test_the_score_goes_from_bare_soil_to_permanent_grass(self):
        fallow = evaluate_soil_protection(rotation("jachere"), SITE, 60)
        maize_soy = evaluate_soil_protection(rotation("mais", "soya"), SITE, 60)
        hay = evaluate_soil_protection(rotation("foin"), SITE, 60)
        assert 0 <= fallow.score < maize_soy.score < hay.score <= 1

    def test_the_same_rotation_is_worth_less_on_a_steeper_field(self):
        cycle = rotation("mais", "soya")
        flat = evaluate_soil_protection(cycle, site(slope_pct=1), 24)
        steep = evaluate_soil_protection(cycle, site(slope_pct=12), 24)
        assert steep.erosion.soil_loss_t_ha_year > flat.erosion.soil_loss_t_ha_year
        assert steep.score < flat.score
        assert steep.index.rpi == flat.index.rpi  # the theory does not see the field

    def test_the_soil_lost_over_the_simulation(self):
        result = evaluate_soil_protection(rotation("mais", "soya"), SITE, 48)
        assert result.cumulative_soil_loss_t_ha == pytest.approx(
            4 * result.erosion.soil_loss_t_ha_year
        )
        assert math.isfinite(result.score)
