"""The rotation ranking: weights, ranking, the routes, the data sources and their configuration."""

from __future__ import annotations

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from field_shift.algorithm.ranking.measure_weights import measure_weights
from field_shift.algorithm.ranking.measures import (
    MeasureResult,
    SectionContext,
    SoilProtectionMeasure,
    all_measures,
)
from field_shift.algorithm.ranking.rotation_ranker import rank_rotations
from field_shift.algorithm.rotation.rotation import Rotation, RotationStep
from field_shift.api.app import create_app
from field_shift.api.settings import Settings
from field_shift.reference.measures import MEASURE_IDS
from field_shift.services.ranking_service import RankingService
from field_shift.tools.make_examples import example_plan_service
from tests.helpers.site_stub import TEST_ORIGIN, FixedSiteData, site, square

REQUEST = {
    "simulationYears": 6,
    "priorities": {"protection_sol": 2, "rendement": 1},
    "rotations": [
        {"id": "mais-soya", "phases": ["mais", "soya"]},
        {"id": "prairie", "name": "Prairie permanente", "phases": ["foin"]},
        {
            "id": "couvert",
            "phases": ["mais", {"crop": "seigle", "months": 6}, "soya"],
        },
    ],
    "sections": [
        {
            "id": "A",
            "geometry": square(45.5, -73.0, 300),
            "site": {"slopePct": 2, "supportPracticeFactor": 1},
        },
        {
            "id": "B",
            "geometry": square(45.51, -73.0, 200),
            "site": {"slopePct": 9, "sandPct": 20, "clayPct": 15, "supportPracticeFactor": 1},
        },
    ],
}


def client_on(site_data: FixedSiteData) -> TestClient:
    return TestClient(create_app(Settings(), example_plan_service(), RankingService(site_data)))


@pytest.fixture
def site_data() -> FixedSiteData:
    return FixedSiteData()


@pytest.fixture
def client(site_data) -> TestClient:
    """The application on the test site data (no network)."""
    return client_on(site_data)


P = {"supportPracticeFactor": 1}
SECTION = {"id": "A", "geometry": square(), "site": P}
OPEN_RING = {
    "type": "Polygon",
    "coordinates": [[[-73, 45.5], [-72.99, 45.5], [-72.99, 45.51], [-73, 45.51]]],
}
BOW_TIE = {
    "type": "Polygon",
    "coordinates": [[[-73, 45.5], [-72.99, 45.51], [-72.99, 45.5], [-73, 45.51], [-73, 45.5]]],
}


def rotation(rotation_id: str, *crops: str) -> Rotation:
    return Rotation.from_steps(rotation_id, [RotationStep(crop) for crop in crops])


def context(**changes: float) -> SectionContext:
    return SectionContext("A", 45.5, -73.0, site(**changes), simulation_months=48)


class TestWeights:
    def test_without_priorities_the_measures_weigh_the_same(self):
        assert measure_weights(None) == dict.fromkeys(MEASURE_IDS, 0.25)

    def test_weights_keep_their_proportions(self):
        weights = measure_weights({"protection_sol": 3, "rendement": 1})
        assert weights["protection_sol"] == 0.75 and weights["rendement"] == 0.25
        assert weights["eau"] == weights["ravageurs"] == 0

    def test_a_ranking_gives_decreasing_weights_that_add_up_to_one(self):
        weights = measure_weights(["protection_sol", "rendement", "eau"])
        assert weights["protection_sol"] > weights["rendement"] > weights["eau"]
        assert 0 < weights["ravageurs"] < weights["eau"]  # unranked: a small share
        assert sum(weights.values()) == pytest.approx(1)

    @pytest.mark.parametrize(
        "priorities, message",
        [
            ({"bonheur": 1}, "mesure inconnue"),
            ({"eau": -1, "rendement": 2}, "négatif"),
            ({"eau": 0}, "supérieur à zéro"),
        ],
    )
    def test_wrong_priorities_are_refused(self, priorities, message):
        with pytest.raises(ValueError, match=message):
            measure_weights(priorities)


