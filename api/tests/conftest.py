"""Shared fixtures of the server tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from field_shift.api.app import create_app
from field_shift.api.settings import Settings
from field_shift.services.plan_service import PlanService
from field_shift.services.ranking_service import RankingService
from field_shift.tools.make_examples import ExampleWeatherProvider
from tests.helpers.site_stub import FixedSiteData

CONTRACT_DIR = Path(__file__).resolve().parents[2] / "backend" / "contract"
EXAMPLES_DIR = CONTRACT_DIR / "examples"
SCHEMA_PATH = CONTRACT_DIR / "field-shift.schema.json"


@pytest.fixture(scope="session")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def example_inputs() -> dict[str, dict]:
    return {
        path.name.removesuffix(".input.json"): json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(EXAMPLES_DIR.glob("*.input.json"))
    }


@pytest.fixture
def plan_client() -> TestClient:
    """The application on the fixed weather of the contract examples and the test site data
    (no network)."""
    return TestClient(
        create_app(
            Settings(),
            PlanService(ExampleWeatherProvider()),
            RankingService(FixedSiteData()),
        )
    )
