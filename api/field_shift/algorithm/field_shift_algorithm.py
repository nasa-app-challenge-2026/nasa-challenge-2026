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

The data sources are given when it is built: the farm weather (real NASA POWER or the demo
series), the water model of the place (`algorithm/water`: water score of the chains, water
pressure of the farm) and, for now, fictitious climate models, twins and satellite measures
(`sources/demo_*`).
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
from field_shift.algorithm.sources.demo_climate_models import demo_climate_models
from field_shift.algorithm.sources.demo_twin_atlas import demo_twin_atlas
from field_shift.algorithm.sources.demo_twin_crops import demo_twin_evidence
from field_shift.algorithm.twins.climate_twin_finder import ClimateTwinFinder
from field_shift.algorithm.water.water_model import WaterModel, WaterPressure
from field_shift.algorithm.weather.daily_weather import DailyWeather

ALGORITHM_VERSION = "field_shift v5.1"


class FieldShiftAlgorithm:
    """The algorithm for the farm of one place."""

    #: What is fictitious for now (replaced by real data one by one, see docs/ALGORITHME.md).
    DEMO_SOURCES = (
        DataSource(
            "climateModels", False, "3 modèles climatiques fictifs (à la place de NEX-GDDP-CMIP6)"
        ),
        DataSource("twins", False, "Grille de climats et cultures des jumeaux fictive"),
        DataSource("fieldMeasures", False, "Mesures satellites de l’érosion et sol fictifs"),
    )

    def __init__(
        self,
        farm_weather: DailyWeather,
        weather_source: DataSource,
        lat: float,
        lon: float,
        current_year: int,
        water: WaterModel,
    ) -> None:
        self.weather_source = weather_source
        self.water_source = water.source
        #: The water pressure of the farm today: the one of its most recent weather.
        self.water_today: WaterPressure = water.for_cycle(
            ((weather_source.label, farm_weather.between(*RECENT_WINDOW)),)
        ).pressure
        self._data = CycleDataProvider(
            projector=TargetClimateProjector(
                farm_weather, current_year, models=demo_climate_models(farm_weather)
            ),
            twin_finder=ClimateTwinFinder(demo_twin_atlas(lat, lon, farm_weather)),
            evidence_for=demo_twin_evidence,
            water=water,
        )

    @property
    def data_sources(self) -> tuple[DataSource, ...]:
        """All the data sources of a plan, the farm weather first."""
        return (self.weather_source, self.water_source, *self.DEMO_SOURCES)

    @property
    def is_demo(self) -> bool:
        return any(not source.real for source in self.data_sources)

    def plan_parcel(
        self, parcel: Parcel, time: TimeSettings, farmer: FarmerProfile, today: float
    ) -> ParcelPlan:
        """The plan of one field, cycle after cycle. `today` is an absolute month."""
        return ParcelPlanner(time, farmer, self._data, today).plan(parcel)
