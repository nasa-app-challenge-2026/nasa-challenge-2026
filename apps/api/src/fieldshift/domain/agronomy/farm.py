"""The farm as described by the farmer, and the rotations to compare.

Everything here is declared information. Fields the farmer does not know stay ``None``; the
model never substitutes a default for an unknown.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from fieldshift.domain.geo import GeoPoint

MAX_ROTATION_YEARS = 8
MAX_PRIORITY_WEIGHT = 3


class RotationOrigin(StrEnum):
    DECLARED_BY_FARMER = "declared_by_farmer"
    TEMPLATE = "template"


@dataclass(frozen=True, slots=True)
class CropRotation:
    """A repeating cycle: one crop per year, in order."""

    id: str
    name_fr: str
    crop_ids: tuple[str, ...]
    origin: RotationOrigin
    rationale_fr: str | None = None
    source_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not 1 <= len(self.crop_ids) <= MAX_ROTATION_YEARS:
            raise ValueError(
                f"a rotation must have between 1 and {MAX_ROTATION_YEARS} years, "
                f"got {len(self.crop_ids)}"
            )

    @property
    def length_years(self) -> int:
        return len(self.crop_ids)

    def crop_shares(self) -> dict[str, float]:
        """Fraction of the cycle occupied by each crop, in order of first appearance.

        With one field per phase, this is also the fraction of the farm under each crop in
        any given year.
        """
        shares: dict[str, float] = {}
        for crop_id in self.crop_ids:
            shares[crop_id] = shares.get(crop_id, 0.0) + 1.0 / len(self.crop_ids)
        return shares


class Criterion(StrEnum):
    CLIMATE_RESILIENCE = "climate_resilience"
    SOIL_HEALTH = "soil_health"
    WATER_CONSERVATION = "water_conservation"
    POTENTIAL_INCOME = "potential_income"


@dataclass(frozen=True, slots=True)
class FarmerPriorities:
    """Importance the farmer gives to each criterion, from 0 (ignore) to 3 (essential)."""

    climate_resilience: int = 1
    soil_health: int = 1
    water_conservation: int = 1
    potential_income: int = 1

    def __post_init__(self) -> None:
        for criterion, weight in self.as_weights().items():
            if not 0 <= weight <= MAX_PRIORITY_WEIGHT:
                raise ValueError(
                    f"priority {criterion.value} must be within [0, {MAX_PRIORITY_WEIGHT}], "
                    f"got {weight}"
                )

    def as_weights(self) -> dict[Criterion, int]:
        return {
            Criterion.CLIMATE_RESILIENCE: self.climate_resilience,
            Criterion.SOIL_HEALTH: self.soil_health,
            Criterion.WATER_CONSERVATION: self.water_conservation,
            Criterion.POTENTIAL_INCOME: self.potential_income,
        }


class SoilTexture(StrEnum):
    SAND = "sand"
    SANDY_LOAM = "sandy_loam"
    LOAM = "loam"
    SILT_LOAM = "silt_loam"
    CLAY_LOAM = "clay_loam"
    CLAY = "clay"
    ORGANIC = "organic"


class SoilInformationSource(StrEnum):
    DECLARED_BY_FARMER = "declared_by_farmer"
    LABORATORY_ANALYSIS = "laboratory_analysis"


class LocationPrecision(StrEnum):
    EXACT = "exact"
    """The point is on the farm."""
    APPROXIMATE = "approximate"
    """The point stands for a wider area, for example the centre of the municipality."""


class ObservationTopic(StrEnum):
    FROST = "frost"
    HARVEST_WEATHER = "harvest_weather"
    WATER = "water"
    WEEDS = "weeds"
    MARKET = "market"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class FarmObservation:
    """Something the farmer reported. Kept verbatim, never treated as a measurement."""

    text: str
    topic: ObservationTopic = ObservationTopic.OTHER
    year: int | None = None
    crop_id: str | None = None


@dataclass(frozen=True, slots=True)
class FarmProfile:
    name: str
    location: GeoPoint
    location_precision: LocationPrecision
    current_rotation: CropRotation
    priorities: FarmerPriorities = field(default_factory=FarmerPriorities)
    soil_texture: SoilTexture | None = None
    soil_information_source: SoilInformationSource | None = None
    irrigation_available: bool | None = None
    excluded_crop_ids: frozenset[str] = frozenset()
    observations: tuple[FarmObservation, ...] = ()

    def observations_about(self, crop_id: str) -> tuple[FarmObservation, ...]:
        return tuple(obs for obs in self.observations if obs.crop_id == crop_id)
