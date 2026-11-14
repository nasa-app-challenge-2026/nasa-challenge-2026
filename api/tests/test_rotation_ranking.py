"""The rotation ranking: weights, ranking, the routes, the data sources and their configuration."""

from __future__ import annotations

import json
from copy import deepcopy

import httpx
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
from field_shift.algorithm.soil_protection.site_conditions import SITE_VARIABLES, SiteConditions
from field_shift.api.app import create_app
from field_shift.api.settings import Settings
from field_shift.data_access.data_source_config import (
    DATA_SOURCES,
    DataSourceConfig,
    DataSourceConfigError,
)
from field_shift.data_access.site_data import RemoteSiteData, value_at
from field_shift.reference.measures import MEASURE_IDS
from field_shift.services.ranking_service import RankingService

REQUEST = {
    "location": {"lat": 45.5, "lon": -73.0},
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
        {"id": "A", "areaHa": 12, "site": {"slopePct": 2}},
        {"id": "B", "site": {"slopePct": 9, "sandPct": 20, "clayPct": 15}},
    ],
}


@pytest.fixture
def client() -> TestClient:
    """The application without any data source (no network)."""
    return TestClient(create_app(Settings(weather="demo")))


def rotation(rotation_id: str, *crops: str) -> Rotation:
    return Rotation.from_steps(rotation_id, [RotationStep(crop) for crop in crops])


def context(**site: float) -> SectionContext:
    return SectionContext("A", 45.5, -73.0, SiteConditions(**site), simulation_months=48)


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
        site = client.post("/rotations/rank", json=REQUEST).json()["sections"][1]["site"]
        origins = {value["key"]: (value["value"], value["origin"]) for value in site}
        assert origins["slope_pct"] == (9, "section")
        assert origins["sand_pct"] == (20, "section")
        assert origins["ksat_mm_h"] == (10, "valeur par défaut")
        assert "ndvi" not in origins  # unknown and optional: the theory is kept

    def test_the_notes_list_every_value_the_model_supplied_itself(self, client):
        section = client.post("/rotations/rank", json=REQUEST).json()["sections"][1]
        notes = "\n".join(section["notes"])
        defaults = [v["label"] for v in section["site"] if v["origin"] == "valeur par défaut"]
        given = [v["label"] for v in section["site"] if v["origin"] == "section"]
        assert defaults and all(f"{label} :" in notes for label in defaults)
        assert not any(
            note.startswith(f"{label} :") for label in given for note in section["notes"]
        )
        for estimated in ("Érosivité des pluies (R)", "Érodibilité du sol (K)", "Limon", "NDVI"):
            assert estimated in notes
        r_factor = section["rotations"][0]["soilProtection"]["erosion"]["factors"]["r"]
        assert f"{r_factor:.4g}".replace(".", ",") in notes  # the value the erosion really used

    def test_a_value_given_by_the_section_is_not_in_the_notes(self, client):
        request = deepcopy(REQUEST)
        request["sections"][1]["site"].update({"rFactor": 2500, "kFactor": 0.03, "ndvi": 0.7})
        notes = "\n".join(
            client.post("/rotations/rank", json=request).json()["sections"][1]["notes"]
        )
        assert "Érosivité des pluies (R)" not in notes
        assert "Érodibilité du sol (K)" not in notes
        assert "NDVI" not in notes

    def test_rotations_are_generated_from_the_crops_and_the_cycle(self, client):
        request = {
            "location": REQUEST["location"],
            "simulationYears": 4,
            "crops": ["mais", "soya", "luzerne"],
            "cycleYears": 2,
            "sections": [{"id": "A"}],
        }
        body = client.post("/rotations/rank", json=request).json()
        names = [r["name"] for r in body["sections"][0]["rotations"]]
        assert body["meta"]["rotationsGenerated"] and body["meta"]["rotationCount"] == 6
        assert names[0] == "Luzerne ×2" and names[-1] == "Soya → Soya"

    def test_a_ranking_of_measures_is_accepted_as_priorities(self, client):
        request = REQUEST | {"priorities": ["protection_sol", "eau"]}
        weights = client.post("/rotations/rank", json=request).json()["meta"]["weights"]
        assert weights["protection_sol"] > weights["eau"] > weights["rendement"] > 0

    def test_a_section_can_have_its_own_place(self, client):
        request = deepcopy(REQUEST)
        request["sections"][0]["location"] = {"lat": 46.0, "lon": -72.0}
        assert client.post("/rotations/rank", json=request).status_code == 200

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
            ({"sections": [{"id": "A"}, {"id": "A"}]}, "même id"),
            ({"sections": [{"id": "A", "site": {"slopePct": 250}}]}, "slopePct"),
            ({"sections": [{"id": "A", "site": {"sandPct": 70, "clayPct": 50}}]}, "100 %"),
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


