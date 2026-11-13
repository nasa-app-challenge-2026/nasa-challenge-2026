"""Everything derived from one complete year of data at one site, computed once.

Both the climate indicators and the crop rules read from a ``YearContext``, so a season
boundary or a heat-unit total has exactly one definition in the code base.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from functools import cached_property

from fieldshift.domain.climate import seasons
from fieldshift.domain.climate.formulas import (
    crop_heat_units,
    daily_mean_from_extremes,
    growing_degree_days,
    hargreaves_reference_evapotranspiration_mm,
)
from fieldshift.domain.climate.seasons import Season
from fieldshift.domain.climate.series import YearData

AGROCLIMATIC_WINDOW = ((4, 1), (10, 31))
"""1 April to 31 October: the accumulation window of the agroclimatic products of
Agriculture and Agri-Food Canada (source: aafc_agroclimate)."""


@dataclass(frozen=True, slots=True)
class SiteContext:
    """Site-level constants shared by every year of an analysis."""

    latitude_deg: float
    chu_search_start_index: int
    """Median day-of-year index of the last spring frost (Québec heat-unit method)."""
    chu_reference_first_year: int
    chu_reference_last_year: int


def build_site_context(latitude_deg: float, years: Sequence[YearData]) -> SiteContext:
    if not years:
        raise ValueError("at least one complete year is required")
    reference = years[-seasons.CHU_REFERENCE_YEARS :]
    return SiteContext(
        latitude_deg=latitude_deg,
        chu_search_start_index=seasons.median_last_spring_frost_index(years),
        chu_reference_first_year=reference[0].year,
        chu_reference_last_year=reference[-1].year,
    )


class YearContext:
    """Lazily computed, immutable view of one year. Indices are 0-based days of the year."""

    def __init__(self, data: YearData, site: SiteContext) -> None:
        self.data = data
        self.site = site

    @property
    def year(self) -> int:
        return self.data.year

    def window(self, start: tuple[int, int], end: tuple[int, int]) -> tuple[int, int]:
        """Half-open index range covering two calendar dates (month, day), both included."""
        return self.data.index_of(*start), self.data.index_of(*end) + 1

    @cached_property
    def agroclimatic_window(self) -> tuple[int, int]:
        return self.window(*AGROCLIMATIC_WINDOW)

    # --- Daily derived series -------------------------------------------------

    @cached_property
    def daily_means_c(self) -> tuple[float, ...]:
        """``(Tmax + Tmin) / 2``, the mean used by agroclimatic indices."""
        return tuple(
            daily_mean_from_extremes(t_max, t_min)
            for t_max, t_min in zip(self.data.t_max_c, self.data.t_min_c, strict=True)
        )

    @cached_property
    def crop_heat_units(self) -> tuple[float, ...]:
        return tuple(
            crop_heat_units(t_max, t_min)
            for t_max, t_min in zip(self.data.t_max_c, self.data.t_min_c, strict=True)
        )

    @cached_property
    def reference_evapotranspiration_mm(self) -> tuple[float, ...]:
        return tuple(
            hargreaves_reference_evapotranspiration_mm(
                t_max, t_min, self.site.latitude_deg, day_of_year
            )
            for day_of_year, (t_max, t_min) in enumerate(
                zip(self.data.t_max_c, self.data.t_min_c, strict=True), start=1
            )
        )

    def degree_days(self, base_c: float) -> tuple[float, ...]:
        return tuple(
            growing_degree_days(t_max, t_min, base_c)
            for t_max, t_min in zip(self.data.t_max_c, self.data.t_min_c, strict=True)
        )

    @cached_property
    def degree_days_base0(self) -> tuple[float, ...]:
        return self.degree_days(0.0)

    # --- Seasons and frost dates ----------------------------------------------

    @cached_property
    def growing_season(self) -> Season | None:
        return seasons.thermal_growing_season(self.data)

    @cached_property
    def crop_heat_unit_season(self) -> Season | None:
        return seasons.crop_heat_unit_season(self.data, self.site.chu_search_start_index)

    @cached_property
    def last_spring_frost_index(self) -> int | None:
        return seasons.last_spring_frost_index(self.data, seasons.FROST)

    @cached_property
    def first_fall_frost_index(self) -> int | None:
        return seasons.first_fall_frost_index(self.data, seasons.FROST)

    @cached_property
    def first_fall_killing_frost_index(self) -> int | None:
        return seasons.first_fall_frost_index(self.data, seasons.KILLING_FROST)

    @cached_property
    def frost_free_season(self) -> Season | None:
        return seasons.frost_free_season(self.data, seasons.FROST)


def build_year_contexts(latitude_deg: float, years: Sequence[YearData]) -> tuple[YearContext, ...]:
    """One context per complete year, sharing the same site constants."""
    site = build_site_context(latitude_deg, years)
    return tuple(YearContext(year, site) for year in years)
