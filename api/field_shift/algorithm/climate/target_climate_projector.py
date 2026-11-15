"""Step 3: the climate the farm will have during a cycle, as day-by-day weather.

The last year of the cycle decides:
  - it ends within 10 years of today → case 1, NASA POWER trend (TemperatureTrend);
  - later → case 2, 3 to 5 NEX-GDDP-CMIP6 models applied to NASA POWER by the delta method,
    on a 20-year window centred on the cycle. Each model gives its own target climate (the
    twins are searched model by model, step 4); the calendar of step 9b is the mean of the models.

The change of a model is measured from its reference period (`ModelSimulation.reference`) and
added to the observed weather of the same period:
  - 1985–2014, the historical runs of the models: the NASA POWER years 1985–2014 of the farm
    (the reference method of field_shift.py);
  - a later period (2015–2034: the NASA POWER projection service has no historical runs): the 20
    most recent NASA POWER years, moved by the observed trend to the middle of that period, as in
    case 1. The observed warming up to the reference period, then the change of the model.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from field_shift.algorithm.climate.cycle_climate import ClimateMethod, CycleClimate
from field_shift.algorithm.climate.cycle_climate_builder import (
    average_climates,
    climate_from_weather,
    mean_summer_rain,
    mean_temperature,
)
from field_shift.algorithm.climate.delta_method import apply_deltas
from field_shift.algorithm.climate.indicator_table import IndicatorTable
from field_shift.algorithm.climate.temperature_trend import TemperatureTrend
from field_shift.algorithm.config.climate import (
    CLIMATE_WINDOW_AFTER_YEARS,
    CLIMATE_WINDOW_BEFORE_YEARS,
    MODEL_BASELINE,
    RECENT_WINDOW,
    SHORT_TERM_HORIZON_YEARS,
    YearRange,
)
from field_shift.algorithm.numerics.ratios import percent_change
from field_shift.algorithm.weather.daily_weather import DailyWeather

TREND_SOURCE = "tendance NASA POWER"
TREND_TARGET_SOURCE = "NASA POWER"


@dataclass(frozen=True)
class ModelSimulation:
    """A climate model on its reference period and on the future window (°C and mm/day).

    `historical` is the model on `reference` (1985–2014 for the historical runs)."""

    historical: DailyWeather
    future: DailyWeather
    reference: YearRange = MODEL_BASELINE


class ClimateModel(Protocol):
    """A climate model (NEX-GDDP-CMIP6, converted to °C and mm/day)."""

    name: str

    def simulate(self, first_year: int, last_year: int) -> ModelSimulation:
        """The model on its reference period and on the window `first_year`–`last_year`."""
        ...


@dataclass(frozen=True)
class ClimateTarget:
    """A target climate of the farm, searched for twins (one per model after 10 years)."""

    source: str
    indicators: IndicatorTable


@dataclass(frozen=True)
class ProjectedClimate:
    """What step 3 gives for one cycle: the targets for step 4, the calendar for step 9b, and
    the daily weather itself for the water model (one weather in case 1, one per model in
    case 2, each with its name)."""

    targets: tuple[ClimateTarget, ...]
    climate: CycleClimate
    weathers: tuple[tuple[str, DailyWeather], ...] = ()


class TargetClimateProjector:
    """Projects the climate of the farm for any cycle."""

    def __init__(
        self,
        farm_weather: DailyWeather,
        current_year: int,
        models: Sequence[ClimateModel] = (),
        models_label: str | None = None,
    ) -> None:
        """`models_label` names the mean of the models in the plan (default: "NEX-GDDP-CMIP6
        (deltas, moyenne de N modèles)")."""
        self._farm_weather = farm_weather
        self._current_year = current_year
        self._models = tuple(models)
        self._models_label = models_label
        self._trend = TemperatureTrend(farm_weather)
        self._cache: dict[tuple[int, int], ProjectedClimate] = {}

    def uses_trend(self, last_year: int) -> bool:
        """Case 1 (trend) or case 2 (models) for a cycle ending in `last_year`."""
        return last_year <= self._current_year + SHORT_TERM_HORIZON_YEARS

    def project(self, first_year: int, last_year: int) -> ProjectedClimate:
        key = (first_year, last_year)
        if key not in self._cache:
            self._cache[key] = (
                self._from_trend(first_year, last_year)
                if self.uses_trend(last_year)
                else self._from_models(first_year, last_year)
            )
        return self._cache[key]

    def _from_trend(self, first_year: int, last_year: int) -> ProjectedClimate:
        weather, shift_c = self._trend.extend_to((first_year + last_year) / 2)
        return ProjectedClimate(
            targets=(ClimateTarget(TREND_TARGET_SOURCE, IndicatorTable.from_weather(weather)),),
            climate=climate_from_weather(
                weather, warming_c=shift_c, method=ClimateMethod.TREND, source=TREND_SOURCE
            ),
            weathers=((TREND_SOURCE, weather),),
        )

    def _observed_base(self, reference: YearRange) -> DailyWeather:
        """The observed weather a model's change is added to: the NASA POWER years of the
        model's reference period when the farm has them, else the most recent years moved by
        the observed trend to the middle of that period (see the module docstring)."""
        weather = self._farm_weather
        if weather.first_year <= reference.first and reference.last <= weather.last_year:
            return weather.between(reference.first, reference.last)
        moved, _ = self._trend.extend_to((reference.first + reference.last) / 2)
        return moved

    def _from_models(self, first_year: int, last_year: int) -> ProjectedClimate:
        if not self._models:
            raise ValueError(
                f"Cycle {first_year}-{last_year} au-delà de {SHORT_TERM_HORIZON_YEARS} ans : "
                "il faut des modèles climatiques"
            )
        recent = self._farm_weather.between(RECENT_WINDOW.first, RECENT_WINDOW.last)
        recent_temperature = mean_temperature(recent)
        recent_summer_rain = mean_summer_rain(recent)
        centre = round((first_year + last_year) / 2)
        targets, climates, weathers = [], [], []
        for model in self._models:
            simulation = model.simulate(
                centre - CLIMATE_WINDOW_BEFORE_YEARS, centre + CLIMATE_WINDOW_AFTER_YEARS
            )
            observed = self._observed_base(simulation.reference)
            weather = apply_deltas(observed, simulation.historical, simulation.future)
            targets.append(ClimateTarget(model.name, IndicatorTable.from_weather(weather)))
            weathers.append((model.name, weather))
            climates.append(
                climate_from_weather(
                    weather,
                    warming_c=mean_temperature(weather) - recent_temperature,
                    method=ClimateMethod.MODELS,
                    source=model.name,
                    summer_rain_change_pct=percent_change(
                        mean_summer_rain(weather), recent_summer_rain
                    ),
                    models=(model.name,),
                )
            )
        source = self._models_label or (
            f"NEX-GDDP-CMIP6 (deltas, moyenne de {len(climates)} modèles)"
        )
        return ProjectedClimate(
            targets=tuple(targets),
            climate=average_climates(climates, method=ClimateMethod.MODELS, source=source),
            weathers=tuple(weathers),
        )
