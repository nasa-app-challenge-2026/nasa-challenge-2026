"""The "ravageurs" criterion for one rotation of the ranking (`POST /rotations/rank`).

A `Rotation` is written in months (phases); the pest pressure is followed in years. This module
turns the cycle into the crops of each year, with the same rule as the plan
(`chain_step.to_occupations`):

  - a cash crop counts for the year it is harvested (the end of its phase);
  - a perennial (alfalfa, hay) counts from the year it is sown to the year of its last harvest;
  - bare soil, tilled fallow and cover crops are not crops of the field: years without a host;
  - a crop counts as its species (double-crop soybean = soybean), as for the return delays.

The cycle must last a whole number of years to repeat year after year. When it does not (18
months), it is played as many times as it takes to make whole years (2 × 18 = 3 years).

The rotation is taken as having been in place for several cycles before (no history, no declared
disease: the ranking request gives neither). The length of the simulation does not change the
result: the criterion measures the pressure of the rotation once it repeats.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from field_shift.algorithm.delays.occupation import Occupation
from field_shift.algorithm.delays.return_delay_catalog import (
    DEFAULT_DELAY_CATALOG,
    ReturnDelayCatalog,
)
from field_shift.algorithm.delays.return_delay_checker import ReturnDelayChecker
from field_shift.algorithm.pests.pest_catalog import DEFAULT_PEST_CATALOG, PestCatalog
from field_shift.algorithm.pests.pest_criterion import PestCriterion
from field_shift.algorithm.pests.pest_result import PestResult
from field_shift.algorithm.rotation.rotation import MONTH_TOLERANCE, Rotation, RotationPhase
from field_shift.reference.crops import crop_name
from field_shift.reference.planning import MONTHS_PER_YEAR
from field_shift.reference.soil_protection import CoverKind

#: Most cycles played to reach a whole number of years (12 is enough for any whole month count).
MAX_CYCLES_FOR_WHOLE_YEARS: Final = 12


@dataclass(frozen=True)
class PestMeasureOutcome:
    """The pests of one rotation.

    result              the criterion; None when the rotation has no crop of the field, or no
                        crop the catalogue knows (a score of 1 would mean "unknown", not "safe")
    crops_without_data  crops of the rotation for which the catalogue knows no organism
    reason              why there is no result (empty when there is one)
    """

    result: PestResult | None
    crops_without_data: tuple[str, ...] = ()
    reason: str = ""


def _is_crop_of_the_field(phase: RotationPhase) -> bool:
    """False for bare soil, tilled fallow and cover crops (see the module documentation)."""
    if phase.crop_id is None or phase.profile is None:
        return False
    return phase.profile.kind not in (CoverKind.FALLOW, CoverKind.COVER)


def cycles_for_whole_years(cycle_months: float) -> int | None:
    """How many cycles make a whole number of years; None beyond MAX_CYCLES_FOR_WHOLE_YEARS."""
    for cycles in range(1, MAX_CYCLES_FOR_WHOLE_YEARS + 1):
        years = cycles * cycle_months / MONTHS_PER_YEAR
        if abs(years - round(years)) * MONTHS_PER_YEAR <= MONTH_TOLERANCE:
            return cycles
    return None


def rotation_occupations(
    rotation: Rotation, cycles: int, delay_catalog: ReturnDelayCatalog = DEFAULT_DELAY_CATALOG
) -> list[Occupation]:
    """The crops of the field, year by year, over `cycles` cycles of the rotation."""
    occupations: list[Occupation] = []
    start_month = 0.0
    for _ in range(cycles):
        for phase in rotation.phases:
            end_month = start_month + phase.months
            if _is_crop_of_the_field(phase):
                harvest_year = int((end_month - MONTH_TOLERANCE) // MONTHS_PER_YEAR)
                first_year = (
                    int((start_month + MONTH_TOLERANCE) // MONTHS_PER_YEAR)
                    if phase.profile.kind is CoverKind.PERENNIAL
                    else harvest_year
                )
                species = delay_catalog.species_of(phase.crop_id)
                occupations.append(Occupation(species, first_year, harvest_year))
            start_month = end_month
    return occupations


def evaluate_pests(
    rotation: Rotation, pest_catalog: PestCatalog = DEFAULT_PEST_CATALOG
) -> PestMeasureOutcome:
    """The "ravageurs" criterion of a rotation that repeats (see the module documentation)."""
    cycles = cycles_for_whole_years(rotation.cycle_months)
    if cycles is None:
        return PestMeasureOutcome(
            None, reason="le cycle ne fait pas un nombre entier d’années, même répété"
        )
    occupations = rotation_occupations(rotation, cycles)
    if not occupations:
        return PestMeasureOutcome(
            None, reason="la rotation n’a pas de culture récoltée (seulement couverts ou sol nu)"
        )
    cycle_years = round(cycles * rotation.cycle_months / MONTHS_PER_YEAR)
    checker = ReturnDelayChecker(cycle_years)
    result = PestCriterion(checker, pest_catalog).evaluate(occupations, closed=True, explain=True)
    without_data = tuple(
        dict.fromkeys(o.crop_id for o in occupations if not pest_catalog.pests_of(o.crop_id))
    )
    if result is None or not result.confidence:
        names = ", ".join(crop_name(crop_id) for crop_id in without_data)
        return PestMeasureOutcome(
            None, without_data, reason=f"aucune donnée de ravageurs pour : {names}"
        )
    return PestMeasureOutcome(result, crops_without_data=without_data)


def pest_note(outcome: PestMeasureOutcome) -> str:
    """The note of the measure: crops without data, then the sentences for the farmer."""
    parts: list[str] = []
    if outcome.crops_without_data:
        names = ", ".join(crop_name(crop_id) for crop_id in outcome.crops_without_data)
        parts.append(f"Aucune donnée de ravageurs pour : {names} (comptées sans risque).")
    if outcome.result is not None:
        parts.extend(outcome.result.explanations)
    return " ".join(parts)
