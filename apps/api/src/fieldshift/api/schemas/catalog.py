"""Contracts of the reference catalogue and of the farm profile."""

from __future__ import annotations

from datetime import date

from pydantic import Field

from fieldshift.api.schemas.common import (
    ApiModel,
    LocationIn,
    ObservationModel,
    RequestModel,
)
from fieldshift.application.reference import DemoFarm
from fieldshift.domain.agronomy.crops import (
    Basis,
    Confidence,
    Crop,
    CropCategory,
    HeatUnit,
    SeasonModel,
)
from fieldshift.domain.agronomy.farm import (
    MAX_PRIORITY_WEIGHT,
    MAX_ROTATION_YEARS,
    CropRotation,
    FarmerPriorities,
    FarmObservation,
    FarmProfile,
    RotationOrigin,
    SoilInformationSource,
    SoilTexture,
)
from fieldshift.domain.references import Reference


class BasisOut(ApiModel):
    source_ids: list[str]
    confidence: Confidence
    note_fr: str


class HeatRequirementOut(ApiModel):
    unit: HeatUnit
    minimum: float
    maximum: float
    basis: BasisOut


class FrostToleranceOut(ApiModel):
    damage_threshold_c: float
    inclusive: bool
    basis: BasisOut


class WaterNeedOut(ApiModel):
    minimum_mm: float
    maximum_mm: float
    basis: BasisOut


class CropOut(ApiModel):
    id: str
    name_fr: str
    name_en: str
    scientific_name: str
    category: CropCategory
    botanical_families: list[str]
    fixes_nitrogen: bool | None
    season_model: SeasonModel
    heat_requirement: HeatRequirementOut | None
    frost_tolerance: FrostToleranceOut | None
    water_need: WaterNeedOut | None
    context_indicator_ids: list[str]
    not_modelled_fr: list[str]


class RotationOut(ApiModel):
    id: str
    name_fr: str
    crop_ids: list[str]
    origin: RotationOrigin
    rationale_fr: str | None
    source_ids: list[str]


class ReferenceOut(ApiModel):
    id: str
    citation: str
    url: str | None
    accessed: date | None
    terms_fr: str
    used_for_fr: str


class PrioritiesModel(RequestModel):
    """Importance of each criterion, from 0 (ignore) to 3 (essential)."""

    climate_resilience: int = Field(default=1, ge=0, le=MAX_PRIORITY_WEIGHT)
    soil_health: int = Field(default=1, ge=0, le=MAX_PRIORITY_WEIGHT)
    water_conservation: int = Field(default=1, ge=0, le=MAX_PRIORITY_WEIGHT)
    potential_income: int = Field(default=1, ge=0, le=MAX_PRIORITY_WEIGHT)


class RotationIn(RequestModel):
    name_fr: str = Field(default="Rotation actuelle", min_length=1, max_length=120)
    crop_ids: list[str] = Field(min_length=1, max_length=MAX_ROTATION_YEARS)


class FarmProfileModel(RequestModel):
    """Farm described by the farmer. Unknown information stays ``null``."""

    name: str = Field(default="Ma ferme", min_length=1, max_length=120)
    location: LocationIn
    current_rotation: RotationIn
    priorities: PrioritiesModel = PrioritiesModel()
    soil_texture: SoilTexture | None = None
    soil_information_source: SoilInformationSource | None = None
    irrigation_available: bool | None = None
    excluded_crop_ids: list[str] = Field(default_factory=list, max_length=50)
    observations: list[ObservationModel] = Field(default_factory=list, max_length=30)

    def to_domain(self) -> FarmProfile:
        return FarmProfile(
            name=self.name,
            location=self.location.to_point(),
            location_precision=self.location.precision,
            current_rotation=CropRotation(
                id="current",
                name_fr=self.current_rotation.name_fr,
                crop_ids=tuple(self.current_rotation.crop_ids),
                origin=RotationOrigin.DECLARED_BY_FARMER,
            ),
            priorities=FarmerPriorities(**self.priorities.model_dump()),
            soil_texture=self.soil_texture,
            soil_information_source=self.soil_information_source,
            irrigation_available=self.irrigation_available,
            excluded_crop_ids=frozenset(self.excluded_crop_ids),
            observations=tuple(observation_to_domain(o) for o in self.observations),
        )

    @classmethod
    def from_domain(cls, profile: FarmProfile) -> FarmProfileModel:
        return cls(
            name=profile.name,
            location=LocationIn(
                latitude=profile.location.latitude,
                longitude=profile.location.longitude,
                precision=profile.location_precision,
            ),
            current_rotation=RotationIn(
                name_fr=profile.current_rotation.name_fr,
                crop_ids=list(profile.current_rotation.crop_ids),
            ),
            priorities=PrioritiesModel(**priorities_dict(profile.priorities)),
            soil_texture=profile.soil_texture,
            soil_information_source=profile.soil_information_source,
            irrigation_available=profile.irrigation_available,
            excluded_crop_ids=sorted(profile.excluded_crop_ids),
            observations=[observation_model(o) for o in profile.observations],
        )


