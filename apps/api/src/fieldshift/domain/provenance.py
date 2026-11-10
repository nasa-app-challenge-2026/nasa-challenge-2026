"""Where a piece of climate data comes from and how far it can be trusted.

Every result returned by the application carries one ``DatasetProvenance`` and one
``DataQualityReport``. Nothing derived from a model is ever labelled as an observation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from fieldshift.domain.climate.series import ClimateSeries
from fieldshift.domain.geo import GridCell


class DataOrigin(StrEnum):
    """How the data reached this process."""

    LIVE_API = "live_api"
    """Fetched from the provider while handling the request."""
    LOCAL_CACHE = "local_cache"
    """A provider response fetched earlier by this installation and reused as is."""
    VERIFIED_SNAPSHOT = "verified_snapshot"
    """A provider response versioned in the repository, checksum verified before use."""


class DataNature(StrEnum):
    """What kind of information the values are."""

    REANALYSIS_ESTIMATE = "reanalysis_estimate"
    """Model-assimilated estimate on a grid. Not a measurement taken on the farm."""
    MODEL_PROJECTION = "model_projection"
    """Output of a climate model for a scenario. Not an observation of any kind."""


@dataclass(frozen=True, slots=True)
class ParameterInfo:
    code: str
    name: str
    unit: str
    definition: str


@dataclass(frozen=True, slots=True)
class DatasetProvenance:
    provider: str
    product: str
    api_version: str | None
    upstream_sources: tuple[str, ...]
    parameters: tuple[ParameterInfo, ...]
    period_start: date
    period_end: date
    retrieved_at: datetime
    """UTC time at which the provider produced the response that is being used."""
    origin: DataOrigin
    nature: DataNature
    time_standard: str
    spatial_resolution: str
    grid_cell: GridCell
    grid_cell_elevation_m: float | None
    """Mean elevation of the grid cell as reported by the provider (metres)."""
    request_url: str
    content_sha256: str
    """SHA-256 of the provider response exactly as received, for reproducibility."""
    citation: str
    license: str


@dataclass(frozen=True, slots=True)
class ClimateDataset:
    """Normalised daily data together with the description of its source."""

    series: ClimateSeries
    provenance: DatasetProvenance
    fallback_reason_fr: str | None = None
    """Set when a verified snapshot replaced a provider call that failed."""


class QualityLevel(StrEnum):
    COMPLETE = "complete"
    """Every requested year is usable."""
    PARTIAL = "partial"
    """Some requested years were left out; the analysis rests on the others."""


class WarningCode(StrEnum):
    COARSE_GRID_CELL = "coarse_grid_cell"
    NEAR_CELL_BOUNDARY = "near_cell_boundary"
    INCOMPLETE_YEARS_EXCLUDED = "incomplete_years_excluded"
    SHORT_RECORD = "short_record"
    SNAPSHOT_FALLBACK = "snapshot_fallback"
    APPROXIMATE_LOCATION = "approximate_location"


@dataclass(frozen=True, slots=True)
class QualityWarning:
    code: WarningCode
    message_fr: str


@dataclass(frozen=True, slots=True)
class ExcludedYear:
    year: int
    missing_days: int


@dataclass(frozen=True, slots=True)
class DataQualityReport:
    level: QualityLevel
    first_year_requested: int
    last_year_requested: int
    years_analysed: tuple[int, ...]
    years_excluded: tuple[ExcludedYear, ...]
    warnings: tuple[QualityWarning, ...]
