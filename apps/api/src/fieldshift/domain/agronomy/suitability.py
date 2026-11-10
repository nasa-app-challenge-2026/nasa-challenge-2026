"""Documented climatic checks of one crop in one historical year (crop suitability).

Two hazards are evaluated, and only where a source gives a threshold:

* **Heat for maturity** (annual crops): heat accumulated in the year's season, compared with
  the documented range needed from sowing to maturity.
* **Damaging spring frost** (annual crops): days, after the start of the crop's season and
  before 15 July, with a minimum at or below the documented damage threshold.

Sowing dates are unknown, so seasons are derived from the weather of each year (see
``docs/methodology.md``). A favourable outcome means "no documented constraint was hit",
never "the crop would have yielded well".
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from fieldshift.domain.agronomy.crops import Crop, HeatUnit, SeasonModel
from fieldshift.domain.climate.seasons import FROST_SEASON_PIVOT, Season
from fieldshift.domain.climate.year_context import YearContext


class HeatStatus(StrEnum):
    SUFFICIENT = "sufficient"
    """Available heat reached the upper end of the documented range."""
    TIGHT = "tight"
    """Within the documented range: enough for the earliest maturities only."""
    INSUFFICIENT = "insufficient"
    """Below the lower end of the documented range."""
    NOT_APPLICABLE = "not_applicable"
    """Perennial forage: harvested without waiting for grain maturity."""
    NOT_DOCUMENTED = "not_documented"


class FrostStatus(StrEnum):
    EXPOSED = "exposed"
    NOT_EXPOSED = "not_exposed"
    NOT_DOCUMENTED = "not_documented"


EVALUATED_HEAT = frozenset({HeatStatus.SUFFICIENT, HeatStatus.TIGHT, HeatStatus.INSUFFICIENT})


@dataclass(frozen=True, slots=True)
class HeatCheck:
    status: HeatStatus
    available: float | None
    """Heat accumulated over ``window``, in the unit of the crop's requirement."""
    window: Season | None


@dataclass(frozen=True, slots=True)
class FrostCheck:
    status: FrostStatus
    damaging_frost_days: int | None
    first_damaging_frost_index: int | None
    window: Season | None


@dataclass(frozen=True, slots=True)
class CropYearOutcome:
    crop_id: str
    year: int
    heat: HeatCheck
    frost: FrostCheck

    @property
    def has_documented_problem(self) -> bool:
        return (
            self.heat.status is HeatStatus.INSUFFICIENT or self.frost.status is FrostStatus.EXPOSED
        )


def season_start_index(crop: Crop, context: YearContext) -> int | None:
    """First day of the crop's season in this year, derived from the weather."""
    if crop.season_model is SeasonModel.WARM_SEASON:
        season = context.crop_heat_unit_season
    else:
        season = context.growing_season
    return season.start_index if season is not None else None


def heat_window(crop: Crop, context: YearContext) -> Season | None:
    """Days over which heat counts toward maturity.

    Warm-season crops: the crop heat unit season (Québec method), which already ends at the
    first fall frost of -2 °C or less. Cool-season crops: the thermal growing season, cut at
    that same killing frost when it comes first.
    """
    if crop.season_model is SeasonModel.WARM_SEASON:
        return context.crop_heat_unit_season
    if crop.season_model is SeasonModel.COOL_SEASON:
        season = context.growing_season
        if season is None:
            return None
        end = season.end_index
        killing_frost = context.first_fall_killing_frost_index
        if killing_frost is not None:
            end = min(end, killing_frost)
        return Season(season.start_index, end) if end > season.start_index else None
    return None


def _heat_series(unit: HeatUnit, context: YearContext) -> tuple[float, ...]:
    if unit is HeatUnit.CROP_HEAT_UNITS:
        return context.crop_heat_units
    return context.degree_days_base0


def check_heat(crop: Crop, context: YearContext) -> HeatCheck:
    if not crop.is_annual:
        return HeatCheck(HeatStatus.NOT_APPLICABLE, available=None, window=None)
    requirement = crop.heat_requirement
    if requirement is None:
        return HeatCheck(HeatStatus.NOT_DOCUMENTED, available=None, window=None)

    window = heat_window(crop, context)
    available = 0.0
    if window is not None:
        series = _heat_series(requirement.unit, context)
        available = sum(series[window.start_index : window.end_index])

    if available < requirement.minimum:
        status = HeatStatus.INSUFFICIENT
    elif available < requirement.maximum:
        status = HeatStatus.TIGHT
    else:
        status = HeatStatus.SUFFICIENT
    return HeatCheck(status, available=available, window=window)


def frost_window(crop: Crop, context: YearContext) -> Season | None:
    """Establishment period: from the start of the crop's season to 14 July."""
    start = season_start_index(crop, context)
    pivot = context.data.index_of(*FROST_SEASON_PIVOT)
    if start is None or start >= pivot:
        return None
    return Season(start, pivot)


def check_frost(crop: Crop, context: YearContext) -> FrostCheck:
    tolerance = crop.frost_tolerance
    if not crop.is_annual or tolerance is None:
        return FrostCheck(FrostStatus.NOT_DOCUMENTED, None, None, None)

    window = frost_window(crop, context)
    if window is None:
        # No season this year: the heat check already reports the crop as impossible.
        return FrostCheck(FrostStatus.NOT_EXPOSED, 0, None, None)

    frost_days = [
        index
        for index in range(window.start_index, window.end_index)
        if tolerance.damage_threshold.is_reached(context.data.t_min_c[index])
    ]
    return FrostCheck(
        status=FrostStatus.EXPOSED if frost_days else FrostStatus.NOT_EXPOSED,
        damaging_frost_days=len(frost_days),
        first_damaging_frost_index=frost_days[0] if frost_days else None,
        window=window,
    )


def evaluate_crop_year(crop: Crop, context: YearContext) -> CropYearOutcome:
    return CropYearOutcome(
        crop_id=crop.id,
        year=context.year,
        heat=check_heat(crop, context),
        frost=check_frost(crop, context),
    )
