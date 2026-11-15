"""Three FICTITIOUS climate models standing in for NEX-GDDP-CMIP6 (field_shift.py, _modele_fictif).

Each sees the farm 1 °C too warm (an error the delta method cancels), warms by `warming_factor` ×
0.04 °C a year since 1985–2014 and changes the rain. The real files (AWS, no account) weigh
hundreds of MB per model: they are prepared offline, not read on each request.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from field_shift.algorithm.climate.target_climate_projector import ModelSimulation
from field_shift.algorithm.config.climate import MODEL_BASELINE
from field_shift.algorithm.weather.daily_weather import DailyWeather

BIAS_C: Final = 1.0
BASE_WARMING_C_PER_YEAR: Final = 0.04
BASELINE_CENTRE: Final = (MODEL_BASELINE.first + MODEL_BASELINE.last) / 2


@dataclass(frozen=True)
class DemoModelSpec:
    name: str
    warming_factor: float
    rain_ratio: float


DEMO_MODEL_SPECS: Final = (
    DemoModelSpec("modèle A (fictif)", warming_factor=0.8, rain_ratio=1.05),
    DemoModelSpec("modèle B (fictif)", warming_factor=1.0, rain_ratio=1.00),
    DemoModelSpec("modèle C (fictif)", warming_factor=1.3, rain_ratio=0.92),
)


class DemoClimateModel:
    """A fictitious climate model built on the weather of the farm."""

    def __init__(self, spec: DemoModelSpec, farm_weather: DailyWeather) -> None:
        self.name = spec.name
        self._spec = spec
        self._historical = farm_weather.between(
            MODEL_BASELINE.first, MODEL_BASELINE.last
        ).shifted_by(BIAS_C)

    def simulate(self, first_year: int, last_year: int) -> ModelSimulation:
        warming = (
            self._spec.warming_factor
            * BASE_WARMING_C_PER_YEAR
            * ((first_year + last_year) / 2 - BASELINE_CENTRE)
        )
        future = self._historical.shifted_by(warming)
        return ModelSimulation(
            self._historical,
            future.with_values(rain=self._historical.rain * self._spec.rain_ratio),
        )


def demo_climate_models(farm_weather: DailyWeather) -> list[DemoClimateModel]:
    return [DemoClimateModel(spec, farm_weather) for spec in DEMO_MODEL_SPECS]
