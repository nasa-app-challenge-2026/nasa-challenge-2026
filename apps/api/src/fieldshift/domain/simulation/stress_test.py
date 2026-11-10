"""Historical climate stress test (étape D).

Each crop is checked against each analysed year, then each rotation is replayed over the
same years. A rotation of ``n`` years is assumed to occupy ``n`` fields of equal area, one per
phase, so in any year every crop of the cycle is in the ground somewhere. The exposure of a
rotation in a year is therefore the share of its fields whose crop met a documented
constraint that year.

This is a retrospective exposure count, not a reconstruction of past yields.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import fmean

from fieldshift.domain.agronomy.crops import Crop, CropCatalog
from fieldshift.domain.agronomy.farm import CropRotation
from fieldshift.domain.agronomy.suitability import (
    EVALUATED_HEAT,
    CropYearOutcome,
    FrostStatus,
    HeatStatus,
    evaluate_crop_year,
)
from fieldshift.domain.climate.statistics import percentile
from fieldshift.domain.climate.year_context import YearContext

WORST_YEARS_REPORTED = 3


@dataclass(frozen=True, slots=True)
class CropClimateRecord:
    """Outcomes of one crop over every analysed year, in year order."""

    crop_id: str
    outcomes: tuple[CropYearOutcome, ...]
    heat_evaluated: bool
    frost_evaluated: bool
    heat_shortfall_years: int
    heat_tight_years: int
    frost_exposed_years: int
    problem_years: int

    @property
    def years(self) -> int:
        return len(self.outcomes)

    def frequency(self, count: int) -> float:
        return count / self.years if self.years else 0.0

    @property
    def heat_shortfall_frequency(self) -> float | None:
        return self.frequency(self.heat_shortfall_years) if self.heat_evaluated else None

    @property
    def frost_exposure_frequency(self) -> float | None:
        return self.frequency(self.frost_exposed_years) if self.frost_evaluated else None

    @property
    def problem_frequency(self) -> float:
        return self.frequency(self.problem_years)


def evaluate_crop(crop: Crop, contexts: Sequence[YearContext]) -> CropClimateRecord:
    outcomes = tuple(evaluate_crop_year(crop, context) for context in contexts)
    return CropClimateRecord(
        crop_id=crop.id,
        outcomes=outcomes,
        heat_evaluated=any(o.heat.status in EVALUATED_HEAT for o in outcomes),
        frost_evaluated=any(o.frost.status is not FrostStatus.NOT_DOCUMENTED for o in outcomes),
        heat_shortfall_years=sum(o.heat.status is HeatStatus.INSUFFICIENT for o in outcomes),
        heat_tight_years=sum(o.heat.status is HeatStatus.TIGHT for o in outcomes),
        frost_exposed_years=sum(o.frost.status is FrostStatus.EXPOSED for o in outcomes),
        problem_years=sum(o.has_documented_problem for o in outcomes),
    )


def evaluate_crops(
    crop_ids: Sequence[str], catalog: CropCatalog, contexts: Sequence[YearContext]
) -> dict[str, CropClimateRecord]:
    """One record per distinct crop, in order of first appearance."""
    return {
        crop_id: evaluate_crop(catalog.get(crop_id), contexts)
        for crop_id in dict.fromkeys(crop_ids)
    }


@dataclass(frozen=True, slots=True)
class RotationYearExposure:
    year: int
    exposed_share: float
    """Share of the rotation's fields whose crop met a documented constraint (0 to 1)."""
    exposed_crop_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UnevaluatedHazard:
    crop_id: str
    description_fr: str


@dataclass(frozen=True, slots=True)
class RotationStressTest:
    rotation_id: str
    yearly: tuple[RotationYearExposure, ...]
    mean_exposed_share: float
    p80_exposed_share: float
    max_exposed_share: float
    years_with_exposure: int
    worst_years: tuple[int, ...]
    unevaluated_hazards: tuple[UnevaluatedHazard, ...]

    @property
    def years(self) -> int:
        return len(self.yearly)


def _unevaluated_hazards(
    rotation: CropRotation, catalog: CropCatalog, records: Mapping[str, CropClimateRecord]
) -> tuple[UnevaluatedHazard, ...]:
    hazards: list[UnevaluatedHazard] = []
    for crop_id in dict.fromkeys(rotation.crop_ids):
        crop = catalog.get(crop_id)
        record = records[crop_id]
        if crop.is_annual and not record.heat_evaluated:
            hazards.append(
                UnevaluatedHazard(crop_id, "Chaleur nécessaire à la maturité : non documentée.")
            )
        if not record.frost_evaluated:
            hazards.append(
                UnevaluatedHazard(crop_id, "Seuil de dommage par le gel : non documenté.")
            )
        hazards.extend(UnevaluatedHazard(crop_id, item) for item in crop.not_modelled_fr)
    return tuple(hazards)


def stress_test_rotation(
    rotation: CropRotation,
    catalog: CropCatalog,
    records: Mapping[str, CropClimateRecord],
) -> RotationStressTest:
    """Replay a rotation over the analysed years. ``records`` must cover all of its crops."""
    phase_records = [records[crop_id] for crop_id in rotation.crop_ids]
    year_count = phase_records[0].years
    yearly: list[RotationYearExposure] = []
    for index in range(year_count):
        exposed = [
            record.crop_id
            for record in phase_records
            if record.outcomes[index].has_documented_problem
        ]
        yearly.append(
            RotationYearExposure(
                year=phase_records[0].outcomes[index].year,
                exposed_share=len(exposed) / rotation.length_years,
                exposed_crop_ids=tuple(dict.fromkeys(exposed)),
            )
        )

    shares = [entry.exposed_share for entry in yearly]
    worst = sorted(
        (entry for entry in yearly if entry.exposed_share > 0),
        key=lambda entry: (-entry.exposed_share, -entry.year),
    )[:WORST_YEARS_REPORTED]
    return RotationStressTest(
        rotation_id=rotation.id,
        yearly=tuple(yearly),
        mean_exposed_share=fmean(shares) if shares else 0.0,
        p80_exposed_share=percentile(shares, 0.8) if shares else 0.0,
        max_exposed_share=max(shares, default=0.0),
        years_with_exposure=sum(share > 0 for share in shares),
        worst_years=tuple(entry.year for entry in worst),
        unevaluated_hazards=_unevaluated_hazards(rotation, catalog, records),
    )
