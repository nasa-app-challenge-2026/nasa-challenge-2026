"""HTTP contracts shared by several endpoints, and their mapping from domain objects."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from fieldshift.domain.agronomy.farm import (
    LocationPrecision,
    ObservationTopic,
)
from fieldshift.domain.geo import GeoPoint, GridCell
from fieldshift.domain.provenance import (
    DataNature,
    DataOrigin,
    DataQualityReport,
    DatasetProvenance,
    QualityLevel,
    WarningCode,
)


class ApiModel(BaseModel):
    """Response model."""

    model_config = ConfigDict(frozen=True)


class RequestModel(BaseModel):
    """Request model: unknown fields are rejected so that typos never pass silently."""

    model_config = ConfigDict(extra="forbid")


class LocationIn(RequestModel):
    latitude: float = Field(ge=-90, le=90, description="Degrés décimaux WGS84, positif au nord.")
    longitude: float = Field(ge=-180, le=180, description="Degrés décimaux WGS84, positif à l'est.")
    precision: LocationPrecision = LocationPrecision.EXACT

    def to_point(self) -> GeoPoint:
        return GeoPoint(self.latitude, self.longitude)


class ObservationModel(RequestModel):
    text: str = Field(min_length=1, max_length=500)
    topic: ObservationTopic = ObservationTopic.OTHER
    year: int | None = Field(default=None, ge=1900, le=2100)
    crop_id: str | None = Field(default=None, max_length=64)


class GeoPointOut(ApiModel):
    latitude: float
    longitude: float


class GridCellOut(ApiModel):
    cell_id: str
    center: GeoPointOut
    latitude_min: float
    latitude_max: float
    longitude_min: float
    longitude_max: float


class ParameterOut(ApiModel):
    code: str
    name: str
    unit: str
    definition: str


class ProvenanceOut(ApiModel):
    provider: str
    product: str
    api_version: str | None
    upstream_sources: list[str]
    parameters: list[ParameterOut]
    period_start: date
    period_end: date
    retrieved_at: datetime
    origin: DataOrigin
    nature: DataNature
    time_standard: str
    spatial_resolution: str
    grid_cell: GridCellOut
    grid_cell_elevation_m: float | None
    request_url: str
    content_sha256: str
    citation: str
    license: str


class WarningOut(ApiModel):
    code: WarningCode
    message_fr: str


class ExcludedYearOut(ApiModel):
    year: int
    missing_days: int


class QualityOut(ApiModel):
    level: QualityLevel
    first_year_requested: int
    last_year_requested: int
    years_analysed: list[int]
    years_excluded: list[ExcludedYearOut]
    warnings: list[WarningOut]


class PeriodOut(ApiModel):
    first_year: int
    last_year: int
    years_analysed: int


def point_out(point: GeoPoint) -> GeoPointOut:
    return GeoPointOut(latitude=point.latitude, longitude=point.longitude)


def grid_cell_out(cell: GridCell) -> GridCellOut:
    return GridCellOut(
        cell_id=cell.cell_id,
        center=point_out(cell.center),
        latitude_min=cell.latitude_min,
        latitude_max=cell.latitude_max,
        longitude_min=cell.longitude_min,
        longitude_max=cell.longitude_max,
    )


def provenance_out(provenance: DatasetProvenance) -> ProvenanceOut:
    return ProvenanceOut(
        provider=provenance.provider,
        product=provenance.product,
        api_version=provenance.api_version,
        upstream_sources=list(provenance.upstream_sources),
        parameters=[
            ParameterOut(code=p.code, name=p.name, unit=p.unit, definition=p.definition)
            for p in provenance.parameters
        ],
        period_start=provenance.period_start,
        period_end=provenance.period_end,
        retrieved_at=provenance.retrieved_at,
        origin=provenance.origin,
        nature=provenance.nature,
        time_standard=provenance.time_standard,
        spatial_resolution=provenance.spatial_resolution,
        grid_cell=grid_cell_out(provenance.grid_cell),
        grid_cell_elevation_m=provenance.grid_cell_elevation_m,
        request_url=provenance.request_url,
        content_sha256=provenance.content_sha256,
        citation=provenance.citation,
        license=provenance.license,
    )


def quality_out(quality: DataQualityReport) -> QualityOut:
    return QualityOut(
        level=quality.level,
        first_year_requested=quality.first_year_requested,
        last_year_requested=quality.last_year_requested,
        years_analysed=list(quality.years_analysed),
        years_excluded=[
            ExcludedYearOut(year=e.year, missing_days=e.missing_days)
            for e in quality.years_excluded
        ],
        warnings=[WarningOut(code=w.code, message_fr=w.message_fr) for w in quality.warnings],
    )


def period_out(quality: DataQualityReport) -> PeriodOut:
    return PeriodOut(
        first_year=quality.first_year_requested,
        last_year=quality.last_year_requested,
        years_analysed=len(quality.years_analysed),
    )
