"""FarmInput 2.0: what the screens send to the algorithm (see docs/ALGO_CONTRACT.md).

The farm (place, cycle / frequency / horizon, ranked priorities, seed reserve) and one entry per
section (crop in place and its harvest month, previous years, current rotation, soil diseases,
irrigation, soil test). Invalid input is refused with a 422 that says which field is wrong.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Annotated, Literal

from pydantic import AfterValidator, Field, model_validator

from field_shift.algorithm.planning.time_settings import TimeSettings
from field_shift.algorithm.terrain.section_shape import SectionShape, ShapeError
from field_shift.contract.base import CamelModel
from field_shift.reference.criteria import CRITERIA_IDS
from field_shift.reference.crops import EQUIPMENT_FORAGE, SHEETS, is_known_crop
from field_shift.reference.planning import ReserveMode
from field_shift.reference.return_delays import SOIL_DISEASES

CONTRACT_VERSION = "2.0"
YEAR_MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
MAX_SECTION_ID_LENGTH = 3
MIN_PH, MAX_PH = 3, 10
PERCENT_RANGE = {"ge": 0, "le": 100}
#: Fewer distinct corners than this: the section is not drawn yet.
MIN_POLYGON_CORNERS = 3


def _one_of(allowed, what: str):
    def check(value: str) -> str:
        if value not in allowed:
            raise ValueError(f"{what} inconnu : {value}")
        return value

    return check


def _known_crop(value: str) -> str:
    if not is_known_crop(value):
        raise ValueError(f"culture inconnue : {value}")
    return value


CropId = Annotated[str, AfterValidator(_known_crop)]
SheetId = Annotated[str, AfterValidator(_one_of(SHEETS, "fiche de culture"))]


def _known_priority(value: str) -> str:
    if value not in CRITERIA_IDS:
        raise ValueError(f"priorité inconnue : {value} (priorités : {', '.join(CRITERIA_IDS)})")
    return value


CriterionId = Annotated[str, AfterValidator(_known_priority)]
DiseaseId = Annotated[str, AfterValidator(_one_of(SOIL_DISEASES, "maladie du sol"))]
EquipmentId = Annotated[str, AfterValidator(_one_of({EQUIPMENT_FORAGE}, "équipement"))]


class Location(CamelModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    label: str | None = None


class TimeInput(CamelModel):
    """Step 1, block C: cycle (2 to 6 years), frequency (12, 6 or 4 months), horizon (a multiple
    of the cycle)."""

    cycle_years: int
    frequency_months: int
    horizon_years: int

    @model_validator(mode="after")
    def check_time_settings(self) -> TimeInput:
        errors = TimeSettings.errors(self.cycle_years, self.frequency_months, self.horizon_years)
        if errors:
            raise ValueError(" ".join(errors))
        return self


class SeedsInput(CamelModel):
    """Step 1, block B: the seeds the farmer owns (no quantities) and what the reserve means."""

    crops: list[CropId]
    mode: ReserveMode = ReserveMode.PREFERRED


class FarmInfo(CamelModel):
    type: Literal["grandes-cultures"]
    location: Location
    time: TimeInput
    priorities: list[CriterionId] = Field(
        description="The four priorities (rendement, eau, protection_sol, ravageurs), most "
        "important first. One left out keeps a small weight."
    )
    seeds: SeedsInput
    missing_equipment: list[EquipmentId] = Field(default_factory=list)

    @model_validator(mode="after")
    def priorities_are_distinct(self) -> FarmInfo:
        if len(set(self.priorities)) != len(self.priorities):
            raise ValueError("une priorité ne peut être classée qu’une fois")
        return self


class HistoryInput(CamelModel):
    year: int
    crop: CropId | None


class SoilTestInput(CamelModel):
    clay_pct: float = Field(**PERCENT_RANGE)
    sand_pct: float = Field(**PERCENT_RANGE)
    organic_carbon: float = Field(gt=0, description="g/kg")
    ph: float = Field(ge=MIN_PH, le=MAX_PH)


class SectionInput(CamelModel):
    """Step 1, block A: what the farmer knows about one field.

    `polygon` is its outline as the screens draw it, [lat, lon] corners (the measures of the field
    are read over it); empty or absent: not drawn yet, the point of the farm is used."""

    id: str = Field(min_length=1, max_length=MAX_SECTION_ID_LENGTH)
    area_ha: float = Field(gt=0)
    polygon: list[tuple[float, float]] | None = None
    current_crop: CropId | None = None
    current_harvest: str | None = Field(
        default=None, description="Month of harvest (or end of a perennial), YYYY-MM."
    )
    history: list[HistoryInput] = Field(default_factory=list)
    current_rotation: list[SheetId] = Field(default_factory=list)
    rotation_position: int = Field(default=0, ge=0)
    diseases: list[DiseaseId] = Field(default_factory=list)
    irrigated: bool = False
    soil_test: SoilTestInput | None = None

    @model_validator(mode="after")
    def check_harvest_month(self) -> SectionInput:
        if self.current_harvest is not None and not YEAR_MONTH.match(self.current_harvest):
            raise ValueError("current_harvest doit s’écrire AAAA-MM")
        return self

    @property
    def ring(self) -> tuple[tuple[float, float], ...]:
        """The outline as a closed ring of (lon, lat) points; empty when not drawn."""
        corners = [(float(lon), float(lat)) for lat, lon in self.polygon or ()]
        if len(set(corners)) < MIN_POLYGON_CORNERS:
            return ()
        if corners[0] != corners[-1]:
            corners.append(corners[0])
        return tuple(corners)

    @property
    def shape(self) -> SectionShape:
        return SectionShape.from_coordinates(self.ring)

    @model_validator(mode="after")
    def check_polygon(self) -> SectionInput:
        if self.ring:
            try:
                self.shape  # noqa: B018 (the outline is checked here: a 422 that says why)
            except ShapeError as error:
                raise ValueError(f"section {self.id}, polygon : {error}") from error
        return self


class FarmInput(CamelModel):
    version: Literal["2.0"]
    farm: FarmInfo
    sections: list[SectionInput] = Field(min_length=1)
    today: date | None = Field(default=None, description="Date of use; the server date if absent.")

    @model_validator(mode="after")
    def sections_are_distinct(self) -> FarmInput:
        ids = [section.id for section in self.sections]
        if len(set(ids)) != len(ids):
            raise ValueError("deux sections ont le même id")
        return self
