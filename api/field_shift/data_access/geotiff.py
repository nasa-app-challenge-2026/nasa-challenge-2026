"""A small reader of the GeoTIFF the SoilGrids WCS answers: one band of integers or floats,
uncompressed or DEFLATE, in strips or tiles, with the horizontal predictor or not.

Nothing more is needed (no GDAL): the answers are a few pixels around a point.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from typing import Final

import numpy as np

_TYPE_SIZES: Final = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8}
_TYPE_FORMATS: Final = {1: "B", 3: "H", 4: "I", 6: "b", 8: "h", 9: "i", 11: "f", 12: "d"}
#: (sample format, bits) → numpy type, without the byte order.
_DTYPES: Final = {(1, 8): "u1", (1, 16): "u2", (1, 32): "u4", (2, 8): "i1", (2, 16): "i2",
                  (2, 32): "i4", (3, 32): "f4", (3, 64): "f8"}  # fmt: skip
WIDTH, HEIGHT, BITS, COMPRESSION, STRIP_OFFSETS = 256, 257, 258, 259, 273
SAMPLES, ROWS_PER_STRIP, STRIP_COUNTS, PREDICTOR = 277, 278, 279, 317
TILE_WIDTH, TILE_HEIGHT, TILE_OFFSETS, TILE_COUNTS = 322, 323, 324, 325
SAMPLE_FORMAT, PIXEL_SCALE, TIEPOINT, NODATA = 339, 33550, 33922, 42113
NO_COMPRESSION, DEFLATE, DEFLATE_OLD = 1, 8, 32946
HORIZONTAL_PREDICTOR = 2


class GeoTiffError(ValueError):
    """The bytes are not a GeoTIFF this reader understands (message in French)."""


@dataclass(frozen=True)
class GeoGrid:
    """The pixels of one band, and where they are: the top left corner and the size of a pixel
    (in the units of the coordinates, degrees here)."""

    values: np.ndarray
    left: float
    top: float
    pixel_width: float
    pixel_height: float
    nodata: float | None

    def at(self, x: float, y: float) -> float | None:
        """The value of the pixel nearest to the point (None: no data there)."""
        column = int(
            np.clip(np.floor((x - self.left) / self.pixel_width), 0, self.values.shape[1] - 1)
        )
        row = int(
            np.clip(np.floor((self.top - y) / self.pixel_height), 0, self.values.shape[0] - 1)
        )
        value = float(self.values[row, column])
        if self.nodata is not None and value == self.nodata:
            return None
        return value


def _tags(data: bytes) -> tuple[str, dict[int, tuple]]:
    if data[:2] == b"II":
        order = "<"
    elif data[:2] == b"MM":
        order = ">"
    else:
        raise GeoTiffError("ce n’est pas un fichier TIFF")
    (magic,) = struct.unpack(order + "H", data[2:4])
    if magic != 42:
        raise GeoTiffError("TIFF non standard (BigTIFF ?)")
    (offset,) = struct.unpack(order + "I", data[4:8])
    (count,) = struct.unpack(order + "H", data[offset : offset + 2])
    tags: dict[int, tuple] = {}
    for i in range(count):
        entry = data[offset + 2 + 12 * i : offset + 14 + 12 * i]
        tag, kind, n = struct.unpack(order + "HHI", entry[:8])
        size = _TYPE_SIZES.get(kind, 1) * n
        raw = entry[8 : 8 + size] if size <= 4 else None
        if raw is None:
            (where,) = struct.unpack(order + "I", entry[8:12])
            raw = data[where : where + size]
        if kind == 2:
            tags[tag] = (raw.rstrip(b"\x00").decode("latin1"),)
        elif kind in _TYPE_FORMATS:
            tags[tag] = struct.unpack(order + _TYPE_FORMATS[kind] * n, raw)
    return order, tags


def _decoded(chunk: bytes, compression: int) -> bytes:
    if compression == NO_COMPRESSION:
        return chunk
    if compression in (DEFLATE, DEFLATE_OLD):
        return zlib.decompress(chunk)
    raise GeoTiffError(f"compression TIFF {compression} non prise en charge")


def _undo_predictor(block: np.ndarray, predictor: int) -> np.ndarray:
    if predictor == HORIZONTAL_PREDICTOR:
        return np.cumsum(block, axis=1, dtype=block.dtype)  # differences along each row
    return block


def read_geotiff(data: bytes) -> GeoGrid:
    """The first band of a GeoTIFF. Raises GeoTiffError."""
    order, tags = _tags(data)
    try:
        width, height = tags[WIDTH][0], tags[HEIGHT][0]
        bits = tags[BITS][0]
        sample_format = tags.get(SAMPLE_FORMAT, (1,))[0]
        compression = tags.get(COMPRESSION, (NO_COMPRESSION,))[0]
        predictor = tags.get(PREDICTOR, (1,))[0]
        if tags.get(SAMPLES, (1,))[0] != 1:
            raise GeoTiffError("une seule bande attendue")
        dtype = np.dtype(order + _DTYPES[(sample_format, bits)])
        scale, tie = tags[PIXEL_SCALE], tags[TIEPOINT]
    except KeyError as error:
        raise GeoTiffError(f"tag TIFF absent ou type non pris en charge ({error})") from error
    values = np.zeros((height, width), dtype=dtype)
    if TILE_OFFSETS in tags:
        tile_w, tile_h = tags[TILE_WIDTH][0], tags[TILE_HEIGHT][0]
        across = -(-width // tile_w)
        for index, (start, length) in enumerate(
            zip(tags[TILE_OFFSETS], tags[TILE_COUNTS], strict=True)
        ):
            block = np.frombuffer(_decoded(data[start : start + length], compression), dtype=dtype)
            block = _undo_predictor(block.reshape(tile_h, tile_w), predictor)
            top, left = (index // across) * tile_h, (index % across) * tile_w
            rows, cols = min(tile_h, height - top), min(tile_w, width - left)
            values[top : top + rows, left : left + cols] = block[:rows, :cols]
    else:
        rows_per_strip = tags.get(ROWS_PER_STRIP, (height,))[0]
        top = 0
        for start, length in zip(tags[STRIP_OFFSETS], tags[STRIP_COUNTS], strict=True):
            block = np.frombuffer(_decoded(data[start : start + length], compression), dtype=dtype)
            rows = min(rows_per_strip, height - top)
            block = _undo_predictor(block[: rows * width].reshape(rows, width), predictor)
            values[top : top + rows] = block
            top += rows
    nodata = tags.get(NODATA, (None,))[0]
    return GeoGrid(
        values=values,
        left=float(tie[3]) - float(tie[0]) * float(scale[0]),
        top=float(tie[4]) + float(tie[1]) * float(scale[1]),
        pixel_width=float(scale[0]),
        pixel_height=float(scale[1]),
        nodata=None if nodata in (None, "") else float(nodata),
    )
