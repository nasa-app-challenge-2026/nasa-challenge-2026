"""The HTTP API: planning a farm, refusing bad input, CORS, and where the weather comes from."""

from __future__ import annotations

from copy import deepcopy
from datetime import date

import httpx
from fastapi.testclient import TestClient

from field_shift.algorithm.sources.demo_farm_weather import demo_farm_weather
from field_shift.api.app import create_app
from field_shift.api.settings import DEFAULT_CORS_ORIGINS, Settings
from field_shift.data_access.nasa_power import FILL_VALUE
from field_shift.data_access.weather_providers import NasaPowerWeatherProvider
from field_shift.services.plan_service import PlanService
from tests.helpers.nasa_power_stub import StubbedPower, power_body
from tests.test_contract import errors

FRONT = "http://localhost:5173"


def test_health(plan_client):
    body = plan_client.get("/health").json()
    assert body["status"] == "ok" and body["algorithm"] == "field_shift v5.1"
    assert "weather" not in body  # there is no demo mode any more


def test_every_example_gets_a_plan_that_respects_the_schema(plan_client, schema, example_inputs):
    for name, farm in example_inputs.items():
        response = plan_client.post("/plan", json=farm)
        assert response.status_code == 200, (name, response.text[:300])
        plan = response.json()
        assert errors(schema, "FarmPlan", plan) == [], name
        assert [s["id"] for s in plan["sections"]] == [s["id"] for s in farm["sections"]]
        cycles = farm["farm"]["time"]["horizonYears"] // farm["farm"]["time"]["cycleYears"]
        assert all(len(s["cycles"]) == cycles for s in plan["sections"]), name
        assert plan["meta"]["demo"] is True


def test_the_front_end_can_send_its_whole_farm(plan_client, example_inputs):
    """The screens send the outline, names, notes… The algorithm only reads what it needs."""
    farm = deepcopy(example_inputs["ferme-demo"])
    farm["farm"]["name"] = "Ma ferme"
    farm["farm"]["boundary"] = [[45.0, -73.0], [45.1, -73.0], [45.1, -72.9]]
    farm["sections"][0]["note"] = "côté route"
    farm["sections"][0]["offset"] = 3  # a field of contract 1.0 that nobody reads any more
    assert plan_client.post("/plan", json=farm).status_code == 200


def test_the_plan_starts_after_the_crop_in_place(plan_client, example_inputs):
    plan = plan_client.post("/plan", json=example_inputs["ferme-demo"]).json()
    first = {s["id"]: s["cycles"][0]["years"] for s in plan["sections"]}
    assert first == {"A": [2027, 2030], "B": [2028, 2031], "C": [2027, 2030], "D": [2027, 2030]}
    assert plan["sections"][0]["cycles"][0]["referenceAlerts"][0]["message"].startswith(
        "Soya après Soya"
    )


def test_today_comes_from_the_request_or_from_the_server_clock(example_inputs):
    farm = deepcopy(example_inputs["ferme-demo"])
    del farm["today"]
    service = PlanService(
        NasaPowerWeatherProvider(StubbedPower().client), clock=lambda: date(2026, 11, 13)
    )
    client = TestClient(create_app(Settings(), service))
    assert client.post("/plan", json=farm).json()["settings"]["currentYear"] == 2026


class TestRefusedInput:
    def refuse(self, client, farm, *where: str) -> str:
        response = client.post("/plan", json=farm)
        assert response.status_code == 422
        text = response.text
        for part in where:
            assert part in text, (part, text[:400])
        return text

    def test_an_unknown_crop(self, plan_client, example_inputs):
        farm = deepcopy(example_inputs["ferme-demo"])
        farm["sections"][1]["currentRotation"] = ["luzerne-3", "riz"]
        self.refuse(plan_client, farm, "currentRotation", "riz")

    def test_a_frequency_that_does_not_exist(self, plan_client, example_inputs):
        farm = deepcopy(example_inputs["ferme-demo"])
        farm["farm"]["time"]["frequencyMonths"] = 5
        self.refuse(plan_client, farm, "Fréquence : 12, 6, 4 mois")

    def test_a_cycle_that_is_too_long(self, plan_client, example_inputs):
        farm = deepcopy(example_inputs["ferme-demo"])
        farm["farm"]["time"].update(cycleYears=7, horizonYears=14)
        self.refuse(plan_client, farm, "de 2 à 6 ans")

    def test_a_horizon_that_is_not_a_multiple_of_the_cycle(self, plan_client, example_inputs):
        farm = deepcopy(example_inputs["ferme-demo"])
        farm["farm"]["time"]["horizonYears"] = 10
        self.refuse(plan_client, farm, "multiple du cycle")

    def test_a_harvest_month_in_the_wrong_format(self, plan_client, example_inputs):
        farm = deepcopy(example_inputs["ferme-demo"])
        farm["sections"][0]["currentHarvest"] = "octobre 2026"
        self.refuse(plan_client, farm, "AAAA-MM")

    def test_a_criterion_ranked_twice(self, plan_client, example_inputs):
        farm = deepcopy(example_inputs["ferme-demo"])
        farm["farm"]["priorities"] = ["eau", "eau"]
        self.refuse(plan_client, farm, "qu’une fois")

    def test_two_sections_with_the_same_id(self, plan_client, example_inputs):
        farm = deepcopy(example_inputs["ferme-demo"])
        farm["sections"][1]["id"] = "A"
        self.refuse(plan_client, farm, "même id")

    def test_no_section(self, plan_client, example_inputs):
        farm = deepcopy(example_inputs["ferme-demo"])
        farm["sections"] = []
        self.refuse(plan_client, farm, "sections")

    def test_an_old_contract_version(self, plan_client, example_inputs):
        farm = deepcopy(example_inputs["ferme-demo"])
        farm["version"] = "1.0"
        self.refuse(plan_client, farm, "version")


