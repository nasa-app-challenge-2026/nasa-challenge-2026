"""NASA POWER implementation of ``HistoricalClimateProvider``.

Order of resolution for one request (keyed by grid cell, period and parameters):

1. local cache (responses already fetched by this installation);
2. live NASA POWER API, then stored in the cache;
3. on failure only, the versioned snapshot with the largest overlap, clearly flagged.

In ``snapshot_only`` mode (offline demonstrations) only step 3 is used, without a fallback
warning because nothing failed.
"""

from __future__ import annotations

import logging
import threading
from datetime import date
from enum import StrEnum

from fieldshift.application.errors import (
    ClimateDataUnavailableError,
    ClimateProviderRateLimitedError,
)
from fieldshift.domain.geo import GeoPoint, GridCell
from fieldshift.domain.provenance import (
    ClimateDataset,
    DataNature,
    DataOrigin,
    DatasetProvenance,
)
from fieldshift.infrastructure.nasa_power.client import (
    PowerClient,
    PowerClientError,
    PowerDailyRequest,
    PowerRateLimitedError,
)
from fieldshift.infrastructure.nasa_power.grid import SPATIAL_RESOLUTION_FR, merra2_cell
from fieldshift.infrastructure.nasa_power.parser import PowerResponseError, parse_daily_point
from fieldshift.infrastructure.nasa_power.store import ResponseStore, StoredResponse

logger = logging.getLogger(__name__)

FIRST_DAILY_YEAR = 1981
"""Daily data are available from 1981/01/01 (POWER Daily API documentation)."""

PROVIDER = "NASA POWER (Prediction Of Worldwide Energy Resources), NASA Langley Research Center"
PRODUCT = "POWER Daily API, données quotidiennes ponctuelles, communauté Agroclimatologie (AG)"
LICENSE = (
    "Données de missions NASA : Creative Commons Zero (CC0), sans restriction d'usage. La NASA "
    "demande de citer les jeux de données utilisés (NASA Earthdata, Data Use and Citation "
    "Guidance)."
)


class ClimateSourceMode(StrEnum):
    LIVE = "live"
    SNAPSHOT_ONLY = "snapshot_only"


def citation(api_version: str | None, retrieved: date) -> str:
    """Acknowledgement requested by the POWER project (power.larc.nasa.gov/docs/referencing)."""
    version = api_version or "unknown version"
    return (
        "The data was obtained from the National Aeronautics and Space Administration (NASA) "
        "Langley Research Center (LaRC) Prediction Of Worldwide Energy Resources (POWER) "
        "project funded through the NASA Earth Science Division. The data was obtained from "
        f"the POWER Project's Daily API {version} on {retrieved:%Y/%m/%d}."
    )


