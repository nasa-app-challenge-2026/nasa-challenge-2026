"""Step 5: in the twin cells, keep only the fields whose soil looks like the field's.

SoilGrids 2.0 (250 m), mean over 0–30 cm of 4 properties: clay, sand, organic carbon, pH. A soil
test of the farmer replaces SoilGrids for his field. Each difference is divided by a tolerance
(organic carbon compared in logarithm), then the root mean square of the 4 differences: 1 or less
= equivalent soil. With fewer than 200 fields left, the tolerances are widened by 25 % (and the
app says so).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, TypeVar

from field_shift.algorithm.config.twins import (
    MIN_FIELDS_AFTER_SOIL_FILTER,
    SAME_SOIL_MAX_DISTANCE,
    SOIL_TOLERANCE_WIDENING,
    SOIL_TOLERANCES,
    SoilTolerances,
)


@dataclass(frozen=True)
class Soil:
    """Soil of a field over 0–30 cm. `organic_carbon` is in g/kg."""

    clay_pct: float
    sand_pct: float
    organic_carbon: float
    ph: float


class HasSoil(Protocol):
    soil: Soil


FieldT = TypeVar("FieldT", bound=HasSoil)


def soil_distance(a: Soil, b: Soil, tolerances: SoilTolerances = SOIL_TOLERANCES) -> float:
    """Distance between two soils (1 or less = same soil)."""
    gaps = (
        (a.clay_pct - b.clay_pct) / tolerances.clay_pct,
        (a.sand_pct - b.sand_pct) / tolerances.sand_pct,
        math.log(a.organic_carbon / b.organic_carbon) / math.log(tolerances.organic_carbon_ratio),
        (a.ph - b.ph) / tolerances.ph,
    )
    return math.sqrt(sum(gap * gap for gap in gaps) / len(gaps))


@dataclass(frozen=True)
class SoilFilterResult:
    fields: list
    widened: bool


class SoilFilter:
    """Keeps the fields of the twins whose soil is comparable to the farmer's."""

    def __init__(self, field_soil: Soil, min_fields: int = MIN_FIELDS_AFTER_SOIL_FILTER) -> None:
        self._field_soil = field_soil
        self._min_fields = min_fields

    def keep_comparable(self, fields: Sequence[FieldT]) -> SoilFilterResult:
        strict = self._keep(fields, SOIL_TOLERANCES)
        if len(strict) >= self._min_fields:
            return SoilFilterResult(strict, widened=False)
        widened = SOIL_TOLERANCES.widened(SOIL_TOLERANCE_WIDENING)
        return SoilFilterResult(self._keep(fields, widened), widened=True)

    def _keep(self, fields: Sequence[FieldT], tolerances: SoilTolerances) -> list[FieldT]:
        return [
            f
            for f in fields
            if soil_distance(self._field_soil, f.soil, tolerances) <= SAME_SOIL_MAX_DISTANCE
        ]
