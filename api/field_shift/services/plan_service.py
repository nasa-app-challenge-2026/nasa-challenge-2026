"""What the web layer calls: plan a whole farm.

Reads the request, gets the weather of the farm, runs the algorithm for every section and writes
the plan. The algorithm of a place (its weather, climate models, twin grid and water model) is
built once and kept: the farmer edits his fields many times for one farm. Everything the data
services answer is kept on disk as well (`data_access/disk_cache.py`): after a restart of the
server, a place already planned is not read again.

The measures of the sections (slope, soil, satellite) are read in parallel: they are requests to
the data services, not computation.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from field_shift.algorithm.field_shift_algorithm import FieldShiftAlgorithm
from field_shift.algorithm.sources.field_data import FieldData, FieldDataSource
from field_shift.algorithm.sources.place_sources import PlaceSources
from field_shift.algorithm.timeline import month_time
from field_shift.algorithm.water.water_model import WaterModel
from field_shift.algorithm.weather.daily_weather import DailyWeather
from field_shift.contract.farm_input import FarmInput
from field_shift.contract.farm_plan import FarmPlan
from field_shift.contract.input_mapper import read_farm_input, section_place, soil_test_of
from field_shift.contract.plan_mapper import farm_plan_out
from field_shift.data_access.weather_providers import FarmWeather, WeatherProvider

#: Places kept in memory (an algorithm holds ~15 MB of weather and grid).
MAX_PLACES = 8
#: Points closer than 0.01° are the same place.
PLACE_PRECISION = 100
#: Sections whose measures are read at the same time.
MAX_PARALLEL_SECTIONS = 4

PlaceKey = tuple[int, int, int]
#: The water model of a place (lat, lon, its NASA POWER weather). Raises
#: WaterDataUnavailableError.
WaterModelProvider = Callable[[float, float, FarmWeather], WaterModel]


class PlaceDataProvider(Protocol):
    def place_sources(self, lat: float, lon: float, farm_weather: DailyWeather) -> PlaceSources:
        """Steps 3 to 7 of a place: climate models, grid of observed climates, twin crops."""
        ...


@dataclass(frozen=True)
class _Place:
    weather: FarmWeather
    algorithm: FieldShiftAlgorithm


class PlanService:
    """Plans farms. Thread-safe: requests of different farms may come at the same time."""

    def __init__(
        self,
        weather: WeatherProvider,
        water: WaterModelProvider,
        place_data: PlaceDataProvider,
        field_data: FieldDataSource,
        clock: Callable[[], date] = date.today,
    ) -> None:
        self._weather = weather
        self._water = water
        self._place_data = place_data
        self._field_data = field_data
        self._clock = clock
        self._places: OrderedDict[PlaceKey, _Place] = OrderedDict()
        self._lock = threading.Lock()
        self._place_locks: dict[PlaceKey, threading.Lock] = {}

    def plan_farm(self, farm_input: FarmInput, generated_at: datetime | None = None) -> FarmPlan:
        today = farm_input.today or self._clock()
        location = farm_input.farm.location
        place = self._known_place(location.lat, location.lon, today.year)
        if place is not None:
            field_data = self._sections_data(farm_input, place.weather.weather)
        else:
            farm_weather = self._weather.farm_weather(location.lat, location.lon)
            # The place (water model, grid of the twins) and the sections are read at the same
            # time: different services, nothing to wait for between them.
            with ThreadPoolExecutor(max_workers=2) as pool:
                place_job = pool.submit(
                    self._place_for, location.lat, location.lon, today.year, farm_weather
                )
                sections_job = pool.submit(self._sections_data, farm_input, farm_weather.weather)
                place, field_data = place_job.result(), sections_job.result()
        context = read_farm_input(farm_input, field_data, self._field_data.source)
        now = month_time.of_date(today)
        plans = [
            place.algorithm.plan_parcel(
                parcel, context.time, context.farmer, now, soil=field_data[parcel.id].soil
            )
            for parcel in context.parcels
        ]
        return farm_plan_out(context, plans, place.algorithm, today, generated_at)

    def prepare_place(self, lat: float, lon: float, today: date) -> None:
        """Builds the place when it is not kept yet. Everything its data services answer is then
        on disk: another process that plans the same place reads it there, not on the network."""
        if self._known_place(lat, lon, today.year) is None:
            self._place_for(lat, lon, today.year, self._weather.farm_weather(lat, lon))

    def _sections_data(self, farm_input: FarmInput, weather: DailyWeather) -> dict[str, FieldData]:
        """The measures of every section, read in parallel (by section id)."""
        location = farm_input.farm.location
        sections = farm_input.sections

        def read(section) -> FieldData:
            place = section_place(section, location.lat, location.lon)
            return self._field_data.field_data(place, soil_test_of(section), weather)

        workers = max(1, min(MAX_PARALLEL_SECTIONS, len(sections)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            data = list(pool.map(read, sections))
        return {section.id: value for section, value in zip(sections, data, strict=True)}

    @staticmethod
    def _key(lat: float, lon: float, current_year: int) -> PlaceKey:
        return (round(lat * PLACE_PRECISION), round(lon * PLACE_PRECISION), current_year)

    def _known_place(self, lat: float, lon: float, current_year: int) -> _Place | None:
        """The place when it is already built (the most recent one kept)."""
        key = self._key(lat, lon, current_year)
        with self._lock:
            if key in self._places:
                self._places.move_to_end(key)
                return self._places[key]
        return None

    def _place_for(
        self, lat: float, lon: float, current_year: int, farm_weather: FarmWeather
    ) -> _Place:
        key = self._key(lat, lon, current_year)
        with self._lock:
            if key in self._places:
                self._places.move_to_end(key)
                return self._places[key]
            place_lock = self._place_locks.setdefault(key, threading.Lock())
        with place_lock:  # one farm being built does not block the others
            with self._lock:
                if key in self._places:
                    return self._places[key]
            with ThreadPoolExecutor(max_workers=2) as pool:  # two independent sets of services
                water_job = pool.submit(self._water, lat, lon, farm_weather)
                sources_job = pool.submit(
                    self._place_data.place_sources, lat, lon, farm_weather.weather
                )
                water, sources = water_job.result(), sources_job.result()
            algorithm = FieldShiftAlgorithm(
                farm_weather.weather,
                farm_weather.source,
                current_year,
                water=water,
                place=sources,
            )
            place = _Place(farm_weather, algorithm)
            with self._lock:
                self._places[key] = place
                while len(self._places) > MAX_PLACES:
                    self._places.popitem(last=False)
            return place
