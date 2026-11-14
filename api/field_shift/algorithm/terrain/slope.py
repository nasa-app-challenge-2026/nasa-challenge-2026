"""Slope and slope length of a section from the elevations of a digital elevation model.

    1. the elevations are sampled at the centres of a 9 × 9 grid over the section, on a window at
       least three cells of the elevation model wide (a section smaller than a cell still gets a
       slope: the one of the ground around it);
    2. the points inside the section are kept (the whole window when fewer than 9 are inside);
    3. a plane z = a·x + b·y + c is fitted on them by least squares: the slope is |∇z| = √(a² + b²)
       and the water runs along −∇z;
    4. the slope length is the length of the section along that direction: the distance the
       runoff travels before leaving the field (RUSLE bounds it at 1000 ft, see `erosion`).

This treats the section as one plane: a field with a hollow or two opposite slopes gets their
mean slope. The elevation model is Copernicus DEM GLO-90 (90 m cells): within-field relief
smaller than a cell is not seen.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from field_shift.algorithm.config.soil_protection import (
    MIN_POINTS_INSIDE,
    MIN_TERRAIN_WINDOW_M,
    TERRAIN_GRID_SIDE,
)
from field_shift.algorithm.terrain.section_shape import Point, SectionShape

#: Below this gradient the ground is flat: no direction of the runoff.
FLAT_GRADIENT = 1e-6


@dataclass(frozen=True)
class TerrainSample:
    """The points where the elevations are read: local (x, y) in metres and (lon, lat).

    inside  True when the points are those inside the section, False when the whole window is
            used (a section too small for the grid)
    """

    local: tuple[Point, ...]
    geographic: tuple[Point, ...]
    inside: bool


@dataclass(frozen=True)
class TerrainEstimate:
    """The slope of a section and how it was obtained."""

    slope_pct: float
    slope_length_m: float
    points: int
    inside: bool


def terrain_sample(shape: SectionShape) -> TerrainSample:
    """The grid of points to read the elevations at (see the module documentation)."""
    x_min, y_min, x_max, y_max = shape.local_bounds
    side = max(x_max - x_min, y_max - y_min, MIN_TERRAIN_WINDOW_M)
    cx, cy = (x_min + x_max) / 2, (y_min + y_max) / 2
    # Points at the centre of the cells of a 9 × 9 grid: none falls on the outline of a square.
    steps = (np.arange(TERRAIN_GRID_SIDE) + 0.5) / TERRAIN_GRID_SIDE * side - side / 2
    grid = [(cx + float(dx), cy + float(dy)) for dy in steps for dx in steps]
    inside = [point for point in grid if shape.contains(*point)]
    points = inside if len(inside) >= MIN_POINTS_INSIDE else grid
    return TerrainSample(
        local=tuple(points),
        geographic=tuple(shape.to_geographic(x, y) for x, y in points),
        inside=points is inside,
    )


def fitted_plane(points: Sequence[Point], elevations: Sequence[float]) -> tuple[float, Point]:
    """(slope in %, unit downslope direction) of the plane fitted on the elevations."""
    if len(points) != len(elevations) or len(points) < 3:
        raise ValueError("at least 3 points, each with its elevation, are needed for a plane")
    design = np.array([[x, y, 1.0] for x, y in points])
    (a, b, _), *_ = np.linalg.lstsq(design, np.asarray(elevations, dtype=float), rcond=None)
    gradient = math.hypot(a, b)
    if gradient < FLAT_GRADIENT:
        return 0.0, (1.0, 0.0)
    return 100 * gradient, (-a / gradient, -b / gradient)


def terrain_of(
    shape: SectionShape, sample: TerrainSample, elevations: Sequence[float]
) -> TerrainEstimate:
    """Slope and slope length of the section from the elevations read at `sample`."""
    slope_pct, downslope = fitted_plane(sample.local, elevations)
    return TerrainEstimate(
        slope_pct=slope_pct,
        slope_length_m=shape.extent_along(downslope),
        points=len(sample.local),
        inside=sample.inside,
    )
