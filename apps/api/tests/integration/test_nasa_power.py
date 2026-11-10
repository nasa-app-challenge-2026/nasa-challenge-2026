from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from fieldshift.application.errors import ClimateDataUnavailableError
from fieldshift.domain.geo import GeoPoint
from fieldshift.domain.provenance import DataOrigin
from fieldshift.infrastructure.nasa_power.client import (
    PowerClient,
    PowerClientError,
    PowerDailyRequest,
    PowerRateLimitedError,
    RawResponse,
)
from fieldshift.infrastructure.nasa_power.grid import merra2_cell
from fieldshift.infrastructure.nasa_power.parser import PowerResponseError, parse_daily_point
from fieldshift.infrastructure.nasa_power.provider import PowerHistoricalProvider
from fieldshift.infrastructure.nasa_power.store import ResponseStore

FIXTURE = (Path(__file__).parents[1] / "fixtures" / "power_daily_6days.json").read_bytes()


def test_grid_cell_matches_empirical_power_behaviour() -> None:
    cell = merra2_cell(GeoPoint(48.23, -69.80))
    assert (cell.center.latitude, cell.center.longitude) == (48.0, -70.0)
    for lat, lon in [(48.0, -70.0), (47.76, -70.30), (48.24, -69.69)]:
        assert cell.contains(GeoPoint(lat, lon))
    assert merra2_cell(GeoPoint(48.26, -69.8)).center.latitude == 48.5
    assert merra2_cell(GeoPoint(48.23, -69.68)).center.longitude == -69.375


def test_parser_normalises_recorded_response() -> None:
    parsed = parse_daily_point(FIXTURE)
    first = parsed.series.records[0]
    assert (
        first.day == date(2024, 6, 28) and first.t_max_c == 18.44 and first.precipitation_mm == 0.33
    )
    assert parsed.api_version == "v2.10.3" and parsed.elevation_m == 244.82


def test_parser_turns_fill_values_into_missing_and_rejects_unknown_units() -> None:
    payload = json.loads(FIXTURE)
    payload["properties"]["parameter"]["T2M_MIN"]["20240628"] = -999.0
    assert parse_daily_point(json.dumps(payload).encode()).series.records[0].t_min_c is None
    payload["parameters"]["PRECTOTCORR"]["units"] = "inch"
    with pytest.raises(PowerResponseError, match="unit"):
        parse_daily_point(json.dumps(payload).encode())


def client_for(handler: httpx.MockTransport) -> PowerClient:
    return PowerClient(httpx.Client(transport=handler), "https://power.test", sleep=lambda _: None)


REQUEST = PowerDailyRequest(48.0, -70.0, date(2024, 6, 28), date(2024, 7, 3))


def test_client_retries_server_errors_and_stops_on_rate_limit() -> None:
    calls = []

    def flaky(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(503) if len(calls) == 1 else httpx.Response(200, content=FIXTURE)

    assert client_for(httpx.MockTransport(flaky)).fetch(REQUEST).body == FIXTURE
    with pytest.raises(PowerRateLimitedError):
        client_for(httpx.MockTransport(lambda r: httpx.Response(429))).fetch(REQUEST)
    with pytest.raises(PowerClientError):
        client_for(httpx.MockTransport(lambda r: httpx.Response(400))).fetch(REQUEST)


def test_provider_uses_cache_then_snapshot_fallback(tmp_path: Path) -> None:
    calls = []

    def ok(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, content=FIXTURE)

    cache = ResponseStore(tmp_path / "cache", writable=True)
    provider = PowerHistoricalProvider(
        client=client_for(httpx.MockTransport(ok)), cache=cache, snapshots=None
    )
    point = GeoPoint(48.23, -69.8)
    assert provider.daily_history(point, 2024, 2024).provenance.origin is DataOrigin.LIVE_API
    assert provider.daily_history(point, 2024, 2024).provenance.origin is DataOrigin.LOCAL_CACHE
    assert len(calls) == 1
    assert "48.0000" in str(calls[0].url) and "48.23" not in str(
        calls[0].url
    )  # farm position stays private

    snapshots = ResponseStore(tmp_path / "snap", writable=True)
    snapshots.put(
        PowerDailyRequest(48.0, -70.0, date(2024, 1, 1), date(2024, 12, 31)),
        RawResponse(FIXTURE, "u", datetime.now(UTC)),
    )
    down = client_for(httpx.MockTransport(lambda r: httpx.Response(500)))
    fallback = PowerHistoricalProvider(client=down, cache=None, snapshots=snapshots)
    dataset = fallback.daily_history(point, 2024, 2024)
    assert dataset.provenance.origin is DataOrigin.VERIFIED_SNAPSHOT and dataset.fallback_reason_fr
    no_snapshot = PowerHistoricalProvider(client=down, cache=None, snapshots=None)
    with pytest.raises(ClimateDataUnavailableError):
        no_snapshot.daily_history(point, 2024, 2024)


def test_tampered_snapshot_is_refused(tmp_path: Path) -> None:
    store = ResponseStore(tmp_path, writable=True)
    stored = store.put(REQUEST, RawResponse(FIXTURE, "u", datetime.now(UTC)))
    (tmp_path / f"{stored.key}.json").write_bytes(FIXTURE + b" ")
    assert store.get(stored.key) is None
