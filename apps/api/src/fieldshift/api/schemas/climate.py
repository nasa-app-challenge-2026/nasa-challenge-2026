"""Contracts of ``POST /api/v1/climate/analyze``."""

from __future__ import annotations

from pydantic import Field

from fieldshift.api.schemas.catalog import observation_model
from fieldshift.api.schemas.common import (
    ApiModel,
    GeoPointOut,
    LocationIn,
    ObservationModel,
    PeriodOut,
    ProvenanceOut,
    QualityOut,
    RequestModel,
    period_out,
    point_out,
    provenance_out,
    quality_out,
)
from fieldshift.application.climate_analysis import ClimateAnalysis
from fieldshift.domain.climate.indicators import IndicatorGroup, IndicatorKind, IndicatorSeries
from fieldshift.domain.climate.statistics import Summary
from fieldshift.domain.observation_checks import SCALE_NOTE_FR, CheckStatus


class ClimateAnalyzeRequest(RequestModel):
    location: LocationIn
    first_year: int | None = Field(default=None, ge=1900, le=2100)
    last_year: int | None = Field(default=None, ge=1900, le=2100)
    observations: list[ObservationModel] = Field(default_factory=list, max_length=30)


class TrendOut(ApiModel):
    slope_per_decade: float
    p_value: float
    years: int
    is_significant: bool


class SummaryOut(ApiModel):
    count: int
    mean: float
    median: float
    p20: float
    p80: float
    minimum: float
    maximum: float
    standard_deviation: float
    trend: TrendOut | None


class YearValueOut(ApiModel):
    year: int
    value: float | None


class IndicatorOut(ApiModel):
    id: str
    group: IndicatorGroup
    kind: IndicatorKind
    label_fr: str
    unit: str
    definition_fr: str
    source_ids: list[str]
    values: list[YearValueOut]
    summary: SummaryOut | None


class MonthlyNormalOut(ApiModel):
    month: int
    t_mean_c: float
    t_max_mean_c: float
    t_min_mean_c: float
    precipitation_mm: float


class YearPositionOut(ApiModel):
    indicator_id: str
    value: float | None
    median: float | None
    years_higher: int
    years_lower: int
    years_compared: int


class ObservationCheckOut(ApiModel):
    observation: ObservationModel
    status: CheckStatus
    positions: list[YearPositionOut]


class HeatUnitReferenceOut(ApiModel):
    """Site constant of the Québec crop heat unit method."""

    median_last_spring_frost_doy: int
    reference_first_year: int
    reference_last_year: int


class ClimateAnalysisOut(ApiModel):
    location: GeoPointOut
    period: PeriodOut
    provenance: ProvenanceOut
    quality: QualityOut
    indicators: list[IndicatorOut]
    monthly_normals: list[MonthlyNormalOut]
    observation_checks: list[ObservationCheckOut]
    observation_scale_note_fr: str
    heat_unit_reference: HeatUnitReferenceOut


def summary_out(summary: Summary | None) -> SummaryOut | None:
    if summary is None:
        return None
    trend = summary.trend
    return SummaryOut(
        count=summary.count,
        mean=summary.mean,
        median=summary.median,
        p20=summary.p20,
        p80=summary.p80,
        minimum=summary.minimum,
        maximum=summary.maximum,
        standard_deviation=summary.standard_deviation,
        trend=(
            TrendOut(
                slope_per_decade=trend.slope_per_decade,
                p_value=trend.p_value,
                years=trend.years,
                is_significant=trend.is_significant,
            )
            if trend
            else None
        ),
    )


def indicator_out(series: IndicatorSeries) -> IndicatorOut:
    definition = series.definition
    return IndicatorOut(
        id=definition.id,
        group=definition.group,
        kind=definition.kind,
        label_fr=definition.label_fr,
        unit=definition.unit,
        definition_fr=definition.definition_fr,
        source_ids=list(definition.source_ids),
        values=[
            YearValueOut(year=year, value=value)
            for year, value in zip(series.years, series.values, strict=True)
        ],
        summary=summary_out(series.summary),
    )


def climate_analysis_out(analysis: ClimateAnalysis) -> ClimateAnalysisOut:
    site = analysis.contexts[0].site
    return ClimateAnalysisOut(
        location=point_out(analysis.location),
        period=period_out(analysis.quality),
        provenance=provenance_out(analysis.provenance),
        quality=quality_out(analysis.quality),
        indicators=[indicator_out(series) for series in analysis.indicators],
        monthly_normals=[
            MonthlyNormalOut(
                month=n.month,
                t_mean_c=n.t_mean_c,
                t_max_mean_c=n.t_max_mean_c,
                t_min_mean_c=n.t_min_mean_c,
                precipitation_mm=n.precipitation_mm,
            )
            for n in analysis.monthly_normals
        ],
        observation_checks=[
            ObservationCheckOut(
                observation=observation_model(check.observation),
                status=check.status,
                positions=[
                    YearPositionOut(
                        indicator_id=p.indicator_id,
                        value=p.value,
                        median=p.median,
                        years_higher=p.years_higher,
                        years_lower=p.years_lower,
                        years_compared=p.years_compared,
                    )
                    for p in check.positions
                ],
            )
            for check in analysis.observation_checks
        ],
        observation_scale_note_fr=SCALE_NOTE_FR,
        heat_unit_reference=HeatUnitReferenceOut(
            median_last_spring_frost_doy=site.chu_search_start_index + 1,
            reference_first_year=site.chu_reference_first_year,
            reference_last_year=site.chu_reference_last_year,
        ),
    )