class DemoFarmOut(ApiModel):
    id: str
    description_fr: str
    provenance_fr: str
    profile: FarmProfileModel


def priorities_dict(priorities: FarmerPriorities) -> dict[str, int]:
    return {criterion.value: weight for criterion, weight in priorities.as_weights().items()}


def observation_to_domain(observation: ObservationModel) -> FarmObservation:
    return FarmObservation(
        text=observation.text,
        topic=observation.topic,
        year=observation.year,
        crop_id=observation.crop_id,
    )


def observation_model(observation: FarmObservation) -> ObservationModel:
    return ObservationModel(
        text=observation.text,
        topic=observation.topic,
        year=observation.year,
        crop_id=observation.crop_id,
    )


def basis_out(basis: Basis) -> BasisOut:
    return BasisOut(
        source_ids=list(basis.source_ids), confidence=basis.confidence, note_fr=basis.note_fr
    )


def crop_out(crop: Crop) -> CropOut:
    heat, frost, water = crop.heat_requirement, crop.frost_tolerance, crop.water_need
    return CropOut(
        id=crop.id,
        name_fr=crop.name_fr,
        name_en=crop.name_en,
        scientific_name=crop.scientific_name,
        category=crop.category,
        botanical_families=list(crop.botanical_families),
        fixes_nitrogen=crop.fixes_nitrogen,
        season_model=crop.season_model,
        heat_requirement=(
            HeatRequirementOut(
                unit=heat.unit,
                minimum=heat.minimum,
                maximum=heat.maximum,
                basis=basis_out(heat.basis),
            )
            if heat
            else None
        ),
        frost_tolerance=(
            FrostToleranceOut(
                damage_threshold_c=frost.damage_threshold.temperature_c,
                inclusive=frost.damage_threshold.inclusive,
                basis=basis_out(frost.basis),
            )
            if frost
            else None
        ),
        water_need=(
            WaterNeedOut(
                minimum_mm=water.minimum_mm,
                maximum_mm=water.maximum_mm,
                basis=basis_out(water.basis),
            )
            if water
            else None
        ),
        context_indicator_ids=list(crop.context_indicator_ids),
        not_modelled_fr=list(crop.not_modelled_fr),
    )


def rotation_out(rotation: CropRotation) -> RotationOut:
    return RotationOut(
        id=rotation.id,
        name_fr=rotation.name_fr,
        crop_ids=list(rotation.crop_ids),
        origin=rotation.origin,
        rationale_fr=rotation.rationale_fr,
        source_ids=list(rotation.source_ids),
    )


def reference_out(reference: Reference) -> ReferenceOut:
    return ReferenceOut(
        id=reference.id,
        citation=reference.citation,
        url=reference.url,
        accessed=reference.accessed,
        terms_fr=reference.terms_fr,
        used_for_fr=reference.used_for_fr,
    )


def demo_farm_out(demo: DemoFarm) -> DemoFarmOut:
    return DemoFarmOut(
        id=demo.id,
        description_fr=demo.description_fr,
        provenance_fr=demo.provenance_fr,
        profile=FarmProfileModel.from_domain(demo.profile),
    )
