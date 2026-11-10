"""Use case: describe the historical climate of a location (pipeline steps 1 to 12).

validate request -> fetch provider data (cache, live, snapshot) -> detect incomplete years ->
build yearly contexts -> compute indicators -> attach provenance and quality report.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date

from fieldshift.application.errors import (
    ClimateDataUnavailableError,
    InvalidAnalysisRequestError,
    UnsupportedLocationError,
)
from fieldshift.application.ports import HistoricalClimateProvider
from fieldshift.domain.agronomy.farm import FarmObservation, LocationPrecision
from fieldshift.domain.climate.indicators import (
    IndicatorSeries,
    MonthlyNormal,
    compute_all_indicators,
    compute_monthly_normals,
)
from fieldshift.domain.climate.series import YearCompleteness, days_in_year
from fieldshift.domain.climate.year_context import YearContext, build_year_contexts
from fieldshift.domain.geo import GeoPoint, GridCell
from fieldshift.domain.observation_checks import ObservationCheck, check_observations
from fieldshift.domain.provenance import (
    DataQualityReport,
    DatasetProvenance,
    ExcludedYear,
    QualityLevel,
    QualityWarning,
    WarningCode,
)

KM_PER_DEGREE_LATITUDE = 111.2
NEAR_BOUNDARY_DEGREES = 0.05
ROBUST_RECORD_YEARS = 30
"""Climate normals are conventionally computed over 30 years (the Québec agroclimatic atlas
uses 30-year periods). Shorter records give less stable frequencies."""


@dataclass(frozen=True, slots=True)
class ClimateAnalysisRequest:
    location: GeoPoint
    location_precision: LocationPrecision = LocationPrecision.EXACT
    first_year: int | None = None
    last_year: int | None = None
    observations: tuple[FarmObservation, ...] = field(default=())


@dataclass(frozen=True, slots=True)
class ClimateAnalysis:
    location: GeoPoint
    provenance: DatasetProvenance
    quality: DataQualityReport
    contexts: tuple[YearContext, ...]
    indicators: tuple[IndicatorSeries, ...]
    monthly_normals: tuple[MonthlyNormal, ...]
    observation_checks: tuple[ObservationCheck, ...]

    @property
    def years(self) -> tuple[int, ...]:
        return tuple(context.year for context in self.contexts)


def grid_warnings(cell: GridCell, location: GeoPoint) -> list[QualityWarning]:
    height_km = (cell.latitude_max - cell.latitude_min) * KM_PER_DEGREE_LATITUDE
    width_km = (
        (cell.longitude_max - cell.longitude_min)
        * KM_PER_DEGREE_LATITUDE
        * math.cos(math.radians(cell.center.latitude))
    )
    warnings = [
        QualityWarning(
            WarningCode.COARSE_GRID_CELL,
            f"Les valeurs représentent une cellule d'environ {height_km:.0f} km × {width_km:.0f} km "
            "(moyenne de la cellule), pas une mesure prise sur la ferme. Altitude, pente, "
            "proximité de l'eau et fonds de vallée peuvent rendre la ferme plus froide ou plus "
            "chaude que la cellule.",
        )
    ]
    distance = min(
        location.latitude - cell.latitude_min,
        cell.latitude_max - location.latitude,
        location.longitude - cell.longitude_min,
        cell.longitude_max - location.longitude,
    )
    if distance < NEAR_BOUNDARY_DEGREES:
        warnings.append(
            QualityWarning(
                WarningCode.NEAR_CELL_BOUNDARY,
                "La ferme est à moins de 0,05° du bord de la cellule : une cellule voisine "
                "pourrait la représenter aussi bien, avec des valeurs différentes.",
            )
        )
    return warnings


class ClimateAnalysisService:
    def __init__(self, provider: HistoricalClimateProvider, today: Callable[[], date]) -> None:
        self._provider = provider
        self._today = today

    def default_period(self) -> tuple[int, int]:
        return self._provider.first_available_year, self._today().year - 1

    def _resolve_period(self, request: ClimateAnalysisRequest) -> tuple[int, int]:
        default_first, default_last = self.default_period()
        first = request.first_year if request.first_year is not None else default_first
        last = request.last_year if request.last_year is not None else default_last
        if first < default_first:
            raise InvalidAnalysisRequestError(
                f"Les données quotidiennes commencent en {default_first}."
            )
        if last > default_last:
            raise InvalidAnalysisRequestError(
                f"Seules les années complètes sont analysées : dernière année possible {default_last}."
            )
        if first > last:
            raise InvalidAnalysisRequestError("La première année doit précéder la dernière.")
        return first, last

    def analyze(self, request: ClimateAnalysisRequest) -> ClimateAnalysis:
        if request.location.latitude < 0:
            raise UnsupportedLocationError(
                "Hémisphère sud non pris en charge pour l'instant : les saisons y chevauchent "
                "deux années civiles et les indicateurs supposent l'hémisphère nord."
            )
        first, last = self._resolve_period(request)
        dataset = self._provider.daily_history(request.location, first, last)

        complete = [year for year in dataset.series.complete_years() if first <= year.year <= last]
        if not complete:
            raise ClimateDataUnavailableError(
                "Aucune année complète n'est disponible pour cette période et cet endroit."
            )
        contexts = build_year_contexts(request.location.latitude, complete)
        indicators = compute_all_indicators(contexts)
        quality = self._quality_report(dataset.series.completeness(), first, last, contexts)
        warnings = [
            *quality.warnings,
            *grid_warnings(dataset.provenance.grid_cell, request.location),
        ]
        if request.location_precision is LocationPrecision.APPROXIMATE:
            warnings.append(
                QualityWarning(
                    WarningCode.APPROXIMATE_LOCATION,
                    "Position approximative (par exemple le centre de la municipalité) : la "
                    "cellule retenue pourrait ne pas être celle de la ferme.",
                )
            )
        if dataset.fallback_reason_fr:
            warnings.append(
                QualityWarning(WarningCode.SNAPSHOT_FALLBACK, dataset.fallback_reason_fr)
            )
        quality = DataQualityReport(
            level=quality.level,
            first_year_requested=quality.first_year_requested,
            last_year_requested=quality.last_year_requested,
            years_analysed=quality.years_analysed,
            years_excluded=quality.years_excluded,
            warnings=tuple(warnings),
        )
        series_by_id = {series.definition.id: series for series in indicators}
        return ClimateAnalysis(
            location=request.location,
            provenance=dataset.provenance,
            quality=quality,
            contexts=contexts,
            indicators=indicators,
            monthly_normals=compute_monthly_normals(contexts),
            observation_checks=check_observations(request.observations, series_by_id),
        )

    @staticmethod
    def _quality_report(
        completeness: Sequence[YearCompleteness],
        first: int,
        last: int,
        contexts: Sequence[YearContext],
    ) -> DataQualityReport:
        analysed = tuple(context.year for context in contexts)
        missing_by_year = {entry.year: entry.missing_days for entry in completeness}
        excluded = tuple(
            ExcludedYear(year, missing_by_year.get(year, days_in_year(year)))
            for year in range(first, last + 1)
            if year not in analysed
        )
        warnings: list[QualityWarning] = []
        if excluded:
            warnings.append(
                QualityWarning(
                    WarningCode.INCOMPLETE_YEARS_EXCLUDED,
                    f"{len(excluded)} année(s) incomplète(s) écartée(s) : "
                    f"{', '.join(str(e.year) for e in excluded)}. Aucune valeur manquante n'est "
                    "remplacée par une estimation.",
                )
            )
        if len(analysed) < ROBUST_RECORD_YEARS:
            warnings.append(
                QualityWarning(
                    WarningCode.SHORT_RECORD,
                    f"{len(analysed)} années analysées : moins de 30 ans, les fréquences "
                    "calculées sont moins stables.",
                )
            )
        return DataQualityReport(
            level=QualityLevel.PARTIAL if excluded else QualityLevel.COMPLETE,
            first_year_requested=first,
            last_year_requested=last,
            years_analysed=analysed,
            years_excluded=excluded,
            warnings=tuple(warnings),
        )