class PowerHistoricalProvider:
    def __init__(
        self,
        *,
        client: PowerClient | None,
        cache: ResponseStore | None,
        snapshots: ResponseStore | None,
        mode: ClimateSourceMode = ClimateSourceMode.LIVE,
    ) -> None:
        if mode is ClimateSourceMode.LIVE and client is None:
            raise ValueError("live mode requires a NASA POWER client")
        self._client = client
        self._cache = cache
        self._snapshots = snapshots
        self._mode = mode
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    @property
    def first_available_year(self) -> int:
        return FIRST_DAILY_YEAR

    @property
    def spatial_resolution(self) -> str:
        return SPATIAL_RESOLUTION_FR

    @property
    def mode(self) -> ClimateSourceMode:
        return self._mode

    def grid_cell(self, location: GeoPoint) -> GridCell:
        return merra2_cell(location)

    def _lock(self, key: str) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(key, threading.Lock())

    def daily_history(self, location: GeoPoint, first_year: int, last_year: int) -> ClimateDataset:
        cell = self.grid_cell(location)
        request = PowerDailyRequest(
            latitude=cell.center.latitude,
            longitude=cell.center.longitude,
            start=date(first_year, 1, 1),
            end=date(last_year, 12, 31),
        )
        # One fetch per cell and period at a time: concurrent requests wait for the cache.
        with self._lock(request.key()):
            if self._mode is ClimateSourceMode.SNAPSHOT_ONLY:
                return self._from_snapshot(request, cell, fallback_reason=None, error=None)
            return self._resolve_live(request, cell)

    def _resolve_live(self, request: PowerDailyRequest, cell: GridCell) -> ClimateDataset:
        if self._cache is not None:
            cached = self._cache.get(request.key())
            if cached is not None:
                try:
                    return self._dataset(cached, cell, DataOrigin.LOCAL_CACHE)
                except PowerResponseError:
                    logger.warning(
                        "cached response invalid, refetching", extra={"cell": cell.cell_id}
                    )

        if self._client is None:  # excluded by the constructor; kept for type narrowing
            raise RuntimeError("live mode without a NASA POWER client")
        try:
            raw = self._client.fetch(request)
            parse_daily_point(raw.body)  # validate before anything is stored
        except PowerRateLimitedError as error:
            logger.warning("NASA POWER rate limited", extra={"cell": cell.cell_id})
            return self._from_snapshot(
                request,
                cell,
                fallback_reason=(
                    "NASA POWER a refusé la requête (limite de fréquence) : un instantané "
                    "vérifié des données NASA est utilisé à la place."
                ),
                error=ClimateProviderRateLimitedError(
                    "NASA POWER limite temporairement les requêtes et aucun instantané vérifié "
                    "ne couvre cet endroit. Réessayez dans quelques minutes."
                ),
                cause=error,
            )
        except (PowerClientError, PowerResponseError) as error:
            logger.warning(
                "NASA POWER request failed",
                extra={"cell": cell.cell_id, "reason": str(error)},
            )
            return self._from_snapshot(
                request,
                cell,
                fallback_reason=(
                    "NASA POWER n'a pas répondu correctement : un instantané vérifié des données "
                    "NASA est utilisé à la place."
                ),
                error=ClimateDataUnavailableError(
                    "Les données NASA POWER sont momentanément indisponibles et aucun instantané "
                    "vérifié ne couvre cet endroit."
                ),
                cause=error,
            )

        if self._cache is not None:
            stored = self._cache.put(request, raw)
        else:
            stored = StoredResponse(
                key=request.key(),
                body=raw.body,
                request_url=raw.url,
                retrieved_at=raw.retrieved_at,
                sha256="",
                start=request.start,
                end=request.end,
                latitude=request.latitude,
                longitude=request.longitude,
            )
        logger.info("NASA POWER data fetched", extra={"cell": cell.cell_id})
        return self._dataset(stored, cell, DataOrigin.LIVE_API)

    def _from_snapshot(
        self,
        request: PowerDailyRequest,
        cell: GridCell,
        *,
        fallback_reason: str | None,
        error: ClimateDataUnavailableError | None,
        cause: Exception | None = None,
    ) -> ClimateDataset:
        snapshot = self._snapshots.best_overlap(request) if self._snapshots else None
        if snapshot is None:
            raise error or ClimateDataUnavailableError(
                "Mode hors ligne : aucun instantané vérifié des données NASA ne couvre cet "
                "endroit. Les instantanés disponibles couvrent les fermes de démonstration."
            ) from cause
        dataset = self._dataset(snapshot, cell, DataOrigin.VERIFIED_SNAPSHOT)
        if fallback_reason is None:
            return dataset
        return ClimateDataset(
            series=dataset.series,
            provenance=dataset.provenance,
            fallback_reason_fr=fallback_reason,
        )

    def _dataset(
        self, stored: StoredResponse, cell: GridCell, origin: DataOrigin
    ) -> ClimateDataset:
        parsed = parse_daily_point(stored.body)
        provenance = DatasetProvenance(
            provider=PROVIDER,
            product=PRODUCT,
            api_version=parsed.api_version,
            upstream_sources=parsed.upstream_sources,
            parameters=parsed.parameters,
            period_start=stored.start,
            period_end=stored.end,
            retrieved_at=stored.retrieved_at,
            origin=origin,
            nature=DataNature.REANALYSIS_ESTIMATE,
            time_standard=parsed.time_standard or "LST",
            spatial_resolution=SPATIAL_RESOLUTION_FR,
            grid_cell=cell,
            grid_cell_elevation_m=parsed.elevation_m,
            request_url=stored.request_url,
            content_sha256=stored.sha256,
            citation=citation(parsed.api_version, stored.retrieved_at.date()),
            license=LICENSE,
        )
        return ClimateDataset(series=parsed.series, provenance=provenance)