class TestRanking:
    def test_the_best_rotation_comes_first(self):
        rotations = [rotation("R1", "mais", "soya"), rotation("R2", "foin"), rotation("R3", "soya")]
        ranked = rank_rotations(rotations, context(), measure_weights(None))
        assert [r.rotation.id for r in ranked] == ["R2", "R1", "R3"]
        assert [r.rank for r in ranked] == [1, 2, 3]
        assert ranked[0].score > ranked[1].score > ranked[2].score

    def test_measures_not_written_are_left_out_and_the_weights_rescaled(self):
        ranked = rank_rotations([rotation("R1", "mais")], context(), measure_weights(None))[0]
        assert ranked.weights == {"rendement": 0, "eau": 0, "protection_sol": 1, "ravageurs": 0}
        assert not ranked.results["rendement"].available
        assert ranked.score == pytest.approx(100 * ranked.results["protection_sol"].score)

    def test_the_score_is_the_weighted_sum_of_the_measures(self):
        class Fixed:
            implemented = True

            def __init__(self, measure_id: str, score: float) -> None:
                self.id, self._score = measure_id, score

            def evaluate(self, rotation, context) -> MeasureResult:
                return MeasureResult(self.id, score=self._score)

        measures = [Fixed("rendement", 1.0), Fixed("protection_sol", 0.5)]
        weights = measure_weights({"rendement": 1, "protection_sol": 3})
        ranked = rank_rotations([rotation("R1", "mais")], context(), weights, measures)[0]
        assert ranked.score == pytest.approx(100 * (0.25 * 1.0 + 0.75 * 0.5))

    def test_nothing_to_rank_on_keeps_the_order_of_the_request(self):
        rotations = [rotation("R1", "soya"), rotation("R2", "foin")]
        ranked = rank_rotations(rotations, context(), measure_weights({"rendement": 1}))
        assert [r.rotation.id for r in ranked] == ["R1", "R2"]
        assert all(r.score is None for r in ranked)

    def test_one_measure_is_written_and_three_are_waiting(self):
        assert [m.id for m in all_measures()] == list(MEASURE_IDS)
        assert [m.id for m in all_measures() if m.implemented] == [SoilProtectionMeasure.id]


