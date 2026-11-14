"""A sold crop on the field, from one year to another (both included)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum


class OccupationSource(StrEnum):
    """Where an occupation comes from (shown in the alerts)."""

    CHAIN = "chaîne"
    HISTORY = "historique"
    NEXT_CYCLE = "cycle suivant"
    PREVIOUS_CYCLE = "cycle précédent"


@dataclass(frozen=True)
class Occupation:
    """A crop on the field from `first_year` to `last_year`: one year for an annual crop, its
    production years for a perennial."""

    crop_id: str
    first_year: int
    last_year: int
    source: OccupationSource = OccupationSource.CHAIN

    def shifted_by(self, years: int, source: OccupationSource) -> Occupation:
        return Occupation(self.crop_id, self.first_year + years, self.last_year + years, source)

    def with_source(self, source: OccupationSource) -> Occupation:
        return replace(self, source=source)


def years_between(before: Occupation, after: Occupation) -> int:
    """Years without crop between two occupations (two harvests the same year = −1)."""
    return after.first_year - before.last_year - 1
