"""Fetch NASA POWER data for each demo farm and store it as a verified snapshot.

Usage (from apps/api):  uv run python ../../scripts/refresh_snapshot.py [last_year]
Uses the production pipeline (grid cell, client, parser, store): what is committed is
exactly what the API would have fetched.
"""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime

from fieldshift.infrastructure.nasa_power.client import PowerClient, PowerDailyRequest, build_http_client
from fieldshift.infrastructure.nasa_power.grid import merra2_cell
from fieldshift.infrastructure.nasa_power.parser import parse_daily_point
from fieldshift.infrastructure.nasa_power.provider import FIRST_DAILY_YEAR
from fieldshift.infrastructure.nasa_power.store import ResponseStore
from fieldshift.infrastructure.reference_data import load_reference_data
from fieldshift.infrastructure.settings import Settings


def main() -> None:
    settings = Settings()
    last_year = int(sys.argv[1]) if len(sys.argv) > 1 else datetime.now(UTC).year - 1
    store = ResponseStore(settings.snapshot_dir, writable=True)
    reference = load_reference_data(settings.reference_dir)
    with build_http_client(settings.power_timeout_seconds) as http:
        client = PowerClient(http, settings.power_base_url)
        for demo in reference.demo_farms:
            cell = merra2_cell(demo.profile.location)
            request = PowerDailyRequest(
                cell.center.latitude, cell.center.longitude,
                date(FIRST_DAILY_YEAR, 1, 1), date(last_year, 12, 31),
            )
            raw = client.fetch(request)
            parsed = parse_daily_point(raw.body)
            stored = store.put(request, raw)
            print(f"{demo.id}: cell {cell.cell_id}, {len(parsed.series)} days -> {stored.key}")


if __name__ == "__main__":
    main()