class TestRankRoute:
    def test_every_section_gets_its_rotations_ranked_with_their_measures(self, client):
        response = client.post("/rotations/rank", json=REQUEST)
        assert response.status_code == 200, response.text
        body = response.json()
        assert [s["id"] for s in body["sections"]] == ["A", "B"]
        for section in body["sections"]:
            rotations = section["rotations"]
            assert [r["rank"] for r in rotations] == [1, 2, 3]
            assert [r["rotationId"] for r in rotations] == ["prairie", "couvert", "mais-soya"]
            scores = [r["score"] for r in rotations]
            assert scores == sorted(scores, reverse=True) and all(0 <= s <= 100 for s in scores)
            for ranked in rotations:
                assert list(ranked["measures"]) == list(MEASURE_IDS)
                soil = ranked["measures"]["protection_sol"]
                assert (
                    soil["available"] and soil["weight"] == 1 and soil["score"] == ranked["score"]
                )
                assert ranked["measures"]["rendement"] == {
                    "id": "rendement",
                    "name": "Rendement",
                    "available": False,
                    "score": None,
                    "value": None,
                    "unit": "kg/ha",
                    "weight": 0,
                    "note": "La mesure « Rendement » (rendement) n’est pas encore calculée.",
                }
        meta = body["meta"]
        assert meta["implementedMeasures"] == ["protection_sol"]
        assert meta["pendingMeasures"] == ["rendement", "eau", "ravageurs"]
        assert meta["weights"]["protection_sol"] == pytest.approx(2 / 3, abs=1e-4)
        assert meta["rotationCount"] == 3 and meta["rotationsGenerated"] is False

    def test_the_detail_of_the_soil_protection(self, client):
        body = client.post("/rotations/rank", json=REQUEST).json()
        best = body["sections"][0]["rotations"][0]
        assert best["name"] == "Prairie permanente"
        detail = best["soilProtection"]
        assert detail["rpi"] == 5 and detail["protectionClass"] == "excellente"
        assert detail["infiltration"]["rotationGainPct"] == 59.2
        erosion = detail["erosion"]
        assert 0 < erosion["soilLossTHaYear"] < erosion["bareSoilLossTHaYear"]
        assert erosion["cumulativeSoilLossTHa"] == pytest.approx(
            6 * erosion["soilLossTHaYear"], abs=0.05
        )
        assert [c["crop"] for c in detail["crops"]] == ["foin"]
        assert detail["crops"][0]["sharePct"] == 100

    def test_a_steeper_section_loses_more_soil_with_the_same_rotation(self, client):
        flat, steep = client.post("/rotations/rank", json=REQUEST).json()["sections"]
        loss = [
            s["rotations"][-1]["soilProtection"]["erosion"]["soilLossTHaYear"]
            for s in (flat, steep)
        ]
        assert loss[1] > loss[0]

    def test_the_answer_says_where_each_site_value_comes_from(self, client):
        site_b = client.post("/rotations/rank", json=REQUEST).json()["sections"][1]["site"]
        origins = {value["key"]: (value["value"], value["origin"]) for value in site_b}
        assert origins["slope_pct"] == (9, "section")
        assert origins["sand_pct"] == (20, "section")
        assert origins["ndvi"] == (0.85, TEST_ORIGIN)
        assert origins["ksat_mm_h"][1] == "calcul : Saxton et Rawls (2006)"
        assert origins["k_factor"][1] == "calcul : EPIC, Williams (1995)"
        assert origins["r_factor"][1] == "calcul : Renard et Freimund (1994)"
        assert "valeur par défaut" not in str(site_b)

    def test_only_what_the_section_does_not_give_is_read(self, client, site_data):
        client.post("/rotations/rank", json=REQUEST)
        (_, needed_a), (_, needed_b) = site_data.calls
        assert "slope_pct" not in needed_a and "sand_pct" in needed_a
        assert not {"slope_pct", "sand_pct", "clay_pct", "support_practice_factor"} & needed_b
        assert not {"ksat_mm_h", "k_factor", "r_factor"} & needed_a  # computed, not read

    def test_the_section_gets_its_area_and_centre_from_its_outline(self, client):
        section = client.post("/rotations/rank", json=REQUEST).json()["sections"][0]
        assert section["areaHa"] == pytest.approx(9, rel=1e-3)  # 300 m × 300 m
        assert section["centroid"] == pytest.approx({"lat": 45.5, "lon": -73.0}, abs=1e-6)

    def test_the_notes_list_every_computed_value_with_its_method(self, client):
        section = client.post("/rotations/rank", json=REQUEST).json()["sections"][1]
        notes = "\n".join(section["notes"])
        for computed in ("Saxton et Rawls", "EPIC", "Renard et Freimund", "Limon : 65 %"):
            assert computed in notes
        r_factor = section["rotations"][0]["soilProtection"]["erosion"]["factors"]["r"]
        assert f"{r_factor:.4g}".replace(".", ",") in notes  # the value the erosion really used
        assert "Pente" not in notes and "NDVI" not in notes  # given or read as is

    def test_a_value_given_by_the_section_is_not_computed(self, client):
        request = deepcopy(REQUEST)
        request["sections"][1]["site"].update({"rFactor": 2500, "kFactor": 0.03, "ksatMmH": 20})
        section = client.post("/rotations/rank", json=request).json()["sections"][1]
        origins = {value["key"]: value["origin"] for value in section["site"]}
        assert {origins[k] for k in ("r_factor", "k_factor", "ksat_mm_h")} == {"section"}
        assert "Saxton" not in "\n".join(section["notes"])

    def test_a_failed_data_service_fails_the_request_and_names_it(self):
        client = client_on(FixedSiteData(failing=["SoilGrids 2.0 (ISRIC)", "MODIS (ORNL DAAC)"]))
        response = client.post("/rotations/rank", json=REQUEST)
        assert response.status_code == 502
        assert response.json()["detail"][:2] == [
            {"section": "A", "source": "SoilGrids 2.0 (ISRIC)", "msg": "le service a répondu 503"},
            {"section": "A", "source": "MODIS (ORNL DAAC)", "msg": "le service a répondu 503"},
        ]

    def test_a_texture_over_100_pct_with_the_read_part_is_refused(self):
        values = dict(FixedSiteData().values, clay_pct=60)
        request = deepcopy(REQUEST)
        request["sections"][0]["site"]["sandPct"] = 50
        response = client_on(FixedSiteData(values)).post("/rotations/rank", json=request)
        assert response.status_code == 422 and "100 %" in response.text

    def test_rotations_are_generated_from_the_crops_and_the_cycle(self, client):
        request = {
            "simulationYears": 4,
            "crops": ["mais", "soya", "luzerne"],
            "cycleYears": 2,
            "sections": [REQUEST["sections"][0]],
        }
        body = client.post("/rotations/rank", json=request).json()
        names = [r["name"] for r in body["sections"][0]["rotations"]]
        assert body["meta"]["rotationsGenerated"] and body["meta"]["rotationCount"] == 6
        assert names[0] == "Luzerne ×2" and names[-1] == "Soya → Soya"

    def test_a_ranking_of_measures_is_accepted_as_priorities(self, client):
        request = REQUEST | {"priorities": ["protection_sol", "eau"]}
        weights = client.post("/rotations/rank", json=request).json()["meta"]["weights"]
        assert weights["protection_sol"] > weights["eau"] > weights["rendement"] > 0

    @pytest.mark.parametrize(
        "change, where",
        [
            ({"rotations": [{"phases": ["riz"]}]}, "culture inconnue : riz"),
            ({"rotations": [], "crops": []}, "crops et cycleYears"),
            ({"rotations": [{"phases": [{"crop": None}]}]}, "sol nu"),
            ({"rotations": [{"phases": [{"crop": None, "months": 6}]}]}, "au moins une culture"),
            ({"simulationYears": 0}, "simulationYears"),
            ({"priorities": {"bonheur": 1}}, "mesure inconnue"),
            ({"priorities": {"eau": 0}}, "supérieur à zéro"),
            ({"sections": []}, "sections"),
            ({"sections": [SECTION, SECTION]}, "même id"),
            ({"sections": [SECTION | {"site": P | {"slopePct": 250}}]}, "slopePct"),
            ({"sections": [SECTION | {"site": P | {"sandPct": 70, "clayPct": 50}}]}, "100 %"),
            ({"sections": [SECTION | {"site": {}}]}, "supportPracticeFactor"),
            ({"sections": [{"id": "A", "site": P}]}, "geometry"),
            ({"sections": [SECTION | {"geometry": OPEN_RING}]}, "fermé"),
            ({"sections": [SECTION | {"geometry": BOW_TIE}]}, "se croise"),
            (
                {"sections": [SECTION | {"geometry": {"type": "Point", "coordinates": [0, 0]}}]},
                "Polygon",
            ),
            (
                {
                    "rotations": [],
                    "crops": ["mais", "soya", "orge", "foin", "pois"],
                    "cycleYears": 6,
                },
                "plus de 200 rotations",
            ),
        ],
    )
    def test_a_wrong_request_is_refused_with_the_reason(self, client, change, where):
        response = client.post("/rotations/rank", json=REQUEST | change)
        assert response.status_code == 422
        assert where in response.text, response.text[:400]