def source_server(answers: dict[str, object]) -> tuple[httpx.Client, list[httpx.Request]]:
    """A fake data server: answers the JSON of `answers` by host name, 500 for the others."""
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.host in answers:
            return httpx.Response(200, json=answers[request.url.host])
        return httpx.Response(500)

    return httpx.Client(transport=httpx.MockTransport(handle)), requests


ENVIRONMENT = {
    "FIELD_SHIFT_URL_SLOPE_PCT": "https://srtm.test/slope?lat={lat}&lon={lon}",
    "FIELD_SHIFT_JSON_PATH_SLOPE_PCT": "data.0.slope",
    "FIELD_SHIFT_URL_SOIL_SATURATION": "https://smap.test/{lat}/{lon}",
    "FIELD_SHIFT_SCALE_SOIL_SATURATION": "0.01",
    "FIELD_SHIFT_URL_NDVI": "https://ndvi.test/point",
    "FIELD_SHIFT_URL_ANNUAL_RAIN_MM": "",  # switched off
}


class TestDataSources:
    def test_every_point_source_fills_a_site_variable(self):
        keys = {source.key for source in DATA_SOURCES} - {"power_daily"}
        assert keys <= set(SITE_VARIABLES)

    def test_by_default_only_nasa_power_is_configured(self):
        config = DataSourceConfig.load({})
        assert [s.key for s in config.point_sources] == ["annual_rain_mm"]
        assert config.power_daily_url == "https://power.larc.nasa.gov/api/temporal/daily/point"

    def test_addresses_come_from_the_environment(self):
        config = DataSourceConfig.load(ENVIRONMENT)
        assert [s.key for s in config.point_sources] == ["slope_pct", "ndvi", "soil_saturation"]
        assert config.sources["slope_pct"].json_path == "data.0.slope"
        assert config.sources["soil_saturation"].scale == 0.01

    def test_addresses_come_from_a_file_and_the_environment_wins(self, tmp_path):
        file = tmp_path / "sources.json"
        file.write_text(
            json.dumps(
                {
                    "slope_pct": "https://file.test/slope",
                    "ksat_mm_h": {
                        "url": "https://file.test/ksat",
                        "jsonPath": "ksat",
                        "scale": 3.6,
                        "headers": {"Authorization": "Bearer secret"},
                    },
                    "power_daily": {"url": "https://power.test/daily"},
                }
            ),
            encoding="utf-8",
        )
        environment = {
            "FIELD_SHIFT_DATA_SOURCES": str(file),
            "FIELD_SHIFT_URL_SLOPE_PCT": "https://env.test/slope",
        }
        config = DataSourceConfig.load(environment)
        assert config.sources["slope_pct"].url == "https://env.test/slope"
        ksat = config.sources["ksat_mm_h"]
        assert (ksat.url, ksat.json_path, ksat.scale) == ("https://file.test/ksat", "ksat", 3.6)
        assert ksat.headers == {"Authorization": "Bearer secret"}
        assert config.power_daily_url == "https://power.test/daily"

    @pytest.mark.parametrize(
        "content, message",
        [
            ('{"pente": "https://x.test"}', "inconnue"),
            ("pas du json", "n’a pas pu être lu"),
            ('{"slope_pct": {"scale": "beaucoup"}}', "scale"),
            ("[]", "objet JSON"),
        ],
    )
    def test_a_wrong_file_is_refused_when_the_server_starts(self, tmp_path, content, message):
        file = tmp_path / "sources.json"
        file.write_text(content, encoding="utf-8")
        with pytest.raises(DataSourceConfigError, match=message):
            DataSourceConfig.load({"FIELD_SHIFT_DATA_SOURCES": str(file)})

    def test_a_missing_file_is_refused(self, tmp_path):
        with pytest.raises(DataSourceConfigError, match="introuvable"):
            DataSourceConfig.load({"FIELD_SHIFT_DATA_SOURCES": str(tmp_path / "absent.json")})

    def test_the_path_to_a_value(self):
        document = {"results": [{"value": 4.2}], "properties": {"parameter": {"ANN": 3}}}
        assert value_at(document, "results.0.value") == 4.2
        assert value_at(document, "properties.parameter.ANN") == 3

    def test_values_are_read_at_the_point_scaled_and_remembered(self):
        http, requests = source_server(
            {"srtm.test": {"data": [{"slope": 7.5}]}, "smap.test": {"value": 40}}
        )
        provider = RemoteSiteData(DataSourceConfig.load(ENVIRONMENT), http)
        readings = {r.key: (r.value, r.origin) for r in provider.site_readings(45.5, -73.25)}
        assert readings == {
            "slope_pct": (7.5, "SRTM (NASA Earthdata)"),
            "soil_saturation": (0.4, "SMAP"),
        }  # the NDVI server failed: skipped
        assert str(requests[0].url) == "https://srtm.test/slope?lat=45.50000&lon=-73.25000"
        assert str(requests[2].url) == "https://smap.test/45.50000/-73.25000"
        # A place with a failed source is read again; a complete one is remembered.
        provider.site_readings(45.5, -73.25)
        assert len(requests) == 6

    def test_a_complete_place_is_read_once(self):
        http, requests = source_server({"srtm.test": {"value": 3}})
        # NASA POWER (configured by default) is not in the fake server: switch it off.
        config = DataSourceConfig.load(
            {
                "FIELD_SHIFT_URL_SLOPE_PCT": "https://srtm.test/",
                "FIELD_SHIFT_URL_ANNUAL_RAIN_MM": "",
            }
        )
        provider = RemoteSiteData(config, http)
        provider.site_readings(45.5, -73.0)
        provider.site_readings(45.5004, -73.0004)  # the same place, about 50 m away
        assert len(requests) == 1

    @pytest.mark.parametrize("answer", [{"value": -999}, {"value": "n/a"}, {"other": 1}, [1]])
    def test_a_fill_value_or_an_unexpected_answer_is_ignored(self, answer):
        http, _ = source_server({"srtm.test": answer})
        config = DataSourceConfig.load(
            {
                "FIELD_SHIFT_URL_SLOPE_PCT": "https://srtm.test/",
                "FIELD_SHIFT_URL_ANNUAL_RAIN_MM": "",
            }
        )
        assert RemoteSiteData(config, http).site_readings(45.5, -73.0) == []

    def test_the_section_wins_over_the_sources_which_win_over_the_defaults(self):
        http, _ = source_server(
            {"srtm.test": {"data": [{"slope": 7.5}]}, "smap.test": {"value": 40}}
        )
        settings = Settings(weather="nasa", data_sources=DataSourceConfig.load(ENVIRONMENT))
        service = RankingService(RemoteSiteData(settings.data_sources, http))
        client = TestClient(create_app(Settings(weather="demo"), ranking_service=service))
        request = deepcopy(REQUEST)
        request["sections"] = [{"id": "A"}, {"id": "B", "site": {"slopePct": 1}}]
        sections = client.post("/rotations/rank", json=request).json()["sections"]
        site_a, site_b = (
            {value["key"]: (value["value"], value["origin"]) for value in section["site"]}
            for section in sections
        )
        assert site_a["slope_pct"] == (7.5, "SRTM (NASA Earthdata)")
        assert site_a["soil_saturation"] == (0.4, "SMAP")
        assert site_a["ksat_mm_h"] == (10, "valeur par défaut")
        assert site_b["slope_pct"] == (1, "section")

    def test_the_route_shows_the_configuration_without_its_secrets(self):
        environment = ENVIRONMENT | {"FIELD_SHIFT_URL_NDVI": "https://ndvi.test/point?key=SECRET"}
        settings = Settings(weather="nasa", data_sources=DataSourceConfig.load(environment))
        client = TestClient(create_app(settings))
        sources = {source["key"]: source for source in client.get("/data-sources").json()}
        assert set(sources) == {source.key for source in DATA_SOURCES}
        assert sources["ndvi"]["configured"] and sources["ndvi"]["url"] == "https://ndvi.test/point"
        assert sources["ksat_mm_h"] == {
            "key": "ksat_mm_h",
            "dataset": "USDA SSURGO",
            "provides": "Conductivité hydraulique à saturation, en mm/h",
            "configured": False,
            "url": None,
            "jsonPath": "value",
            "scale": 1,
        }
        assert "SECRET" not in client.get("/data-sources").text

    def test_in_demo_mode_no_source_is_read(self, client):
        assert not any(source["configured"] for source in client.get("/data-sources").json())

    def test_the_weather_address_of_the_plan_comes_from_the_configuration(self):
        config = DataSourceConfig.load({"FIELD_SHIFT_URL_POWER_DAILY": "https://power.test/daily"})
        settings = Settings.from_environment(
            {"FIELD_SHIFT_URL_POWER_DAILY": "https://power.test/daily"}
        )
        assert settings.data_sources == config
        assert settings.data_sources.power_daily_url == "https://power.test/daily"
