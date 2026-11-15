"""Steps 2 and 3 against the reference implementation (field_shift.py v5.1)."""

from __future__ import annotations

import numpy as np
import pytest

from field_shift.algorithm.climate.delta_method import apply_deltas
from field_shift.algorithm.climate.indicator_table import IndicatorTable
from field_shift.algorithm.climate.target_climate_projector import TargetClimateProjector
from field_shift.algorithm.climate.temperature_trend import TemperatureTrend
from tests.helpers.reference_names import fixture
from tests.helpers.synthetic_weather import SyntheticModel, synthetic_weather

REF = fixture("climate.json")
WEATHER = synthetic_weather(
    REF["weather"]["first_year"], REF["weather"]["last_year"], REF["weather"]["seed"]
)
MODELS = [
    SyntheticModel(name, m["seed"], m["warming_factor"], m["rain_ratio"])
    for name, m in REF["models"].items()
]


def assert_climate_close(actual, expected) -> None:
    np.testing.assert_allclose(actual.degree_days_per_day, expected["dj_jour"], rtol=1e-9)
    assert actual.last_spring_frost == pytest.approx(expected["gel_printemps"], rel=1e-9)
    assert actual.first_fall_frost == pytest.approx(expected["gel_automne"], rel=1e-9)
    assert actual.january_minimum_c == pytest.approx(expected["tmin_janvier"], rel=1e-9)
    assert actual.harvest_advance_months == pytest.approx(expected["decalage_fin"], rel=1e-7)
    assert actual.summer_rain_change_pct == pytest.approx(
        expected["delta_pluie_ete_pct"], rel=1e-7, abs=1e-7
    )
    assert actual.source == expected["source"]


def test_step_2_gives_the_same_yearly_indicators():
    table = IndicatorTable.from_weather(WEATHER)
    assert table.years.tolist() == REF["yearly_indicators"]["years"]
    np.testing.assert_allclose(table.rows, REF["yearly_indicators"]["table"], rtol=1e-9)


def test_case_1_extends_the_40_year_trend():
    trend = TemperatureTrend(WEATHER)
    shifted, shift_c = trend.extend_to(REF["extended"]["target_year"])
    assert trend.slope_per_year == pytest.approx(REF["extended"]["slope"], rel=1e-9)
    assert shift_c == pytest.approx(REF["extended"]["shift"], rel=1e-9)
    rows = IndicatorTable.from_weather(shifted).rows[:3]
    np.testing.assert_allclose(rows, REF["extended"]["first_rows"], rtol=1e-9)


def test_case_2_applies_the_monthly_deltas_of_a_model():
    simulation = MODELS[0].simulate(2028, 2047)
    moved = apply_deltas(WEATHER.between(1985, 2014), simulation.historical, simulation.future)
    rows = IndicatorTable.from_weather(moved).rows[:3]
    np.testing.assert_allclose(rows, REF["delta_x_2028_2047"]["table_first_rows"], rtol=1e-8)


def test_the_trend_is_used_up_to_10_years_ahead_and_the_models_after():
    projector = TargetClimateProjector(WEATHER, current_year=2026, models=MODELS)

    short = projector.project(2027, 2030)
    assert [t.source for t in short.targets] == ["NASA POWER"]
    assert (
        len(short.targets[0].indicators.rows) == REF["cycle_2027_2030"]["target_rows"]["NASA POWER"]
    )
    assert_climate_close(short.climate, REF["cycle_2027_2030"]["climate"])

    long = projector.project(2037, 2040)
    assert [t.source for t in long.targets] == list(REF["models"])
    for target in long.targets:
        np.testing.assert_allclose(
            target.indicators.means(), REF["cycle_2037_2040"]["targets"][target.source], rtol=1e-8
        )
    assert_climate_close(long.climate, REF["cycle_2037_2040"]["climate"])


def test_a_cycle_beyond_10_years_needs_climate_models():
    with pytest.raises(ValueError, match="modèles climatiques"):
        TargetClimateProjector(WEATHER, current_year=2026).project(2037, 2040)
