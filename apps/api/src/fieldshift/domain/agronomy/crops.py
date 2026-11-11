"""Crops and the documented climatic requirements used to stress-test them.

A requirement only exists in this model when a source states it. A crop without a documented
requirement keeps ``None``: the corresponding rule is reported as "not evaluated" instead of
being filled with a plausible-looking number.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import StrEnum

from fieldshift.domain.climate.seasons import FrostThreshold


class CropCategory(StrEnum):
    ANNUAL = "annual"
    """Sown and harvested within one growing season."""
    PERENNIAL_FORAGE = "perennial_forage"
    """A stand kept for several years inside a rotation (hay, pasture)."""
    PERENNIAL_WOODY = "perennial_woody"
    """Orchard, sugar bush, Christmas trees... a land-use decision over decades, never a
    phase of a rotation."""


class SeasonModel(StrEnum):
    """Which part of the year the crop grows in, hence how its heat is counted."""

    COOL_SEASON = "cool_season"
    """From the start of the thermal growing season; heat counted in degree-days base 0 °C."""
    WARM_SEASON = "warm_season"
    """Over the crop heat unit season; heat counted in crop heat units (UTM)."""
    PERENNIAL = "perennial"
    """Over the whole thermal growing season; no maturity date."""


class Confidence(StrEnum):
    DOCUMENTED = "documented"
    """The value was read in the cited source."""
    PROVISIONAL = "provisional"
    """A working assumption of the team, to be validated before any decision relies on it."""


@dataclass(frozen=True, slots=True)
class Basis:
    """Why a threshold has the value it has."""

    source_ids: tuple[str, ...]
    confidence: Confidence
    note_fr: str

    def __post_init__(self) -> None:
        if self.confidence is Confidence.DOCUMENTED and not self.source_ids:
            raise ValueError("a documented value must cite at least one source")


class HeatUnit(StrEnum):
    GDD_BASE_0 = "gdd_base0"
    CROP_HEAT_UNITS = "crop_heat_units"


@dataclass(frozen=True, slots=True)
class HeatRequirement:
    """Heat needed from sowing to maturity, as a documented range."""

    unit: HeatUnit
    minimum: float
    maximum: float
    basis: Basis

    def __post_init__(self) -> None:
        if not 0 < self.minimum <= self.maximum:
            raise ValueError("heat requirement must satisfy 0 < minimum <= maximum")


@dataclass(frozen=True, slots=True)
class FrostTolerance:
    """Daily minimum temperature from which damage is documented during growth."""

    damage_threshold: FrostThreshold
    basis: Basis


@dataclass(frozen=True, slots=True)
class WaterNeed:
    """Indicative seasonal crop water need over the whole growing period (mm)."""

    minimum_mm: float
    maximum_mm: float
    basis: Basis

    def __post_init__(self) -> None:
        if not 0 < self.minimum_mm <= self.maximum_mm:
            raise ValueError("water need must satisfy 0 < minimum <= maximum")

    @property
    def midpoint_mm(self) -> float:
        return (self.minimum_mm + self.maximum_mm) / 2.0


@dataclass(frozen=True, slots=True)
class Crop:
    id: str
    name_fr: str
    name_en: str
    scientific_name: str
    category: CropCategory
    botanical_families: tuple[str, ...]
    fixes_nitrogen: bool | None
    """``None`` when the composition is unknown (for example hay of unspecified species)."""
    season_model: SeasonModel
    heat_requirement: HeatRequirement | None
    frost_tolerance: FrostTolerance | None
    water_need: WaterNeed | None
    context_indicator_ids: tuple[str, ...]
    """Climate indicators worth reading next to this crop, shown without any pass/fail."""
    not_modelled_fr: tuple[str, ...]
    """Known influences on this crop that the stress test does not represent."""

    def __post_init__(self) -> None:
        if not self.botanical_families:
            raise ValueError(f"crop {self.id!r} must declare at least one botanical family")
        if self.category is CropCategory.PERENNIAL_FORAGE and (
            self.season_model is not SeasonModel.PERENNIAL
        ):
            raise ValueError(f"perennial forage {self.id!r} must use the perennial season model")
        if self.heat_requirement is not None:
            expected = {
                SeasonModel.COOL_SEASON: HeatUnit.GDD_BASE_0,
                SeasonModel.WARM_SEASON: HeatUnit.CROP_HEAT_UNITS,
            }.get(self.season_model)
            if self.heat_requirement.unit is not expected:
                raise ValueError(
                    f"crop {self.id!r}: heat unit {self.heat_requirement.unit} does not match "
                    f"season model {self.season_model}"
                )

    @property
    def is_annual(self) -> bool:
        return self.category is CropCategory.ANNUAL

    @property
    def uses_provisional_values(self) -> bool:
        bases = [
            rule.basis
            for rule in (self.heat_requirement, self.frost_tolerance, self.water_need)
            if rule is not None
        ]
        return any(basis.confidence is Confidence.PROVISIONAL for basis in bases)


class UnknownCropError(LookupError):
    def __init__(self, crop_id: str) -> None:
        super().__init__(f"unknown crop: {crop_id!r}")
        self.crop_id = crop_id


class CropCatalog:
    """The crops the application knows about, by identifier."""

    def __init__(self, crops: Iterable[Crop]) -> None:
        self._crops: dict[str, Crop] = {}
        for crop in crops:
            if crop.id in self._crops:
                raise ValueError(f"duplicate crop id: {crop.id!r}")
            self._crops[crop.id] = crop

    def __iter__(self) -> Iterator[Crop]:
        return iter(self._crops.values())

    def __len__(self) -> int:
        return len(self._crops)

    def __contains__(self, crop_id: object) -> bool:
        return crop_id in self._crops

    def get(self, crop_id: str) -> Crop:
        try:
            return self._crops[crop_id]
        except KeyError:
            raise UnknownCropError(crop_id) from None
