"""Use case: compare the declared rotation with alternatives over the historical record."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from fieldshift.application.climate_analysis import (
    ClimateAnalysis,
    ClimateAnalysisRequest,
    ClimateAnalysisService,
)
from fieldshift.application.errors import InvalidAnalysisRequestError
from fieldshift.domain.agronomy.crops import CropCatalog
from fieldshift.domain.agronomy.farm import CropRotation, FarmProfile
from fieldshift.domain.agronomy.validation import InvalidRotationError
from fieldshift.domain.simulation.assessment import ScoringPolicy, ScreeningPolicy
from fieldshift.domain.simulation.comparison import (
    RotationComparison,
    UnknownTemplateError,
    compare_rotations,
)


@dataclass(frozen=True, slots=True)
class FarmAnalysis:
    climate: ClimateAnalysis
    comparison: RotationComparison


class RotationComparisonService:
    def __init__(
        self,
        climate: ClimateAnalysisService,
        catalog: CropCatalog,
        templates: Sequence[CropRotation],
        screening: ScreeningPolicy | None = None,
        scoring: ScoringPolicy | None = None,
    ) -> None:
        self._climate = climate
        self._catalog = catalog
        self._templates = tuple(templates)
        self._screening = screening or ScreeningPolicy()
        self._scoring = scoring or ScoringPolicy()

    def compare(
        self,
        farm: FarmProfile,
        first_year: int | None = None,
        last_year: int | None = None,
        selected_template_ids: Sequence[str] | None = None,
    ) -> FarmAnalysis:
        unknown = [c for c in farm.current_rotation.crop_ids if c not in self._catalog]
        if unknown:
            raise InvalidAnalysisRequestError(f"Culture(s) inconnue(s) : {', '.join(unknown)}.")
        climate = self._climate.analyze(
            ClimateAnalysisRequest(
                location=farm.location,
                location_precision=farm.location_precision,
                first_year=first_year,
                last_year=last_year,
                observations=farm.observations,
            )
        )
        try:
            comparison = compare_rotations(
                farm,
                self._templates,
                self._catalog,
                climate.contexts,
                selected_template_ids=selected_template_ids,
                screening=self._screening,
                scoring=self._scoring,
            )
        except InvalidRotationError as error:
            raise InvalidAnalysisRequestError(str(error)) from error
        except UnknownTemplateError as error:
            raise InvalidAnalysisRequestError(
                f"Modèle de rotation inconnu : {error.template_id}."
            ) from error
        return FarmAnalysis(climate=climate, comparison=comparison)
