"""Write real API responses (from the versioned NASA snapshot, offline) for frontend tests
and offline frontend development. Usage (from apps/api): uv run python ../../scripts/export_api_fixtures.py
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from fieldshift.api.app import create_app
from fieldshift.infrastructure.nasa_power.provider import ClimateSourceMode
from fieldshift.infrastructure.settings import REPO_ROOT, Settings

OUT = REPO_ROOT / "apps" / "web" / "src" / "api" / "__fixtures__"


def main() -> None:
    settings = Settings(climate_source=ClimateSourceMode.SNAPSHOT_ONLY, log_level="WARNING")
    client = TestClient(create_app(settings, today=lambda: date(2026, 11, 10)))
    demo = client.get("/api/v1/demo-farms").json()
    profile = demo[0]["profile"]
    responses = {
        "demo-farms.json": demo,
        "climate-analyze.sacre-coeur.json": client.post(
            "/api/v1/climate/analyze",
            json={"location": profile["location"], "observations": profile["observations"]},
        ).json(),
        "rotations-compare.sacre-coeur.json": client.post(
            "/api/v1/rotations/compare", json={"farm": profile}
        ).json(),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    for name, body in responses.items():
        Path(OUT / name).write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("wrote", name)


if __name__ == "__main__":
    main()