class TestMeasureRoutes:
    def test_the_soil_protection_alone(self, client):
        body = client.post("/measures/protection-sol", json=REQUEST).json()
        assert body["meta"]["weights"] == {
            "rendement": 0,
            "eau": 0,
            "protection_sol": 1,
            "ravageurs": 0,
        }
        assert body["sections"][0]["rotations"][0]["rotationId"] == "prairie"

    @pytest.mark.parametrize("path", ["rendement", "eau", "ravageurs"])
    def test_the_other_measures_have_their_route_and_say_they_are_not_written(self, client, path):
        response = client.post(f"/measures/{path}", json=REQUEST)
        assert response.status_code == 501
        assert "pas encore calculée" in response.json()["detail"]

    def test_a_measure_route_still_checks_its_input(self, client):
        assert client.post("/measures/rendement", json={}).status_code == 422

    def test_the_list_of_measures(self, client):
        measures = client.get("/measures").json()
        assert [m["id"] for m in measures] == list(MEASURE_IDS)
        assert [m["implemented"] for m in measures] == [False, False, True, False]

    def test_the_crops_a_rotation_can_contain(self, client):
        crops = {crop["id"]: crop for crop in client.get("/crops").json()}
        assert crops["luzerne"]["kind"] == "perenne" and crops["luzerne"]["infiltrationScore"] == 5


class TestDataSourcesRoute:
    def test_the_services_with_their_dataset_and_reference(self, client):
        sources = {source["key"]: source for source in client.get("/data-sources").json()}
        assert set(sources) == {
            "power_daily",
            "power_climatology",
            "power_hourly",
            "soilgrids",
            "elevation",
            "modis",
        }
        assert sources["soilgrids"]["reference"].startswith("Poggio et al.")
        assert sources["elevation"]["url"] == "https://api.open-meteo.com/v1/elevation"