class TestCors:
    def test_the_front_end_is_allowed(self, plan_client, example_inputs):
        response = plan_client.post(
            "/plan", json=example_inputs["ferme-demo"], headers={"Origin": FRONT}
        )
        assert response.headers["access-control-allow-origin"] == FRONT

    def test_the_browser_preflight_is_answered(self, plan_client):
        response = plan_client.options(
            "/plan",
            headers={
                "Origin": FRONT,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert response.status_code == 200
        assert "content-type" in response.headers["access-control-allow-headers"].lower()

    def test_another_site_is_not(self, plan_client):
        response = plan_client.get("/health", headers={"Origin": "https://example.org"})
        assert "access-control-allow-origin" not in response.headers

    def test_the_allowed_sites_come_from_the_environment(self):
        settings = Settings.from_environment(
            {"FIELD_SHIFT_CORS_ORIGINS": "https://equipe.github.io, https://autre.org"}
        )
        assert settings.cors_origins == ("https://equipe.github.io", "https://autre.org")
        assert Settings.from_environment({}).cors_origins == DEFAULT_CORS_ORIGINS

    def test_the_old_demo_mode_does_not_exist_any_more(self):
        assert not hasattr(Settings.from_environment({"FIELD_SHIFT_WEATHER": "demo"}), "weather")


class TestWeatherSource:
    def client_for(self, power: StubbedPower) -> TestClient:
        service = PlanService(NasaPowerWeatherProvider(power.client))
        return TestClient(create_app(Settings(), service))

    def test_nasa_power_is_read_once_per_place_and_the_plan_says_so(self, example_inputs):
        power = StubbedPower()
        client = self.client_for(power)
        farm = example_inputs["ferme-demo"]
        first = client.post("/plan", json=farm).json()
        client.post("/plan", json=farm)
        assert len(power.requests) == 1
        params = power.requests[0].url.params
        assert (
            params["latitude"] == "45.6287"
            and params["start"] == "19850101"
            and params["end"] == "20241231"
        )
        assert first["meta"]["sources"]["farmWeather"]["real"] is True
        assert first["meta"]["demo"] is True  # the models and the twins are still fictitious

    def test_a_failure_is_a_502_and_nasa_power_is_tried_again(self, example_inputs):
        power = StubbedPower(lambda request: httpx.Response(503))
        client = self.client_for(power)
        farm = example_inputs["ferme-demo"]
        response = client.post("/plan", json=farm)
        assert response.status_code == 502
        (failure,) = response.json()["detail"]
        assert failure["source"] == "NASA POWER (MERRA-2)" and "503" in failure["msg"]
        client.post("/plan", json=farm)
        assert len(power.requests) == 2  # a failure is not kept

    def test_an_unexpected_answer_is_a_failure_too(self, example_inputs):
        power = StubbedPower(lambda request: httpx.Response(200, json={"properties": {}}))
        response = self.client_for(power).post("/plan", json=example_inputs["ferme-demo"])
        assert response.status_code == 502

    def test_missing_days_take_the_value_of_the_day_before(self, example_inputs):
        weather_body = power_body(demo_farm_weather(), missing_days=5)
        assert str(FILL_VALUE) in weather_body
        power = StubbedPower(lambda request: httpx.Response(200, content=weather_body))
        plan = self.client_for(power).post("/plan", json=example_inputs["ferme-demo"]).json()
        assert plan["meta"]["sources"]["farmWeather"]["real"] is True

    def test_two_places_are_two_requests(self, example_inputs):
        power = StubbedPower()
        client = self.client_for(power)
        farm = deepcopy(example_inputs["ferme-demo"])
        client.post("/plan", json=farm)
        farm["farm"]["location"] = {"lat": 46.8, "lon": -71.2}
        client.post("/plan", json=farm)
        assert len(power.requests) == 2
