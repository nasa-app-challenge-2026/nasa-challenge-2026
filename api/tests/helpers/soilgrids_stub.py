"""The SoilGrids WCS of the tests: a 1 × 1 GeoTIFF per property and layer, from memory."""

from __future__ import annotations

import struct
from collections.abc import Callable, Mapping

import httpx

WCS_HOST = "maps.isric.org"


#: (tag, TIFF type) of the image file directory, in order; the values are filled below.
_TAGS = ((256, 3), (257, 3), (258, 3), (259, 3), (273, 4), (277, 3), (278, 3), (279, 4),
         (339, 3), (33550, 12), (33922, 12))  # fmt: skip


def geotiff(value: int, lon: float, lat: float, size_deg: float = 0.003) -> bytes:
    """An uncompressed GeoTIFF of one signed 16-bit pixel centred on the point."""
    scale = struct.pack("<3d", size_deg, size_deg, 0.0)
    tiepoint = struct.pack("<6d", 0.0, 0.0, 0.0, lon - size_deg / 2, lat + size_deg / 2, 0.0)
    scale_at = 8 + 2 + 12 * len(_TAGS) + 4  # after the header and the directory
    tie_at = scale_at + len(scale)
    pixel_at = tie_at + len(tiepoint)
    values = {256: 1, 257: 1, 258: 16, 259: 1, 273: pixel_at, 277: 1, 278: 1, 279: 2,
              339: 2, 33550: scale_at, 33922: tie_at}  # fmt: skip
    counts = {33550: 3, 33922: 6}
    directory = struct.pack("<H", len(_TAGS))
    for tag, kind in _TAGS:
        directory += struct.pack("<HHI", tag, kind, counts.get(tag, 1))
        if kind == 3:
            directory += struct.pack("<HH", values[tag], 0)
        else:
            directory += struct.pack("<I", values[tag])
    header = b"II" + struct.pack("<HI", 42, 8)
    return header + directory + struct.pack("<I", 0) + scale + tiepoint + struct.pack("<h", value)


def wcs_answer(
    raw: Mapping[str, Mapping[str, int | None]] | Callable[[str, str], int | None],
) -> Callable[[httpx.Request], httpx.Response]:
    """Answers a WCS GetCoverage with the raw value (mapped units: g/kg, dg/kg, pH × 10) of
    `raw[property][layer]`; None or 0 is a point without soil."""

    def handle(request: httpx.Request) -> httpx.Response:
        coverage = request.url.params["COVERAGEID"]
        name, label, _ = coverage.split("_")
        value = raw(name, label) if callable(raw) else raw[name].get(label)
        subsets = request.url.params.get_list("SUBSET")
        lon_low, lon_high = (float(v) for v in subsets[0][5:-1].split(","))
        lat_low, lat_high = (float(v) for v in subsets[1][4:-1].split(","))
        lon, lat = (lon_low + lon_high) / 2, (lat_low + lat_high) / 2
        return httpx.Response(200, content=geotiff(value or 0, lon, lat))

    return handle
