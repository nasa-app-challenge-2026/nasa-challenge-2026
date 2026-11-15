"""What the web layer calls: plan a whole farm.

Reads the request, gets the weather of the farm, runs the algorithm for every section and writes
the plan. The algorithm of a place (its weather, climate models and twin grid) is built once and
kept: the farmer edits his fields many times for one farm.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from collections.abc import Callable
from datetime import date, datetime

from field_shift.algorithm.field_shift_algorithm import FieldShiftAlgorithm
from field_shift.algorithm.sources.field_data import DemoFieldDataSource, FieldDataSource
from field_shift.algorithm.timeline import month_time
from field_shift.contract.farm_input import FarmInput
from field_shift.contract.farm_plan import FarmPlan
from field_shift.contract.input_mapper import read_farm_input
from field_shift.contract.plan_mapper import farm_plan_out
from field_shift.data_access.weather_providers import WeatherProvider

#: Places kept in memory (an algorithm holds ~15 MB of weather and grid).
MAX_PLACES = 8
#: Points closer than 0.01° are the same place.
PLACE_PRECISION = 100

PlaceKey = tuple[int, int, int]


class PlanService:
    """Plans farms. Thread-safe: requests of different farms may come at the same time."""

    def __init__(
        self,
        weather: WeatherProvider,
        field_data: FieldDataSource | None = None,
        clock: Callable[[], date] = date.today,
    ) -> None:
        self._weather = weather
        self._field_data = field_data or DemoFieldDataSource()
        self._clock = clock
        self._places: OrderedDict[PlaceKey, FieldShiftAlgorithm] = OrderedDict()
        self._lock = threading.Lock()

    def plan_farm(self, farm_input: FarmInput, generated_at: datetime | None = None) -> FarmPlan:
        today = farm_input.today or self._clock()
        location = farm_input.farm.location
        algorithm = self._algorithm_for(location.lat, location.lon, today.year)
        context = read_farm_input(farm_input, self._field_data)
        now = month_time.of_date(today)
        plans = [
            algorithm.plan_parcel(parcel, context.time, context.farmer, now)
            for parcel in context.parcels
        ]
        return farm_plan_out(context, plans, algorithm, today, generated_at)

    def _algorithm_for(self, lat: float, lon: float, current_year: int) -> FieldShiftAlgorithm:
        key = (round(lat * PLACE_PRECISION), round(lon * PLACE_PRECISION), current_year)
        with self._lock:
            if key in self._places:
                self._places.move_to_end(key)
                return self._places[key]
            farm_weather = self._weather.farm_weather(lat, lon)
            algorithm = FieldShiftAlgorithm(
                farm_weather.weather, farm_weather.source, lat, lon, current_year
            )
            self._places[key] = algorithm
            while len(self._places) > MAX_PLACES:
                self._places.popitem(last=False)
            return algorithm
