"""What the field grew before its first cycle, as occupations.

The crop in place (with all its years if it is a perennial) and the crops the farmer gave for the
previous years. Consecutive years of the same crop become one occupation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from field_shift.algorithm.delays.occupation import Occupation, OccupationSource
from field_shift.algorithm.delays.return_delay_catalog import (
    DEFAULT_DELAY_CATALOG,
    ReturnDelayCatalog,
)

_HISTORY = OccupationSource.HISTORY


@dataclass(frozen=True)
class CropInPlace:
    """The crop growing now: its crop id and, for a perennial, its years of production."""

    crop_id: str
    production_years: int = 0


@dataclass(frozen=True)
class PastCrop:
    """What the field grew in a previous year."""

    year: int
    crop_id: str | None


def field_history(
    in_place: CropInPlace | None,
    free_year: int,
    past: Sequence[PastCrop] = (),
    catalog: ReturnDelayCatalog = DEFAULT_DELAY_CATALOG,
) -> list[Occupation]:
    """Occupations of the field before the cycle, oldest first.

    free_year  the year the crop in place is harvested (the field becomes free)
    """
    occupations: list[Occupation] = []
    in_place_first_year = free_year + 1
    if in_place is not None:
        in_place_first_year = free_year - max(in_place.production_years, 1) + 1
        occupations.append(
            Occupation(
                catalog.species_of(in_place.crop_id), in_place_first_year, free_year, _HISTORY
            )
        )
    for entry in past:
        if entry.year >= in_place_first_year or not entry.crop_id:
            continue  # that year belongs to the crop in place
        occupations.append(
            Occupation(catalog.species_of(entry.crop_id), entry.year, entry.year, _HISTORY)
        )
    occupations.sort(key=lambda o: o.first_year)
    merged: list[Occupation] = []
    for occupation in occupations:
        last = merged[-1] if merged else None
        if (
            last is not None
            and last.crop_id == occupation.crop_id
            and occupation.first_year <= last.last_year + 1
        ):
            merged[-1] = Occupation(
                occupation.crop_id,
                last.first_year,
                max(occupation.last_year, last.last_year),
                _HISTORY,
            )
        else:
            merged.append(occupation)
    return merged
