"""Put a year reported by the farmer next to what the gridded data show for that year.

The result is a position among the analysed years, never a verdict on the observation: a
farm can live a storm or a frost pocket that a ~50 km grid cell smooths out.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from fieldshift.domain.agronomy.farm import FarmObservation, ObservationTopic
from fieldshift.domain.climate.indicators import IndicatorSeries

TOPIC_INDICATORS: Mapping[ObservationTopic, tuple[str, ...]] = {
    ObservationTopic.FROST: (
        "last_spring_frost_doy",
        "first_fall_frost_doy",
        "frost_free_season_days",
    ),
    ObservationTopic.HARVEST_WEATHER: (
        "wet_days_june_july",
        "haymaking_days_june_july",
        "heavy_precipitation_days",
    ),
    ObservationTopic.WATER: (
        "precipitation_summer_mm",
        "max_dry_spell_growing_season_days",
        "climatic_water_balance_growing_season_mm",
    ),
}

SCALE_NOTE_FR = (
    "Position de l'année signalée parmi les années analysées, à l'échelle de la cellule NASA. "
    "Un écart avec l'observation peut venir de phénomènes locaux (orages, fonds de vallée) "
    "que la cellule ne résout pas : l'observation reste une information précieuse."
)


class CheckStatus(StrEnum):
    COMPARED = "compared"
    NO_YEAR = "no_year"
    YEAR_NOT_ANALYSED = "year_not_analysed"
    TOPIC_NOT_COVERED = "topic_not_covered"


@dataclass(frozen=True, slots=True)
class YearPosition:
    indicator_id: str
    value: float | None
    median: float | None
    years_higher: int
    years_lower: int
    years_compared: int


@dataclass(frozen=True, slots=True)
class ObservationCheck:
    observation: FarmObservation
    status: CheckStatus
    positions: tuple[YearPosition, ...]


def _position(series: IndicatorSeries, year: int) -> YearPosition:
    value = dict(zip(series.years, series.values, strict=True))[year]
    others = [v for y, v in zip(series.years, series.values, strict=True) if v is not None]
    return YearPosition(
        indicator_id=series.definition.id,
        value=value,
        median=series.summary.median if series.summary else None,
        years_higher=sum(other > value for other in others) if value is not None else 0,
        years_lower=sum(other < value for other in others) if value is not None else 0,
        years_compared=len(others),
    )


def check_observations(
    observations: Sequence[FarmObservation], series_by_id: Mapping[str, IndicatorSeries]
) -> tuple[ObservationCheck, ...]:
    checks: list[ObservationCheck] = []
    for observation in observations:
        indicator_ids = TOPIC_INDICATORS.get(observation.topic)
        if indicator_ids is None:
            checks.append(ObservationCheck(observation, CheckStatus.TOPIC_NOT_COVERED, ()))
            continue
        if observation.year is None:
            checks.append(ObservationCheck(observation, CheckStatus.NO_YEAR, ()))
            continue
        analysed_years = series_by_id[indicator_ids[0]].years
        if observation.year not in analysed_years:
            checks.append(ObservationCheck(observation, CheckStatus.YEAR_NOT_ANALYSED, ()))
            continue
        positions = tuple(
            _position(series_by_id[indicator_id], observation.year)
            for indicator_id in indicator_ids
        )
        checks.append(ObservationCheck(observation, CheckStatus.COMPARED, positions))
    return tuple(checks)
