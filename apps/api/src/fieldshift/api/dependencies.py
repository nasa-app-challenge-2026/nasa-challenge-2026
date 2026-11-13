"""Composition root: the only place where concrete implementations are chosen."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Annotated

import httpx
from fastapi import Depends, Request

from fieldshift.application.climate_analysis import ClimateAnalysisService
from fieldshift.application.ports import HistoricalClimateProvider
from fieldshift.application.reference import ReferenceData
from fieldshift.application.rotation_comparison import RotationComparisonService
from fieldshift.infrastructure.nasa_power.client import PowerClient, build_http_client
from fieldshift.infrastructure.nasa_power.provider import ClimateSourceMode, PowerHistoricalProvider
from fieldshift.infrastructure.nasa_power.store import ResponseStore
from fieldshift.infrastructure.reference_data import load_reference_data
from fieldshift.infrastructure.settings import Settings


@dataclass(frozen=True, slots=True)
class Container:
    settings: Settings
    reference: ReferenceData
    climate: ClimateAnalysisService
    comparison: RotationComparisonService
    http_client: httpx.Client | None


def build_container(
    settings: Settings,
    provider: HistoricalClimateProvider | None = None,
    today: Callable[[], date] | None = None,
) -> Container:
    reference = load_reference_data(settings.reference_dir)
    http_client: httpx.Client | None = None
    if provider is None:
        snapshots = ResponseStore(settings.snapshot_dir, writable=False)
        if settings.climate_source is ClimateSourceMode.LIVE:
            http_client = build_http_client(settings.power_timeout_seconds)
            provider = PowerHistoricalProvider(
                client=PowerClient(
                    http_client,
                    settings.power_base_url,
                    max_attempts=settings.power_max_attempts,
                    max_concurrent_requests=settings.power_max_concurrent_requests,
                ),
                cache=ResponseStore(settings.power_cache_dir, writable=True),
                snapshots=snapshots,
            )
        else:
            provider = PowerHistoricalProvider(
                client=None, cache=None, snapshots=snapshots, mode=ClimateSourceMode.SNAPSHOT_ONLY
            )
    climate = ClimateAnalysisService(provider, today or (lambda: datetime.now(UTC).date()))
    comparison = RotationComparisonService(climate, reference.catalog, reference.rotation_templates)
    return Container(settings, reference, climate, comparison, http_client)


def get_container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container


ContainerDep = Annotated[Container, Depends(get_container)]
