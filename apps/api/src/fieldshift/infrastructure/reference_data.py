"""Load the versioned reference data in ``data/reference/*.yaml``.

The files are validated strictly (unknown keys are errors) and cross-checked: every cited
source must exist, every crop of a rotation must be in the catalogue, every indicator named
by a crop must exist. Problems are reported all at once, at start-up.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from fieldshift.application.reference import DemoFarm, ReferenceData
from fieldshift.domain.agronomy.crops import (
    Basis,
    Confidence,
    Crop,
    CropCatalog,
    CropCategory,
    FrostTolerance,
    HeatRequirement,
    HeatUnit,
    SeasonModel,
    WaterNeed,
)
from fieldshift.domain.agronomy.farm import (
    CropRotation,
    FarmerPriorities,
    FarmObservation,
    FarmProfile,
    LocationPrecision,
    ObservationTopic,
    RotationOrigin,
    SoilInformationSource,
    SoilTexture,
)
from fieldshift.domain.agronomy.validation import InvalidRotationError, validate_rotation
from fieldshift.domain.climate.indicators import INDICATORS, INDICATORS_BY_ID
from fieldshift.domain.climate.seasons import FrostThreshold
from fieldshift.domain.geo import GeoPoint
from fieldshift.domain.references import Reference
from fieldshift.domain.simulation import explanations


class ReferenceDataError(ValueError):
    """The reference files are invalid. The message lists every problem found."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _Basis(_Strict):
    source_ids: list[str]
    confidence: Confidence
    note_fr: str

    def to_domain(self) -> Basis:
        return Basis(tuple(self.source_ids), self.confidence, self.note_fr)


class _Heat(_Strict):
    unit: HeatUnit
    minimum: float
    maximum: float
    basis: _Basis


class _Frost(_Strict):
    damage_threshold_c: float
    inclusive: bool
    basis: _Basis


class _Water(_Strict):
    minimum_mm: float
    maximum_mm: float
    basis: _Basis


class _Crop(_Strict):
    id: str
    name_fr: str
    name_en: str
    scientific_name: str
    category: CropCategory
    botanical_families: list[str]
    fixes_nitrogen: bool | None
    season_model: SeasonModel
    heat_requirement: _Heat | None = None
    frost_tolerance: _Frost | None = None
    water_need: _Water | None = None
    context_indicator_ids: list[str] = Field(default_factory=list)
    not_modelled_fr: list[str] = Field(default_factory=list)

    def to_domain(self) -> Crop:
        heat = self.heat_requirement
        frost = self.frost_tolerance
        water = self.water_need
        return Crop(
            id=self.id,
            name_fr=self.name_fr,
            name_en=self.name_en,
            scientific_name=self.scientific_name,
            category=self.category,
            botanical_families=tuple(self.botanical_families),
            fixes_nitrogen=self.fixes_nitrogen,
            season_model=self.season_model,
            heat_requirement=(
                HeatRequirement(heat.unit, heat.minimum, heat.maximum, heat.basis.to_domain())
                if heat
                else None
            ),
            frost_tolerance=(
                FrostTolerance(
                    FrostThreshold(frost.damage_threshold_c, frost.inclusive),
                    frost.basis.to_domain(),
                )
                if frost
                else None
            ),
            water_need=(
                WaterNeed(water.minimum_mm, water.maximum_mm, water.basis.to_domain())
                if water
                else None
            ),
            context_indicator_ids=tuple(self.context_indicator_ids),
            not_modelled_fr=tuple(self.not_modelled_fr),
        )


class _Template(_Strict):
    id: str
    name_fr: str
    crop_ids: list[str]
    rationale_fr: str
    source_ids: list[str] = Field(default_factory=list)

    def to_domain(self) -> CropRotation:
        return CropRotation(
            id=self.id,
            name_fr=self.name_fr,
            crop_ids=tuple(self.crop_ids),
            origin=RotationOrigin.TEMPLATE,
            rationale_fr=self.rationale_fr,
            source_ids=tuple(self.source_ids),
        )


class _Source(_Strict):
    id: str
    citation: str
    url: str | None = None
    accessed: date | None = None
    terms_fr: str
    used_for_fr: str


class _Observation(_Strict):
    text: str
    topic: ObservationTopic = ObservationTopic.OTHER
    year: int | None = None
    crop_id: str | None = None


class _Rotation(_Strict):
    name_fr: str
    crop_ids: list[str]


class _Priorities(_Strict):
    climate_resilience: int = 1
    soil_health: int = 1
    water_conservation: int = 1
    potential_income: int = 1


class _Profile(_Strict):
    name: str
    latitude: float
    longitude: float
    location_precision: LocationPrecision
    current_rotation: _Rotation
    priorities: _Priorities = _Priorities()
    soil_texture: SoilTexture | None = None
    soil_information_source: SoilInformationSource | None = None
    irrigation_available: bool | None = None
    excluded_crop_ids: list[str] = Field(default_factory=list)
    observations: list[_Observation] = Field(default_factory=list)


