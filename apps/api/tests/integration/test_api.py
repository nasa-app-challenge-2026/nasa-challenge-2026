"""End-to-end through HTTP, on the versioned NASA snapshot (no network)."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from fieldshift.api.app import create_app
from fieldshift.infrastructure.nasa_power.provider import ClimateSourceMode
from fieldshift.infrastructure.settings import Settings


@pytest.fixture(scope="module")
def client() -> TestClient:
    settings = Settings(climate_source=ClimateSourceMode.SNAPSHOT_ONLY, log_level="WARNING")
    return TestClient(create_app(settings, today=lambda: date(2026, 11, 10)))


@pytest.fixture(scope="module")
def demo(client: TestClient) -> dict[str, Any]:
    demo: dict[str, Any] = client.get("/api/v1/demo-farms").json()[0]
    return demo


def test_reference_endpoints(client: TestClient) -> None:
    assert client.get("/api/v1/health").json()["status"] == "ok"
    crops = {c["id"]: c for c in client.get("/api/v1/crops").json()}
    assert crops["oat"]["heat_requirement"]["basis"]["source_ids"] == ["msu_mt200103"]
    assert crops["hay_mixed"]["fixes_nitrogen"] is None
    assert len(client.get("/api/v1/sources").json()) >= 10


def test_climate_analysis_is_reproducible_on_the_snapshot(
    client: TestClient, demo: dict[str, Any]
) -> None:
    body = {
        "location": demo["profile"]["location"],
        "observations": demo["profile"]["observations"],
    }
    result = client.post("/api/v1/climate/analyze", json=body).json()
    assert result["period"] == {"first_year": 1981, "last_year": 2025, "years_analysed": 45}
    assert result["provenance"]["origin"] == "verified_snapshot"
    values = {i["id"]: {v["year"]: v["value"] for v in i["values"]} for i in result["indicators"]}
    assert round(values["crop_heat_units"][2024]) == 2886
    assert values["growing_season_length_days"][2024] == 190
    assert values["frost_free_season_days"][2024] == 168
    codes = {w["code"] for w in result["quality"]["warnings"]}
    assert {"coarse_grid_cell", "approximate_location"} <= codes


def test_rotation_comparison_returns_three_explained_strategies(
    client: TestClient, demo: dict[str, Any]
) -> None:
    result = client.post("/api/v1/rotations/compare", json={"farm": demo["profile"]}).json()
    assert [s["role"] for s in result["strategies"]] == [
        "current",
        "resilience_and_soil",
        "farmer_priorities",
    ]
    blocked = {
        c["evaluation"]["rotation"]["id"]
        for c in result["considered"]
        if not c["evaluation"]["admissible"]
    }
    assert "soybean_oat_hay_3y" in blocked
    assert all(s["explanation"]["why_fr"] for s in result["strategies"])
    assert len(result["strategies"][0]["evaluation"]["stress_test"]["yearly"]) == 45


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ({"location": {"latitude": 95, "longitude": 0}}, "validation_error"),
        ({"location": {"latitude": -30, "longitude": 20}}, "unsupported_location"),
        ({"location": {"latitude": 48, "longitude": -70}, "last_year": 2026}, "invalid_request"),
        ({"location": {"latitude": 10, "longitude": 10}}, "climate_data_unavailable"),
    ],
)
def test_errors_are_problem_details(client: TestClient, payload: dict[str, Any], code: str) -> None:
    response = client.post("/api/v1/climate/analyze", json=payload)
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == code


def test_unknown_crop_is_rejected(client: TestClient, demo: dict[str, Any]) -> None:
    farm = {**demo["profile"], "current_rotation": {"name_fr": "x", "crop_ids": ["banana"]}}
    response = client.post("/api/v1/rotations/compare", json={"farm": farm})
    assert response.status_code == 422 and "banana" in response.json()["detail"]
