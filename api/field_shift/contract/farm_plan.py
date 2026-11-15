"""FarmPlan 2.0: what the algorithm returns (see docs/ALGO_CONTRACT.md).

One plan per section, cycle by cycle. Dates are ISO dates, positions count from 1, messages are in
French and name no study. A missing value is an explicit `null`, never an absent key: the screens
read `robustness`, `sowing`, `positions`… and tell "unknown" from "zero".
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from field_shift.algorithm.planning.cycle_plan import Decision
from field_shift.contract.base import CamelModel

StepKind = Literal["culture", "couvert", "jachere"]


class SourceInfo(CamelModel):
    """Where a kind of data comes from, and whether it is real."""

    real: bool
    label: str


class PlanMeta(CamelModel):
    engine: str
    algorithm: str
    demo: bool = Field(description="True while a data source is fictitious.")
    generated_at: datetime
    sources: dict[str, SourceInfo]


class PlanSettings(CamelModel):
    cycle_years: int
    frequency_months: int
    positions_per_cycle: int
    horizon_years: int
    current_year: int
    priorities: list[str] = Field(description="The ranking the weights were computed from.")


class HistoryEntry(CamelModel):
    """What the algorithm read of the past of the field."""

    crop: str
    from_year: int = Field(alias="from")
    to_year: int = Field(alias="to")


class FieldMeasuresOut(CamelModel):
    slope_pct: float
    heavy_rain_days: float
    bare_soil_days: float


class WaterPressureOut(CamelModel):
    """The water pressure of the farm (the water risk before the irrigation is counted)."""

    pressure: float = Field(description="0 (water is not scarce) to 1 (very dry).")
    worst: float = Field(description="The pressure with the worst climate model.")
    components: dict[str, float] = Field(
        description="aridite, pluie_ete, nappes, stress_mesure: each from 0 to 1."
    )
    missing: list[str] = Field(description="Components no source could give.")
    sources: dict[str, str] = Field(description="Where each piece of data comes from.")
    aridity_index: float | None = Field(description="Rain / reference evapotranspiration.")
    aridity_class: str


class ModelNoteOut(CamelModel):
    model: str
    note: float


class WaterOut(CamelModel):
    """The water score of a chain (criterion `eau`) and its readable numbers."""

    note: float = Field(description="0 to 1: the mean of the climate models.")
    worst: float = Field(description="The score with the worst climate model.")
    sub_scores: dict[str, float] = Field(
        description="A sobriety, B resistance, C rain kept, D water left at sowing (0 to 1)."
    )
    demand_mm_per_year: float
    shortfall_mm_per_year: float
    irrigation_mm_per_year: float | None = Field(
        description="Irrigation needed; null when the section is not irrigated."
    )
    rain_kept_pct: float
    water_at_sowing_mm: float | None
    alerts: list[str]
    by_model: list[ModelNoteOut]


class SoilOut(CamelModel):
    clay_pct: float
    sand_pct: float
    organic_carbon: float
    ph: float
    source: str


class RisksOut(CamelModel):
    erosion: float
    water: float


class FieldOut(CamelModel):
    measures: FieldMeasuresOut
    soil: SoilOut
    risks_today: RisksOut
    water_pressure: WaterPressureOut = Field(description="With the most recent weather.")


class MonthDayOut(CamelModel):
    month: int
    day: int


class ClimateOut(CamelModel):
    method: Literal["tendance", "modeles"]
    source: str
    models: list[str]
    last_spring_frost: MonthDayOut | None
    first_fall_frost: MonthDayOut | None
    january_minimum_c: float
    warming_c: float
    summer_rain_change_pct: float
    harvest_advance_days: int


class TwinCellOut(CamelModel):
    lat: float
    lon: float
    sigma: float | None
    sources: list[str]


class TwinsOut(CamelModel):
    sigma_mean: float | None
    reliable: bool = Field(description="Mean sigma of 2 or less: good twins exist.")
    cells: list[TwinCellOut]
    crops: list[str]


class StepOut(CamelModel):
    sheet: str
    crop: str
    kind: StepKind
    sowing: date | None
    harvest: date | None
    positions: tuple[int, int] | None


class GapOut(CamelModel):
    previous: str
    next: str
    message: str


class SharedDiseaseOut(CamelModel):
    disease: str
    previous: str
    next: str
    years_without: int
    advised: int
    message: str


class ChainOut(CamelModel):
    score: float
    criteria: dict[str, float | None]
    label: str
    sheets: list[str]
    steps: list[StepOut]
    gaps: list[GapOut]
    seeds_to_buy: list[str]
    warnings: list[SharedDiseaseOut]
    water: WaterOut | None


class AlertReasonOut(CamelModel):
    kind: str
    previous: str
    next: str
    family: str | None = None
    disease: str | None = None


class YearAndSourceOut(CamelModel):
    year: int
    source: str


class ReferenceAlertOut(CamelModel):
    reason: AlertReasonOut
    years_without: int
    minimum: int
    start: YearAndSourceOut = Field(alias="from")
    end: YearAndSourceOut = Field(alias="to")
    message: str


class RemovedCropOut(CamelModel):
    sheet: str
    required: int
    possible: int
    occupied_years: int
    message: str


class CycleOut(CamelModel):
    index: int
    years: tuple[int, int]
    decision: Decision
    climate: ClimateOut
    twins: TwinsOut
    risks: RisksOut
    water_pressure: WaterPressureOut
    weights: dict[str, float]
    chosen: ChainOut | None
    reference: ChainOut | None
    reference_alerts: list[ReferenceAlertOut]
    alternatives: list[ChainOut]
    removed: list[RemovedCropOut]
    robustness: float | None
    becomes_infeasible_later: bool


class SectionPlanOut(CamelModel):
    id: str
    free_at: date
    first_year: int | None
    last_year: int | None
    repeats_current_crop: bool
    history_years: int
    history: list[HistoryEntry]
    field: FieldOut
    cycles: list[CycleOut]


class FarmPlan(CamelModel):
    version: Literal["2.0"] = "2.0"
    meta: PlanMeta
    settings: PlanSettings
    weights: dict[str, float]
    sections: list[SectionPlanOut]
