"""The MERRA-2 grid used by NASA POWER for meteorological parameters.

POWER serves these parameters at their source resolution, 0.5° latitude × 0.625° longitude,
without interpolation (POWER methodology, Release 9 notes). Grid centres sit on multiples of
the steps. Verified empirically on 2026-11-10: points 48.23N 69.80W, 48.00N 70.00W,
47.76N 70.30W and 48.24N 69.69W return identical daily values, while 48.26N 69.80W and
48.23N 69.68W (just across the cell edges) do not.

Requests are sent with the centre of the cell, never with the farm's own coordinates: the
response is the same, the cache key is stable, and the farm position stays private.
"""

from __future__ import annotations

import math

from fieldshift.domain.geo import MAX_LATITUDE, MIN_LATITUDE, GeoPoint, GridCell

MERRA2_LATITUDE_STEP = 0.5
MERRA2_LONGITUDE_STEP = 0.625
SPATIAL_RESOLUTION_FR = "0,5° de latitude × 0,625° de longitude (grille MERRA-2)"


def _snap(value: float, step: float) -> float:
    return round(math.floor(value / step + 0.5) * step, 6)


def merra2_cell(point: GeoPoint) -> GridCell:
    latitude = _snap(point.latitude, MERRA2_LATITUDE_STEP)
    longitude = _snap(point.longitude, MERRA2_LONGITUDE_STEP)
    if longitude >= 180.0:
        longitude -= 360.0
    half_lat = MERRA2_LATITUDE_STEP / 2
    half_lon = MERRA2_LONGITUDE_STEP / 2
    return GridCell(
        center=GeoPoint(latitude, longitude),
        latitude_min=max(MIN_LATITUDE, latitude - half_lat),
        latitude_max=min(MAX_LATITUDE, latitude + half_lat),
        longitude_min=longitude - half_lon,
        longitude_max=longitude + half_lon,
    )
