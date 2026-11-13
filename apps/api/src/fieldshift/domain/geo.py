"""Geographic primitives. Coordinates are decimal degrees on the WGS84 datum."""

from __future__ import annotations

from dataclasses import dataclass

MIN_LATITUDE = -90.0
MAX_LATITUDE = 90.0
MIN_LONGITUDE = -180.0
MAX_LONGITUDE = 180.0


@dataclass(frozen=True, slots=True)
class GeoPoint:
    """A position on Earth: latitude positive north, longitude positive east."""

    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        if not MIN_LATITUDE <= self.latitude <= MAX_LATITUDE:
            raise ValueError(f"latitude must be within [-90, 90], got {self.latitude}")
        if not MIN_LONGITUDE <= self.longitude <= MAX_LONGITUDE:
            raise ValueError(f"longitude must be within [-180, 180], got {self.longitude}")


@dataclass(frozen=True, slots=True)
class GridCell:
    """The rectangle of a gridded climate product that a location falls into.

    Every point inside the cell receives exactly the same values from the provider, so the cell,
    not the farm, is the real spatial unit of the analysis.
    """

    center: GeoPoint
    latitude_min: float
    latitude_max: float
    longitude_min: float
    longitude_max: float

    @property
    def cell_id(self) -> str:
        """Stable identifier used for cache keys and snapshot file names."""
        return f"lat{self.center.latitude:+08.3f}_lon{self.center.longitude:+09.3f}"

    def contains(self, point: GeoPoint) -> bool:
        return (
            self.latitude_min <= point.latitude <= self.latitude_max
            and self.longitude_min <= point.longitude <= self.longitude_max
        )
