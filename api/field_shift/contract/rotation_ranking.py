"""Wire format of the rotation ranking: `RankingInput` → `RotationRanking`.

What the client sends (`POST /rotations/rank`):
  - the sections of the field, each with its outline (a GeoJSON polygon) and what is known of its
    soil, relief and practices; what is not given is read from the data services;
  - the duration of the simulation;
  - the priorities: the weight of each of the four measures in the score;
  - the rotations to compare — or a selection of crops and a cycle length, from which the server
    builds every possible rotation.

What it gets back: for each section, the rotations ranked from the best to the worst, each with
its score on 100 and the result of the four measures (`rendement`, `eau`, `protection_sol`,
`ravageurs`). Only `protection_sol` is computed today: the others say `available: false` and are
left out of the score.

Like the rest of the contract, the fields are camelCase on the wire and invalid input is refused
with a 422 that says which field is wrong.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AfterValidator, Field, model_validator

from field_shift.algorithm.soil_protection.site_conditions import SITE_VARIABLES
from field_shift.algorithm.terrain.section_shape import MAX_VERTICES, SectionShape
from field_shift.contract.base import CamelModel
from field_shift.contract.farm_input import MAX_SECTION_ID_LENGTH, CropId
from field_shift.reference.measures import MEASURE_IDS
from field_shift.reference.planning import MAX_CYCLE_YEARS

#: Longest simulation accepted, in years.
MAX_SIMULATION_YEARS = 100
#: Longest phase of a rotation, in months (a perennial kept ten years).
MAX_PHASE_MONTHS = 120
#: Most rotations compared in one request (written by the user or generated from the crops).
MAX_ROTATIONS = 200
#: Most sections in one request.
MAX_SECTIONS = 50


def _known_measure(value: str) -> str:
    if value not in MEASURE_IDS:
        raise ValueError(f"mesure inconnue : {value} (mesures : {', '.join(MEASURE_IDS)})")
    return value


MeasureId = Annotated[str, AfterValidator(_known_measure)]


def _site_field(key: str, required: bool = False):
    """A field of `SiteInput` bounded to the valid range of its site variable (optional unless
    `required`: what is not given is read from the data services)."""
    variable = SITE_VARIABLES[key]
    unit = f" ({variable.unit})" if variable.unit else ""
    extra = {} if required else {"default": None}
    return Field(
        ge=variable.minimum, le=variable.maximum, description=variable.label + unit, **extra
    )


# --- Input ----------------------------------------------------------------------------------------


class PhaseInput(CamelModel):
    """One step of a rotation: a crop (or bare soil) and how long it holds the field."""

    crop: CropId | None = Field(
        description="Crop id or crop sheet id (see GET /crops); null for bare soil."
    )
    months: float | None = Field(
        default=None,
        gt=0,
        le=MAX_PHASE_MONTHS,
        description=(
            "Duration in months. Without it, the crop takes its usual season and the soil is "
            "bare until the end of the year. Required for bare soil."
        ),
    )

    @model_validator(mode="after")
    def bare_soil_has_a_duration(self) -> PhaseInput:
        if self.crop is None and self.months is None:
            raise ValueError("une phase de sol nu doit donner sa durée (months)")
        return self


class RotationInput(CamelModel):
    """A candidate rotation: its phases in order; the cycle repeats during the simulation.

    A phase is written as a crop id alone ("mais": one crop a year) or as an object
    ({"crop": "seigle", "months": 8}).
    """

    id: str | None = Field(default=None, min_length=1, description='"R1", "R2"… when absent.')
    name: str | None = Field(default=None, description="The crops joined by arrows when absent.")
    phases: list[CropId | PhaseInput] = Field(min_length=1)

    @model_validator(mode="after")
    def has_a_crop(self) -> RotationInput:
        crops = [p if isinstance(p, str) else p.crop for p in self.phases]
        if all(crop is None for crop in crops):
            raise ValueError("une rotation doit contenir au moins une culture")
        return self


class SiteInput(CamelModel):
    """What is known of the soil, the relief, the climate and the practices of a section.

    `supportPracticeFactor` (RUSLE P: 1 without contouring, strips or terraces) is required: no
    data service knows the practices of a farm. Every other field is optional: what is absent is
    read from the data services (SoilGrids, Copernicus DEM, NASA POWER, MODIS) or computed by a
    published model (Ksat, K, R). There is no default value: a service that fails gives a 502.
    """

    slope_pct: float | None = _site_field("slope_pct")
    slope_length_m: float | None = _site_field("slope_length_m")
    sand_pct: float | None = _site_field("sand_pct")
    clay_pct: float | None = _site_field("clay_pct")
    organic_matter_pct: float | None = _site_field("organic_matter_pct")
    ksat_mm_h: float | None = _site_field("ksat_mm_h")
    k_factor: float | None = _site_field("k_factor")
    support_practice_factor: float = _site_field("support_practice_factor", required=True)
    ndvi: float | None = _site_field("ndvi")
    root_activity: float | None = _site_field("root_activity")
    annual_rain_mm: float | None = _site_field("annual_rain_mm")
    r_factor: float | None = _site_field("r_factor")
    storm_intensity_mm_h: float | None = _site_field("storm_intensity_mm_h")
    soil_saturation: float | None = _site_field("soil_saturation")

    @model_validator(mode="after")
    def texture_adds_up(self) -> SiteInput:
        if (self.sand_pct or 0) + (self.clay_pct or 0) > 100:
            raise ValueError("sable + argile ne peut pas dépasser 100 %")
        return self


Position = Annotated[list[float], Field(min_length=2, max_length=3)]
Ring = Annotated[list[Position], Field(min_length=4, max_length=MAX_VERTICES + 1)]


class PolygonInput(CamelModel):
    """The outline of a section: a GeoJSON Polygon (RFC 7946) with one ring of [lon, lat]
    positions (WGS84), closed (the last position repeats the first), without holes."""

    type: Literal["Polygon"]
    coordinates: list[Ring] = Field(
        min_length=1, max_length=1, description="One ring: holes are not supported."
    )

    @model_validator(mode="after")
    def is_a_usable_outline(self) -> PolygonInput:
        SectionShape.from_coordinates(self.coordinates[0])  # ShapeError is a ValueError: 422
        return self

    @property
    def shape(self) -> SectionShape:
        return SectionShape.from_coordinates(self.coordinates[0])


class RankingSectionInput(CamelModel):
    """One section of the field: its outline, and what is known of it."""

    id: str = Field(min_length=1, max_length=MAX_SECTION_ID_LENGTH)
    geometry: PolygonInput = Field(
        description="Outline of the section. Its area, centre, slope and slope length are "
        "computed from it; the soil, rain and satellite measures are read at its centre."
    )
    irrigated: bool = False
    site: SiteInput


class RankingInput(CamelModel):
    """The request of `POST /rotations/rank` and of the `POST /measures/…` routes."""

    simulation_years: float = Field(
        gt=0, le=MAX_SIMULATION_YEARS, description="Total duration of the simulation, in years."
    )
    priorities: dict[MeasureId, float] | list[MeasureId] | None = Field(
        default=None,
        description=(
            "Weights of the measures ({measure: weight}, only the proportions matter) or their "
            "ranking, most important first. Equal weights when absent."
        ),
    )
    rotations: list[RotationInput] = Field(
        default_factory=list, max_length=MAX_ROTATIONS, description="The rotations to compare."
    )
    crops: list[CropId] = Field(
        default_factory=list,
        description="Selected crops, used with cycleYears when no rotation is given.",
    )
    cycle_years: int | None = Field(
        default=None,
        ge=1,
        le=MAX_CYCLE_YEARS,
        description="Length of the rotations generated from the crops (one crop a year).",
    )
    sections: list[RankingSectionInput] = Field(min_length=1, max_length=MAX_SECTIONS)

    @model_validator(mode="after")
    def check_request(self) -> RankingInput:
        if not self.rotations and not (self.crops and self.cycle_years):
            raise ValueError(
                "donnez des rotations à comparer (rotations), ou une sélection de cultures et "
                "une durée de cycle (crops et cycleYears)"
            )
        section_ids = [section.id for section in self.sections]
        if len(set(section_ids)) != len(section_ids):
            raise ValueError("deux sections ont le même id")
        rotation_ids = [rotation.id for rotation in self.rotations if rotation.id]
        if len(set(rotation_ids)) != len(rotation_ids):
            raise ValueError("deux rotations ont le même id")
        if isinstance(self.priorities, dict):
            if any(weight < 0 for weight in self.priorities.values()):
                raise ValueError("un poids ne peut pas être négatif")
            if self.priorities and sum(self.priorities.values()) <= 0:
                raise ValueError("au moins une mesure doit avoir un poids supérieur à zéro")
        elif self.priorities and len(set(self.priorities)) != len(self.priorities):
            raise ValueError("une mesure ne peut être classée qu’une fois")
        return self


# --- Output ---------------------------------------------------------------------------------------


class PhaseOut(CamelModel):
    """A phase of the cycle of a rotation."""

    crop: str | None = Field(description="Crop id; null for bare soil.")
    name: str
    months: float


class MeasureOut(CamelModel):
    """The result of one measure for a rotation on a section."""

    id: str
    name: str
    available: bool = Field(description="False while the logic of the measure is not written.")
    score: float | None = Field(description="From 0 (worst) to 100 (best); null if unavailable.")
    value: float | None = Field(description="Main value of the measure, in `unit`.")
    unit: str | None
    weight: float = Field(description="Weight the measure really had in the score (0 to 1).")
    note: str = ""


class RusleFactorsOut(CamelModel):
    """The factors of A = R × K × LS × C × P (SI units)."""

    r: float = Field(description="Rain erosivity, MJ·mm/(ha·h·year).")
    k: float = Field(description="Soil erodibility, t·ha·h/(ha·MJ·mm).")
    ls: float = Field(description="Slope length and steepness.")
    c: float = Field(description="Cover and management: what the rotation changes (0 to 1).")
    p: float = Field(description="Support practices.")


class ErosionOut(CamelModel):
    soil_loss_t_ha_year: float = Field(description="Mean soil loss under the rotation.")
    bare_soil_loss_t_ha_year: float = Field(description="The same field kept bare and tilled.")
    cumulative_soil_loss_t_ha: float = Field(description="Soil lost over the whole simulation.")
    tolerance_t_ha_year: float = Field(description="Soil loss tolerance T.")
    tolerance_ratio: float = Field(description="Soil loss / T: above 1, the soil degrades.")
    factors: RusleFactorsOut
    score: float = Field(description="0 to 100.")


class InfiltrationOut(CamelModel):
    baseline_mm_h: float = Field(description="Ksat of the soil.")
    rotation_gain_pct: float = Field(description="Change due to the rotation, in percent.")
    potential_mm_h: float = Field(description="Infiltration rate under the rotation, dry soil.")
    effective_mm_h: float = Field(description="The same with the soil moisture of the place.")
    storm_intensity_mm_h: float = Field(description="The storm the infiltration is compared to.")
    infiltrated_share_pct: float = Field(description="Share of the storm entering the soil.")
    score: float = Field(description="0 to 100.")


class CropProtectionOut(CamelModel):
    """A line of the RPI table: one crop (or bare soil) over the whole simulation."""

    crop: str | None
    name: str
    months: float = Field(description="Months in place during the simulation.")
    share_pct: float = Field(description="Share of the simulation time.")
    score: float = Field(description="SC: mean of the three scores of the crop (1 to 5).")
    adjusted_score: float = Field(description="SC adjusted to the measured vigour.")
    weighted_score: float = Field(description="WSC: its part of the RPI.")


class SoilProtectionOut(CamelModel):
    """Detail of the soil protection measure."""

    rpi: float = Field(description="Rotation Protection Index, theoretical (1 to 5).")
    adjusted_rpi: float = Field(description="RPI adjusted to the vigour seen by satellite.")
    protection_class: str = Field(description="risque-eleve, moderee or excellente.")
    protection_label: str
    erosion: ErosionOut
    infiltration: InfiltrationOut
    crops: list[CropProtectionOut]


class RankedRotationOut(CamelModel):
    """A rotation with its rank on a section."""

    rank: int = Field(description="1 for the best rotation of the section.")
    rotation_id: str
    name: str
    cycle_years: float
    phases: list[PhaseOut]
    score: float | None = Field(
        description="Weighted sum of the available measures, on 100; null if nothing to rank on."
    )
    measures: dict[str, MeasureOut]
    soil_protection: SoilProtectionOut | None = None


class SiteValueOut(CamelModel):
    """One of the conditions of a section the model ran with, and where it came from."""

    key: str
    label: str
    value: float
    unit: str
    origin: str = Field(
        description='"section", the dataset it was read from, or the model that computed it '
        '("calcul : …").'
    )
    method: str = Field(
        default="", description="How it was computed, when it is not a value read as is."
    )


class PointOut(CamelModel):
    lat: float
    lon: float


class SectionRankingOut(CamelModel):
    id: str
    area_ha: float = Field(description="Area of the outline.")
    centroid: PointOut = Field(description="Where the soil, rain and satellite data are read.")
    site: list[SiteValueOut]
    notes: list[str] = Field(
        default_factory=list,
        description=(
            "Every value that is not a value given in the request or read as is from a data "
            "service: conversions, statistics and published models, with their inputs."
        ),
    )
    rotations: list[RankedRotationOut] = Field(description="Best rotation first.")


class RankingMetaOut(CamelModel):
    simulation_years: float
    weights: dict[str, float] = Field(description="Weights asked for the measures (sum 1).")
    implemented_measures: list[str]
    pending_measures: list[str] = Field(description="Measures whose logic is not written yet.")
    rotation_count: int
    rotations_generated: bool = Field(description="True when built from crops and cycleYears.")
    notes: list[str]


class RotationRanking(CamelModel):
    """The answer of `POST /rotations/rank`."""

    meta: RankingMetaOut
    sections: list[SectionRankingOut]


class CropOut(CamelModel):
    """A crop a rotation can contain, with its soil protection sheet (`GET /crops`)."""

    id: str
    name: str
    kind: str = Field(description="annuelle, couvert, perenne or jachere.")
    season_months: float
    infiltration_score: int
    residue_score: int
    cover_score: int


class DataSourceOut(CamelModel):
    """A data service as configured (`GET /data-sources`). Headers are never shown."""

    key: str
    dataset: str
    provides: str
    reference: str = Field(description="The publication that describes the dataset.")
    url: str
