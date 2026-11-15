"""The FICTITIOUS steps 3 to 7 of field_shift.py, as the `PlaceSources` of a place: the three
fictitious climate models, the fictitious grid of climates around the farm and the fictitious crops
of its twins. The tests compare the algorithm with its reference on them; the server never uses
them (`field_shift/data_access/place_data.py` reads the real ones)."""

from __future__ import annotations

from field_shift.algorithm.sources.data_source import DataSource
from field_shift.algorithm.sources.place_sources import (
    CLIMATE_MODELS_KEY,
    TWINS_KEY,
    PlaceSources,
)
from field_shift.algorithm.weather.daily_weather import DailyWeather
from tests.helpers.demo_climate_models import demo_climate_models
from tests.helpers.demo_twin_atlas import demo_twin_atlas
from tests.helpers.demo_twin_crops import demo_twin_evidence

REFERENCE_SOURCES = (
    DataSource(
        CLIMATE_MODELS_KEY, False, "3 modèles climatiques fictifs (à la place de NEX-GDDP-CMIP6)"
    ),
    DataSource(TWINS_KEY, False, "Grille de climats et cultures des jumeaux fictive"),
)


def reference_place_sources(lat: float, lon: float, farm_weather: DailyWeather) -> PlaceSources:
    """The reference (fictitious) sources of steps 3 to 7 for a farm."""
    return PlaceSources(
        models=demo_climate_models(farm_weather),
        grid=demo_twin_atlas(lat, lon, farm_weather),
        evidence_for=lambda first, last, twins, soil: demo_twin_evidence(first, last, twins),
        sources=REFERENCE_SOURCES,
    )


class ReferencePlaceData:
    """A `PlaceDataProvider` with the reference sources of field_shift.py, whatever the place."""

    def place_sources(self, lat: float, lon: float, farm_weather: DailyWeather) -> PlaceSources:
        return reference_place_sources(lat, lon, farm_weather)
