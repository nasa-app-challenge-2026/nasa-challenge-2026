"""Small rules of the algorithm, and the deliberate differences with the reference
(docs/ALGORITHME.md, "Écarts avec la référence")."""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from field_shift.algorithm.chain.chain_scorer import successions, yield_criterion
from field_shift.algorithm.chain.crop_placer import place_crop
from field_shift.algorithm.climate.cycle_climate import ClimateMethod, CycleClimate
from field_shift.algorithm.planning.time_settings import TimeSettings
from field_shift.algorithm.sources.demo_farm_weather import demo_farm_weather
from field_shift.algorithm.sources.demo_twin_crops import demo_warming
from field_shift.algorithm.sources.field_data import (
    DEMO_SOIL_SOURCE,
    SOIL_TEST_SOURCE,
    DemoFieldDataSource,
)
from field_shift.algorithm.timeline import month_time
from field_shift.algorithm.twins.soil_comparison import Soil
from field_shift.algorithm.weather.daily_weather import DailyWeather
from field_shift.services.plan_service import MAX_PLACES, PlanService
from field_shift.tools.make_examples import ExampleWeatherProvider


class TestDeliberateDifferences:
    def test_without_a_crop_in_place_the_yield_successions_are_read_in_order(self):
        assert successions(["mais", "soya", "ble-automne"], None, complete=True) == [
            ("mais", "soya"),
            ("soya", "ble-automne"),
            ("ble-automne", "mais"),
        ]
        assert successions(["soya"], "mais", complete=False) == [("mais", "soya")]
        assert yield_criterion([]) is None

    def test_a_climate_without_frost_does_not_block_frost_sensitive_crops(self):
        tropical = CycleClimate(
            degree_days_per_day=(12.0,) * 12,
            last_spring_frost=None,
            first_fall_frost=None,
            january_minimum_c=15,
            harvest_advance_months=0,
            method=ClimateMethod.TREND,
            source="test",
        )
        time = TimeSettings(4, 12, 12)
        assert place_crop("mais", 27, 321.5, None, time, tropical) is not None

    def test_a_maturity_does_not_depend_on_the_year_of_sowing(self):
        climate = CycleClimate(
            degree_days_per_day=(0, 0, 0, 2, 6, 10, 11, 10, 6, 2, 0, 0),
            last_spring_frost=4.0,
            first_fall_frost=9.0,
            january_minimum_c=-14,
            harvest_advance_months=0,
            method=ClimateMethod.TREND,
            source="test",
        )
        first = climate.maturity(4 * 12 + 4.5, 1000) - (4 * 12)
        later = climate.maturity(20 * 12 + 4.5, 1000) - (20 * 12)
        assert first == pytest.approx(later, abs=1e-9)
        assert climate.maturity(4.5, 1_000_000) is None  # never mature within a year


class TestTimeSettings:
    def test_positions_of_a_cycle(self):
        settings = TimeSettings(cycle_years=4, frequency_months=6, horizon_years=12)
        assert (
            settings.positions_per_cycle,
            settings.cycle_count,
            settings.position_start_month,
        ) == (8, 3, 1)
        assert TimeSettings(5, 12, 10).position_start_month == 0

    @pytest.mark.parametrize(
        ("cycle", "frequency", "horizon", "message"),
        [
            (7, 12, 14, "de 2 à 6 ans"),
            (4, 5, 12, "Fréquence"),
            (4, 12, 10, "multiple du cycle"),
            (4, 12, 0, "multiple"),
        ],
    )
    def test_invalid_settings_say_why(self, cycle, frequency, horizon, message):
        with pytest.raises(ValueError, match=message):
            TimeSettings(cycle, frequency, horizon)


class TestMonthTime:
    def test_a_date_goes_back_and_forth(self):
        time = month_time.of_date(date(2026, 11, 13))
        assert time == pytest.approx(26 * 12 + 10 + 12 / 30)
        assert month_time.to_date(time) == date(2026, 11, 13)

    def test_a_month_is_read_as_its_middle(self):
        assert month_time.to_date(month_time.of_year_month(2026, 10)) == date(2026, 10, 16)

    def test_a_decimal_month_of_the_year_is_a_day(self):
        assert month_time.month_day(3.75) == month_time.MonthDay(4, 23)
        assert month_time.month_day(0.0) == month_time.MonthDay(1, 1)

    def test_the_year_of_a_time(self):
        assert month_time.year_of(month_time.of(2030, 11.9)) == 2030
        assert month_time.year_of(month_time.of(2030, 0)) == 2030


class TestWeather:
    def test_the_demo_weather_is_always_the_same(self):
        a, b = demo_farm_weather(), demo_farm_weather()
        assert np.array_equal(a.tmax, b.tmax) and len(a) == 14610
        assert (a.first_year, a.last_year) == (1985, 2024)

    def test_the_calendar_knows_leap_years(self):
        columns = DailyWeather.calendar_columns(2023, 2024)
        assert len(columns["year"]) == 365 + 366
        assert columns["day_of_year"][-1] == 366 and columns["month"][-1] == 12

    def test_years_are_cut_where_they_change(self):
        weather = demo_farm_weather().between(2000, 2002)
        assert [(year, days.stop - days.start) for year, days in weather.year_slices()] == [
            (2000, 366),
            (2001, 365),
            (2002, 365),
        ]

    def test_columns_must_have_the_same_length(self):
        weather = demo_farm_weather().between(2000, 2000)
        with pytest.raises(ValueError, match="même longueur"):
            DailyWeather(
                weather.year,
                weather.month,
                weather.day_of_year,
                weather.tmax[:-1],
                weather.tmin,
                weather.rain,
            )


class TestDemoSources:
    def test_the_fictitious_measures_of_a_section_are_stable_and_differ_between_sections(self):
        source = DemoFieldDataSource()
        a1, a2, b = (source.field_data(s, None) for s in ("A", "A", "B"))
        assert a1 == a2
        assert a1.measures != b.measures
        assert a1.soil_source == DEMO_SOIL_SOURCE

    def test_a_soil_test_replaces_soilgrids(self):
        test = Soil(40, 20, 30, 7.0)
        data = DemoFieldDataSource().field_data("A", test)
        assert data.soil == test and data.soil_source == SOIL_TEST_SOURCE

    def test_the_twins_look_warmer_as_the_cycles_go(self):
        assert demo_warming(2027, 2030) < demo_warming(2035, 2038)
        assert demo_warming(2010, 2012) == 0.0


class TestPlacesAreKept:
    def test_a_place_is_built_once_and_the_oldest_is_dropped_when_there_are_too_many(
        self, example_inputs
    ):
        reads = []

        class CountingWeather(ExampleWeatherProvider):
            def farm_weather(self, lat, lon):
                reads.append((lat, lon))
                return super().farm_weather(lat, lon)

        from copy import deepcopy

        from field_shift.contract.farm_input import FarmInput

        service = PlanService(CountingWeather())
        farm = deepcopy(example_inputs["cycle-5-ans"])
        farm["sections"] = farm["sections"][:1]

        def plan_at(lat: float) -> None:
            farm["farm"]["location"] = {"lat": lat, "lon": -72.9}
            service.plan_farm(FarmInput.model_validate(farm))

        plan_at(45.0)
        plan_at(45.0)
        assert len(reads) == 1
        for i in range(MAX_PLACES):
            plan_at(46.0 + i)  # MAX_PLACES other places push the first one out
        plan_at(45.0)
        assert reads.count((45.0, -72.9)) == 2
