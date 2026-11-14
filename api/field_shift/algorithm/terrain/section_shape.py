"""The shape of a section: a polygon of (longitude, latitude) points, as GeoJSON writes it.

A section is small (a few hectares to a few km²): its points are projected on a plane tangent to
the Earth at the middle of the section (equirectangular projection), which is exact to a fraction
of a percent at that size. Area, centroid, "is this point inside" and lengths are computed there.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cached_property

from field_shift.algorithm.config.soil_protection import EARTH_RADIUS_M

#: Most vertices accepted in the outline of a section.
MAX_VERTICES = 500
#: Smallest area accepted (m²): below it the outline is a point or a line.
MIN_AREA_M2 = 1.0
M2_PER_HA = 10_000

Point = tuple[float, float]


class ShapeError(ValueError):
    """The outline of a section is not a usable polygon (message in French)."""


def _segments_cross(a: Point, b: Point, c: Point, d: Point) -> bool:
    """True when the segments ab and cd cross at a point inside both (not at an end)."""

    def side(p: Point, q: Point, r: Point) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    d1, d2 = side(c, d, a), side(c, d, b)
    d3, d4 = side(a, b, c), side(a, b, d)
    return d1 * d2 < 0 and d3 * d4 < 0


@dataclass(frozen=True)
class SectionShape:
    """The outline of a section: a closed ring of (lon, lat) points, the first equal to the last."""

    ring: tuple[Point, ...]

    @classmethod
    def from_coordinates(cls, positions: Sequence[Sequence[float]]) -> SectionShape:
        """The shape of a GeoJSON ring ([[lon, lat], …], closed).

        Raises ShapeError for a ring that is open, too short, too long, outside the valid
        coordinates, across the antimeridian, self-intersecting or without area.
        """
        ring = tuple((float(p[0]), float(p[1])) for p in positions)
        if len(ring) < 4:
            raise ShapeError("le contour d’une section doit avoir au moins 4 positions")
        if len(ring) > MAX_VERTICES + 1:
            raise ShapeError(f"le contour d’une section a au plus {MAX_VERTICES} sommets")
        if ring[0] != ring[-1]:
            raise ShapeError("le contour doit être fermé : la dernière position = la première")
        for lon, lat in ring:
            if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                raise ShapeError(f"position hors des coordonnées valides : [{lon}, {lat}]")
        lons = [lon for lon, _ in ring]
        if max(lons) - min(lons) > 180:
            raise ShapeError("une section ne peut pas traverser l’antiméridien (180°)")
        shape = cls(ring)
        if len(set(ring)) < 3:
            raise ShapeError("le contour doit avoir au moins 3 sommets distincts")
        if shape.is_self_intersecting:
            raise ShapeError("le contour se croise lui-même")
        if shape.area_m2 < MIN_AREA_M2:
            raise ShapeError("le contour n’a pas de surface")
        return shape

    # --- Local plane ------------------------------------------------------------------------------

    @cached_property
    def _origin(self) -> Point:
        vertices = self.ring[:-1]
        return (
            sum(lon for lon, _ in vertices) / len(vertices),
            sum(lat for _, lat in vertices) / len(vertices),
        )

    def to_local(self, lon: float, lat: float) -> Point:
        """(x, y) in metres east and north of the middle of the section."""
        lon0, lat0 = self._origin
        x = EARTH_RADIUS_M * math.radians(lon - lon0) * math.cos(math.radians(lat0))
        y = EARTH_RADIUS_M * math.radians(lat - lat0)
        return x, y

    def to_geographic(self, x: float, y: float) -> Point:
        """(lon, lat) of a point given in metres east and north of the middle of the section."""
        lon0, lat0 = self._origin
        lon = lon0 + math.degrees(x / (EARTH_RADIUS_M * math.cos(math.radians(lat0))))
        lat = lat0 + math.degrees(y / EARTH_RADIUS_M)
        return lon, lat

    @cached_property
    def local_ring(self) -> tuple[Point, ...]:
        return tuple(self.to_local(lon, lat) for lon, lat in self.ring)

    # --- Measures ---------------------------------------------------------------------------------

    @cached_property
    def _signed_area_m2(self) -> float:
        ring = self.local_ring
        return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in itertools.pairwise(ring)) / 2

    @property
    def area_m2(self) -> float:
        return abs(self._signed_area_m2)

    @property
    def area_ha(self) -> float:
        return self.area_m2 / M2_PER_HA

    @cached_property
    def centroid(self) -> Point:
        """(lon, lat) of the centre of mass of the section: where its soil, rain and satellite
        measures are read."""
        ring, area = self.local_ring, self._signed_area_m2
        cx = cy = 0.0
        for (x1, y1), (x2, y2) in itertools.pairwise(ring):
            cross = x1 * y2 - x2 * y1
            cx += (x1 + x2) * cross
            cy += (y1 + y2) * cross
        return self.to_geographic(cx / (6 * area), cy / (6 * area))

    @property
    def is_self_intersecting(self) -> bool:
        ring = self.local_ring
        edges = list(itertools.pairwise(ring))
        for i, (a, b) in enumerate(edges):
            for c, d in edges[i + 2 :]:
                if _segments_cross(a, b, c, d):
                    return True
        return False

    def contains(self, x: float, y: float) -> bool:
        """True when the local point (x, y) is inside the section (ray casting)."""
        inside = False
        ring = self.local_ring
        for (x1, y1), (x2, y2) in itertools.pairwise(ring):
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                inside = not inside
        return inside

    @property
    def local_bounds(self) -> tuple[float, float, float, float]:
        """(x min, y min, x max, y max) of the section on the local plane."""
        xs = [x for x, _ in self.local_ring]
        ys = [y for _, y in self.local_ring]
        return min(xs), min(ys), max(xs), max(ys)

    def extent_along(self, direction: Point) -> float:
        """Length of the section along a unit direction (m): from its first to its last point
        seen in that direction."""
        ux, uy = direction
        projections = [x * ux + y * uy for x, y in self.local_ring]
        return max(projections) - min(projections)