class _DemoFarm(_Strict):
    id: str
    description_fr: str
    provenance_fr: str
    profile: _Profile

    def to_domain(self) -> DemoFarm:
        p = self.profile
        return DemoFarm(
            id=self.id,
            description_fr=self.description_fr,
            provenance_fr=self.provenance_fr,
            profile=FarmProfile(
                name=p.name,
                location=GeoPoint(p.latitude, p.longitude),
                location_precision=p.location_precision,
                current_rotation=CropRotation(
                    id="current",
                    name_fr=p.current_rotation.name_fr,
                    crop_ids=tuple(p.current_rotation.crop_ids),
                    origin=RotationOrigin.DECLARED_BY_FARMER,
                ),
                priorities=FarmerPriorities(**p.priorities.model_dump()),
                soil_texture=p.soil_texture,
                soil_information_source=p.soil_information_source,
                irrigation_available=p.irrigation_available,
                excluded_crop_ids=frozenset(p.excluded_crop_ids),
                observations=tuple(
                    FarmObservation(o.text, o.topic, o.year, o.crop_id) for o in p.observations
                ),
            ),
        )


class _SourcesFile(_Strict):
    sources: list[_Source]


class _CropsFile(_Strict):
    crops: list[_Crop]


class _TemplatesFile(_Strict):
    templates: list[_Template]


class _DemoFarmsFile(_Strict):
    demo_farms: list[_DemoFarm]


def _read(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ReferenceDataError(f"{path.name}: cannot be read ({error})") from error


def _validate[T: BaseModel](model: type[T], path: Path) -> T:
    try:
        return model.model_validate(_read(path))
    except ValidationError as error:
        raise ReferenceDataError(f"{path.name}: {error}") from error


def _duplicates(ids: list[str]) -> set[str]:
    return {item for item in ids if ids.count(item) > 1}


def cited_source_ids(crops: list[Crop], templates: list[CropRotation]) -> set[str]:
    """Every source identifier the code and the reference files rely on."""
    cited = {source for indicator in INDICATORS for source in indicator.source_ids}
    cited |= {
        explanations.SOURCE_FORAGES,
        explanations.SOURCE_DIVERSITY,
        explanations.SOURCE_WATER,
        explanations.SOURCE_HAY,
    }
    for crop in crops:
        for rule in (crop.heat_requirement, crop.frost_tolerance, crop.water_need):
            if rule is not None:
                cited |= set(rule.basis.source_ids)
    for template in templates:
        cited |= set(template.source_ids)
    return cited


def load_reference_data(directory: Path) -> ReferenceData:
    sources_file = _validate(_SourcesFile, directory / "sources.yaml")
    crops_file = _validate(_CropsFile, directory / "crops.yaml")
    templates_file = _validate(_TemplatesFile, directory / "rotation_templates.yaml")
    demos_file = _validate(_DemoFarmsFile, directory / "demo_farms.yaml")

    problems: list[str] = []
    for label, ids in (
        ("source", [s.id for s in sources_file.sources]),
        ("crop", [c.id for c in crops_file.crops]),
        ("template", [t.id for t in templates_file.templates]),
        ("demo farm", [d.id for d in demos_file.demo_farms]),
    ):
        problems.extend(f"duplicate {label} id: {item}" for item in sorted(_duplicates(ids)))

    try:
        crops = [crop.to_domain() for crop in crops_file.crops]
        templates = [template.to_domain() for template in templates_file.templates]
        demos = [demo.to_domain() for demo in demos_file.demo_farms]
    except ValueError as error:
        raise ReferenceDataError(f"invalid reference value: {error}") from error
    if problems:
        raise ReferenceDataError("; ".join(problems))

    catalog = CropCatalog(crops)
    source_ids = {source.id for source in sources_file.sources}
    problems.extend(
        f"unknown source id: {missing}"
        for missing in sorted(cited_source_ids(crops, templates) - source_ids)
    )
    for crop in crops:
        problems.extend(
            f"crop {crop.id}: unknown indicator {indicator}"
            for indicator in crop.context_indicator_ids
            if indicator not in INDICATORS_BY_ID
        )
    for rotation in [*templates, *(demo.profile.current_rotation for demo in demos)]:
        try:
            validate_rotation(rotation, catalog)
        except InvalidRotationError as error:
            problems.append(str(error))
    if problems:
        raise ReferenceDataError("; ".join(problems))

    return ReferenceData(
        catalog=catalog,
        rotation_templates=tuple(templates),
        references=tuple(
            Reference(s.id, s.citation, s.url, s.accessed, s.terms_fr, s.used_for_fr)
            for s in sources_file.sources
        ),
        demo_farms=tuple(demos),
    )
