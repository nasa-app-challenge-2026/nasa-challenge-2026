"""Field Shift, the rotation algorithm (field_shift v5.1, see docs/ALGORITHME.md).

The facade of the algorithm for one farm place. It is built once per place (the weather of the
farm, the climate models and the twin grid do not depend on the farmer's choices) and plans any
number of fields:

    step 1     the farmer's inputs           planning/ (TimeSettings, FarmerProfile, Parcel)
    steps 2-3  target climate per cycle      climate/
    step 4     climate twins                 twins/climate_twin_finder.py
    steps 5-7  soil, rotations, precrops     twins/
    step 8     field diagnostic              diagnostic/
    step 9b    best chains                   chain/
    step 10    plan, cycle by cycle          planning/

Every data source is given when it is built: the farm weather (NASA POWER), the water model of
the place (`algorithm/water`: water score of the chains, water pressure of the farm) and the
sources of steps 3 to 7 (`PlaceSources`: climate models, grid of observed climates, crops of the
twins). The algorithm contains no data of its own.
"""

from __future__ import annotations

from field_shift.algorithm.climate.target_climate_projector import TargetClimateProjector
from field_shift.algorithm.config.climate import RECENT_WINDOW
from field_shift.algorithm.planning.cycle_plan import ParcelPlan
from field_shift.algorithm.planning.farmer_profile import FarmerProfile
from field_shift.algorithm.planning.parcel import Parcel
from field_shift.algorithm.planning.parcel_planner import ParcelPlanner
from field_shift.algorithm.planning.time_settings import TimeSettings
from field_shift.algorithm.sources.cycle_data_provider import CycleDataProvider
from field_shift.algorithm.sources.data_source import DataSource
from field_shift.algorithm.sources.place_sources import PlaceSources
from field_shift.algorithm.twins.climate_twin_finder import ClimateTwinFinder
from field_shift.algorithm.twins.soil_comparison import Soil
from field_shift.algorithm.water.water_model import WaterModel, WaterPressure
from field_shift.algorithm.weather.daily_weather import DailyWeather

ALGORITHM_VERSION = "field_shift v5.1"


class FieldShiftAlgorithm:
    """The algorithm for the farm of one place."""

    def __init__(
        self,
        farm_weather: DailyWeather,
        weather_source: DataSource,
        current_year: int,
        water: WaterModel,
        place: PlaceSources,
    ) -> None:
        self.weather_source = weather_source
        self.water_source = water.source
        self.place_sources = place.sources
        self.notes = place.notes
        #: The water pressure of the farm today: the one of its most recent weather.
        self.water_today: WaterPressure = water.for_cycle(
            ((weather_source.label, farm_weather.between(*RECENT_WINDOW)),)
        ).pressure
        self._data = CycleDataProvider(
            projector=TargetClimateProjector(
                farm_weather, current_year, models=place.models, models_label=place.models_label
            ),
            twin_finder=ClimateTwinFinder(place.grid, cultivation=place.cultivation),
            evidence_for=place.evidence_for,
            water=water,
        )

    @property
    def data_sources(self) -> tuple[DataSource, ...]:
        """All the data sources of a plan, the farm weather first."""
        return (self.weather_source, self.water_source, *self.place_sources)

    @property
    def is_demo(self) -> bool:
        return any(not source.real for source in self.data_sources)

    def plan_parcel(
        self,
        parcel: Parcel,
        time: TimeSettings,
        farmer: FarmerProfile,
        today: float,
        soil: Soil | None = None,
    ) -> ParcelPlan:
        """The plan of one field, cycle after cycle. `today` is an absolute month; `soil` is the
        soil of the field (step 5 keeps the twin fields of a comparable soil)."""
        return ParcelPlanner(time, farmer, self._data.for_soil(soil), today).plan(parcel)
