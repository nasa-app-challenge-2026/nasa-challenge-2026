from __future__ import annotations

import pytest

from fieldshift.domain.climate import formulas, precipitation, seasons, statistics
from fieldshift.domain.climate.indicators import INDICATORS_BY_ID, compute_all_indicators
from fieldshift.domain.climate.series import ClimateSeries, DailyRecord
from fieldshift.domain.climate.year_context import build_year_contexts
from tests.factories import make_year, seasonal, year_records


# OMAFRA factsheet 93-119, appendix I (rounded daily CHU for Tmax, Tmin).
@pytest.mark.parametrize(
    ("t_max", "t_min", "expected"),
    [(10, 4, 0), (15, 4, 7), (15, 5, 8), (20, 10, 17), (25, 15, 25), (30, 10, 22)],
)
def test_crop_heat_units_match_published_matrix(t_max: float, t_min: float, expected: int) -> None:
    assert round(formulas.crop_heat_units(t_max, t_min)) == expected


def test_crop_heat_units_daytime_curve_peaks_at_30c() -> None:
    assert formulas.crop_heat_units(30, 0) > formulas.crop_heat_units(29, 0)
    assert formulas.crop_heat_units(30, 0) > formulas.crop_heat_units(31, 0)
    assert formulas.crop_heat_units(60, 0) == 0.0


def test_growing_degree_days_never_negative() -> None:
    assert formulas.growing_degree_days(10, 0, 0) == 5.0
    assert formulas.growing_degree_days(-2, -10, 0) == 0.0


def test_extraterrestrial_radiation_reproduces_fao56_example_8() -> None:
    # 20°S on 3 September (day 246): Ra = 32.2 MJ m-2 day-1.
    assert formulas.extraterrestrial_radiation_mj(-20, 246) == pytest.approx(32.2, abs=0.1)


def test_hargreaves_is_zero_without_daily_range() -> None:
    assert formulas.hargreaves_reference_evapotranspiration_mm(20, 20, 48, 180) == 0.0
    assert formulas.hargreaves_reference_evapotranspiration_mm(25, 10, 48, 180) > 0


def test_percentile_matches_numpy_linear_method() -> None:
    assert statistics.percentile([1, 2, 3, 4], 0.2) == pytest.approx(1.6)
    assert statistics.percentile([5], 0.8) == 5


def test_mann_kendall_and_theil_sen_on_a_monotonic_series() -> None:
    years = list(range(2000, 2010))
    values = [float(v) for v in range(10)]
    assert statistics.mann_kendall_p_value(values) == pytest.approx(8.3e-5, rel=0.05)
    assert statistics.theil_sen_slope(years, values) == 1.0
    assert statistics.trend(years[:5], values[:5]) is None  # too short to say anything


def test_dry_windows_need_the_whole_window_observed() -> None:
    rain = [0, 0, 0, 5, 0, 0]
    assert precipitation.count_dry_window_starts(rain, 0, 6, 3) == 1
    assert precipitation.longest_dry_spell(rain, 0, 6) == 3


def test_series_rejects_unordered_records_and_excludes_incomplete_years() -> None:
    records = year_records(2001, seasonal)
    with pytest.raises(ValueError, match="ascending"):
        ClimateSeries([records[1], records[0]])
    gap = records[:100] + [DailyRecord(records[100].day, None, None, None, None)] + records[101:]
    series = ClimateSeries(gap + year_records(2002, seasonal))
    assert [y.year for y in series.complete_years()] == [2002]
    assert series.completeness()[0].missing_days == 1


def test_seasons_on_a_synthetic_year() -> None:
    year = make_year(2001, seasonal)
    assert seasons.last_spring_frost_index(year) == year.index_of(4, 30)
    assert seasons.first_fall_frost_index(year) == year.index_of(10, 1)
    season = seasons.thermal_growing_season(year)
    assert season is not None
    assert (season.start_index, season.end_index) == (year.index_of(5, 1), year.index_of(10, 1))
    chu = seasons.crop_heat_unit_season(year, search_start_index=0)
    assert chu is not None  # (-10 + 4 x 18.5) / 5 = 12.8 °C on 4 May
    assert chu.start_index == year.index_of(5, 4)


def test_indicators_on_a_synthetic_year() -> None:
    contexts = build_year_contexts(48.0, [make_year(2001, seasonal)])
    values = {s.definition.id: s.values[0] for s in compute_all_indicators(contexts)}
    assert values["frost_days"] == 365 - 153
    assert values["gdd_base0"] == pytest.approx(153 * 18.5)  # May-Sep, mean 18.5 °C
    assert values["haymaking_days_june_july"] == 61
    assert values["frost_free_season_days"] == 153
    assert set(values) == set(INDICATORS_BY_ID)
