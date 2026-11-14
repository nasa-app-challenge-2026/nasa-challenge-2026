"""The water of a rotation, as the planner sees it.

Two numbers come from the water model, for every cycle:
  - the water score of a chain (criterion `eau`, 0 to 1): the higher, the less the chain depends
    on water that is getting scarce. It is computed for the whole chain, with its sowing and
    harvest dates and its cover crops;
  - the water pressure of the farm (0 to 1): how scarce water is there. It is the water risk of
    step 8, which gives more weight to the criterion `eau`.

The model itself is not here: `algorithm/` computes without the network. It is given when the
algorithm is built (see `data_access/field_shift_eau.py`, which runs the `water_use` module: a
daily soil water balance on the weather of the cycle, with the soil and the slope of the place).
With several climate models, a chain gets one score per model: the mean and the worst are kept.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from field_shift.algorithm.chain.chain_step import ChainStep
from field_shift.algorithm.sources.data_source import DataSource
from field_shift.algorithm.weather.daily_weather import DailyWeather


@dataclass(frozen=True)
class WaterScore:
    """The water score of one chain during one cycle.

    note        0 to 1: the mean of the climate models (the criterion `eau`)
    worst       the score with the worst climate model (= `note` with one weather)
    sub_scores  the four parts of the score, 0 to 1 (A sobriety, B resistance, C rain kept,
                D water left at sowing)
    figures     readable numbers: water demand, missing water, irrigation (mm a year), share of
                the rain kept (%), water in the soil at sowing (mm)
    alerts      what the farmer should know about the result
    by_model    the score with each climate model
    """

    note: float
    worst: float
    sub_scores: Mapping[str, float] = field(default_factory=dict)
    figures: Mapping[str, float] = field(default_factory=dict)
    alerts: tuple[str, ...] = ()
    by_model: tuple[tuple[str, float], ...] = ()


@dataclass(frozen=True)
class WaterPressure:
    """The water pressure of the farm during one cycle.

    pressure    0 (water is not scarce) to 1 (very dry): the mean of the climate models
    worst       the pressure with the worst climate model
    components  what it is made of, each from 0 to 1 (aridity, summer rain drop, groundwater,
                measured stress)
    missing     the components no source could give (the others share their weight)
    sources     where each component comes from
    aridity_index  rain / reference evapotranspiration of the cycle
    aridity_class  "humide", "subhumide sec", "semi-aride"...
    """

    pressure: float
    worst: float
    components: Mapping[str, float] = field(default_factory=dict)
    missing: tuple[str, ...] = ()
    sources: Mapping[str, str] = field(default_factory=dict)
    aridity_index: float | None = None
    aridity_class: str = ""


class CycleWater(Protocol):
    """The water model on the weather of one cycle."""

    @property
    def pressure(self) -> WaterPressure: ...

    def score(
        self,
        steps: Sequence[ChainStep],
        start: float,
        end: float,
        *,
        irrigated: bool,
        partial: bool,
    ) -> WaterScore | None:
        """The water score of a chain: `steps` are its crops and its covers, from `start` (when
        the field becomes free) to `end` (absolute months).

        None means the criterion is not known: it is then left out of the score of the chain. A
        model may answer None for a `partial` chain (one the search is still building).
        Raises ValueError when a crop of the chain is not known to the model.
        """
        ...


#: A daily weather of the cycle with the name of what it comes from (a climate model, or NASA
#: POWER for a cycle in the short term).
NamedWeather = tuple[str, DailyWeather]


class WaterModel(Protocol):
    """The water model of one place (its soil and its slope are read once).

    source  what the model is and whether its data are real (shown to the farmer)
    """

    source: DataSource

    def for_cycle(self, weathers: Sequence[NamedWeather]) -> CycleWater:
        """The model on the weather of a cycle: one weather in the short term, one per climate
        model beyond."""
        ...
