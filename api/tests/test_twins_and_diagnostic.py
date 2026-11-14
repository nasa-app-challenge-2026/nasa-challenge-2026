"""Steps 4 to 8 against the reference implementation (field_shift.py v5.1)."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pytest
from scipy.stats import chi

from field_shift.algorithm.climate.indicator_table import IndicatorTable
from field_shift.algorithm.climate.target_climate_projector import ClimateTarget
from field_shift.algorithm.config.climate import GOOD_TWIN_MAX_SIGMA
from field_shift.algorithm.diagnostic.parcel_diagnostic import FieldMeasures, ParcelDiagnostic
from field_shift.algorithm.twins.climate_twin_finder import ClimateTwinFinder, GridCell
from field_shift.algorithm.twins.precrop_value import (
    FieldYear,
    NdviPercentiles,
    precrop_value,
    yield_gap_from_ndvi,
)
from field_shift.algorithm.twins.rotation_pattern import rotation_of
from field_shift.algorithm.twins.sigma_dissimilarity import (
    sigma_dissimilarities,
    sigma_dissimilarity,
)
from field_shift.algorithm.twins.soil_comparison import Soil, SoilFilter, soil_distance
from field_shift.algorithm.twins.twin_evidence_builder import TwinField, build_twin_evidence
from tests.helpers.reference_names import fixture, infinite

TWINS = fixture("twins.json")
STEPS = fixture("steps-5-to-8.json")
PRESENT = np.array(TWINS["present"])  # (years, cells, 5)
FUTURE = np.array(TWINS["future"])
#: Beyond this sigma the reference loses digits (see test_sigma_of_every_cell_is_the_reference_one).
FAR_SIGMA = 5


def soil_of(raw: dict) -> Soil:
    return Soil(raw["argile"], raw["sable"], raw["soc"], raw["ph"])


def field_years_of(rows: list[dict]) -> list[FieldYear]:
    return [FieldYear(r["culture"], r["precedent"], r["ecart"]) for r in rows]


class TestClimateTwins:
    def test_sigma_of_every_cell_is_the_reference_one(self):
        for cell, raw in enumerate(TWINS["sigma"]):
            expected = infinite(raw)
            sigma = sigma_dissimilarity(FUTURE, PRESENT[:, cell, :])
            if math.isinf(expected):
                assert sigma > FAR_SIGMA, f"cell {cell}"
                continue
            # Up to ~5σ both read the same percentile. Beyond, the reference rounds 1 − 1e-12
            # and loses digits (or returns inf): the upper tail is the accurate one.
            tolerance = 1e-9 if expected < FAR_SIGMA else 1e-2
            assert sigma == pytest.approx(expected, rel=tolerance, abs=1e-9), f"cell {cell}"

    def test_vectorised_sigma_matches_one_place_at_a_time(self):
        together = sigma_dissimilarities(FUTURE, PRESENT)
        alone = [sigma_dissimilarity(FUTURE, PRESENT[:, c, :]) for c in range(PRESENT.shape[1])]
        np.testing.assert_allclose(together, alone, rtol=1e-12)

    def test_far_places_keep_a_finite_ordered_sigma(self):
        # The reference reads ppf(cdf(d)), which is inf as soon as cdf(d) rounds to 1 (d above ~8):
        # all very far places tie. The upper tail keeps them apart.
        place = PRESENT[:, 6, :]
        shift = np.array([900, 300, 60, 20, 10])
        near = sigma_dissimilarity(FUTURE, place)
        far = sigma_dissimilarity(FUTURE, place + shift)
        farther = sigma_dissimilarity(FUTURE, place + 1.3 * shift)
        assert np.isfinite([far, farther]).all()
        assert near < far < farther
        assert chi(1).ppf(chi(5).cdf(4.0)) == pytest.approx(chi(1).isf(chi(5).sf(4.0)), rel=1e-9)

    def test_a_place_where_an_indicator_never_changes_is_simply_far(self):
        place = PRESENT[:, 3, :].copy()
        place[:, 3] = 0.0  # no hot day in any year: singular covariance
        sigma = sigma_dissimilarity(FUTURE, place)
        assert sigma > GOOD_TWIN_MAX_SIGMA and not np.isnan(sigma)

    def test_keeps_the_closest_cultivated_cells(self):
        years = np.arange(2011, 2011 + PRESENT.shape[0])
        cells = [
            GridCell(
                f"c{c}",
                45.0,
                -73.0,
                bool(TWINS["mask"][c]),
                IndicatorTable(years, PRESENT[:, c, :]),
            )
            for c in range(PRESENT.shape[1])
        ]
        finder = ClimateTwinFinder(cells, twins_per_target=TWINS["best"]["n"])
        best = finder.closest_cells(FUTURE)
        assert [int(t.cell.id[1:]) for t in best] == TWINS["best"]["cells"]

        target = IndicatorTable(years[: len(FUTURE)], FUTURE)
        union = finder.twins_of([ClimateTarget("A", target), ClimateTarget("B", target)])
        assert len(union) == TWINS["best"]["n"]
        assert union[0].sources == ["A", "B"]


class TestSoil:
    def test_distance_is_the_reference_one(self):
        for case in STEPS["soil"]:
            distance = soil_distance(soil_of(case["a"]), soil_of(case["b"]))
            assert distance == pytest.approx(case["distance"], rel=1e-12)

    def test_tolerances_widen_when_too_few_fields_are_left(self):
        base = soil_of(STEPS["soil"][1]["a"])

        @dataclass
        class Field:
            soil: Soil

        near = Field(base)
        medium = Field(Soil(base.clay_pct + 18, base.sand_pct, base.organic_carbon, base.ph))
        soil_filter = SoilFilter(base, min_fields=2)
        strict = soil_filter.keep_comparable([near, near, medium])
        assert strict.fields == [near, near] and not strict.widened
        widened = soil_filter.keep_comparable([near, medium])
        assert widened.widened and widened.fields == [near, medium]


class TestRotationsAndPrecrops:
    def test_a_sequence_is_reduced_to_its_rotation(self):
        for case in STEPS["canonical"]:
            assert rotation_of(case["sequence"]) == case["result"]

    def test_greenness_becomes_a_yield_gap(self):
        for case in STEPS["ndvi_gap"]:
            ndvi, p90, p50, p25 = case["args"]
            gap = yield_gap_from_ndvi(ndvi, NdviPercentiles(p90, p50, p25))
            assert gap == pytest.approx(case["result"], rel=1e-12)

    def test_precrop_values_are_the_reference_ones(self):
        rows = field_years_of(STEPS["precrop"]["rows"])
        for case in STEPS["precrop"]["results"]:
            value = precrop_value(rows, case["a"], case["b"])
            if case["value"] is None:
                assert value is None
            else:
                assert value == pytest.approx(case["value"], rel=1e-9)

    def test_twin_evidence_is_the_reference_one(self):
        reference = STEPS["twin_evidence"]
        rows = field_years_of(STEPS["precrop"]["rows"])
        fields = [
            TwinField(f["sequence"], f["superficie"], f["sigma"]) for f in reference["fields"]
        ]
        evidence = build_twin_evidence(fields, rows)
        assert sorted(evidence.crops) == reference["cultures"]
        for previous, next_crop, value in reference["precedents"]:
            assert evidence.is_observed(previous, next_crop)
            if value is None:
                assert evidence.precrop_value(previous, next_crop) is None
            else:
                assert evidence.precrop_value(previous, next_crop) == pytest.approx(value, rel=1e-9)
        assert evidence.sigma_mean == pytest.approx(reference["sigma_moyen"])
        assert [name for name, _ in evidence.top_rotations] == [
            name for name, _ in reference["top"]
        ]


class TestDiagnostic:
    def test_risks_are_the_reference_ones(self):
        for case in STEPS["diagnostics"]:
            m = case["measures"]
            diagnostic = ParcelDiagnostic(
                FieldMeasures(
                    slope_pct=m["pente_pct"],
                    heavy_rain_days=m["jours_pluie_intense"],
                    bare_soil_days=m["jours_sol_nu"],
                    summer_stress_index=m["esi_ete"],
                    root_zone_drought=m["smap_secheresse"],
                    groundwater_trend_cm_per_year=m["grace_tendance_cm_an"],
                ),
                irrigated=case["irrigation"],
            )
            assert diagnostic.erosion_risk == pytest.approx(
                case["result"]["risque_erosion"], rel=1e-12
            )
            assert diagnostic.water_risk(case["rain"]) == pytest.approx(
                case["result"]["risque_eau"], rel=1e-12
            )
