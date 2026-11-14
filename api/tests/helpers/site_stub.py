"""Test data for the soil protection: a complete set of conditions, a data provider that answers
from memory, and section outlines. The tests never use the network."""

from __future__ import annotations

import math
from collections.abc import Collection, Mapping
from dataclasses import replace

from field_shift.algorithm.config.soil_protection import EARTH_RADIUS_M
from field_shift.algorithm.soil_protection.erosion import (
    erodibility_from_texture,
    erosivity_from_annual_rain,
)
from field_shift.algorithm.soil_protection.site_conditions import SiteConditions, SiteReading
from field_shift.algorithm.terrain.section_shape import SectionShape
from field_shift.data_access.site_data import SiteDataUnavailableError
from field_shift.data_access.site_readers import SourceError

#: A loam on a gentle slope, in southern Quebec, at full vigour and dry: what the tests reason on.
#: Ksat, K and R are not here: the model computes them when they are not given.
TEST_VALUES: Mapping[str, float] = {
    "slope_pct": 3.0,
    "slope_length_m": 60.0,
    "sand_pct": 40.0,
    "clay_pct": 20.0,
    "organic_matter_pct": 3.0,
    "support_practice_factor": 1.0,
    "ndvi": 0.85,
    "root_activity": 1.0,
    "annual_rain_mm": 1000.0,
    "storm_intensity_mm_h": 25.0,
    "soil_saturation": 0.0,
}
TEST_ORIGIN = "service de test"

BASE_SITE = SiteConditions(
    **TEST_VALUES,
    ksat_mm_h=10.0,
    k_factor=erodibility_from_texture(40, 40, 20, 3),
    r_factor=erosivity_from_annual_rain(1000),
)


def site(**changes: float) -> SiteConditions:
    """The test conditions with some values changed."""
    return replace(BASE_SITE, **changes)


class FixedSiteData:
    """A data provider answering `values` (TEST_VALUES by default) and remembering what it was
    asked; `failing` names datasets that fail."""

    def __init__(
        self, values: Mapping[str, float] | None = None, failing: Collection[str] = ()
    ) -> None:
        self.values = dict(TEST_VALUES if values is None else values)
        self.failing = tuple(failing)
        self.calls: list[tuple[SectionShape, frozenset[str]]] = []

    def site_readings(self, shape: SectionShape, needed: Collection[str]) -> list[SiteReading]:
        self.calls.append((shape, frozenset(needed)))
        if self.failing:
            raise SiteDataUnavailableError(
                [SourceError(dataset, "le service a répondu 503") for dataset in self.failing]
            )
        return [
            SiteReading(key, self.values[key], TEST_ORIGIN) for key in needed if key in self.values
        ]


def square(lat: float = 45.5, lon: float = -73.0, side_m: float = 300.0) -> dict:
    """A GeoJSON Polygon: a square of `side_m` metres centred on (lat, lon)."""
    half_lat = math.degrees(side_m / 2 / EARTH_RADIUS_M)
    half_lon = half_lat / math.cos(math.radians(lat))
    ring = [
        [lon - half_lon, lat - half_lat],
        [lon + half_lon, lat - half_lat],
        [lon + half_lon, lat + half_lat],
        [lon - half_lon, lat + half_lat],
        [lon - half_lon, lat - half_lat],
    ]
    return {"type": "Polygon", "coordinates": [ring]}
