"""Bounded native decoders for NumPy grids and uncompressed thematic U8 TIFF."""
import ast
import math
import struct

MAX_GRID_DIMENSION = 512
MAX_BANDS = 8
_DTYPES = {"<i2": "h", "<u2": "H", "|u1": "B", "<u1": "B", "<f4": "f"}


def parse_npy_grid(buffer, *, expected_width=None, expected_height=None):
    data = bytes(buffer)
    if len(data) < 16 or data[:6] != b"\x93NUMPY":
        raise ValueError("Format .npy invalide (en-tête NUMPY manquant).")
    major = data[6]
    if major not in (1, 2):
        raise ValueError("Version d'en-tête .npy non supportée.")
    header_offset = 10 if major == 1 else 12
    header_len = struct.unpack_from("<H" if major == 1 else "<I", data, 8)[0]
    offset = header_offset + header_len
    if header_len > 4096 or offset > len(data):
        raise ValueError("En-tête .npy corrompu ou hors bornes.")
    try:
        header = ast.literal_eval(data[header_offset:offset].decode("latin1").strip())
        dtype, shape = header["descr"], header["shape"]
    except (ValueError, SyntaxError, KeyError, TypeError) as error:
        raise ValueError("En-tête .npy non reconnu.") from error
    if header.get("fortran_order") is not False:
        raise ValueError("Grille .npy en ordre Fortran ou ordre inconnu non supportée.")
    if dtype not in _DTYPES:
        raise ValueError(f"Type NumPy non supporté : {dtype}")
    if not isinstance(shape, tuple) or len(shape) not in (2, 3) or any(type(d) is not int or d <= 0 for d in shape):
        raise ValueError("Dimensions .npy invalides.")
    bands, height, width = shape if len(shape) == 3 else (1, *shape)
    if bands > MAX_BANDS or max(height, width) > MAX_GRID_DIMENSION:
        raise ValueError("Dimensions .npy hors limites de sécurité.")
    if (expected_width is not None and expected_width != width
        or expected_height is not None and expected_height != height):
        raise ValueError("Dimensions de grille .npy inattendues.")
    fmt = "<" + _DTYPES[dtype]
    count = bands * width * height
    required = count * struct.calcsize(fmt)
    if offset + required > len(data):
        raise ValueError("Buffer .npy tronqué.")
    values = [row[0] for row in struct.iter_unpack(fmt, data[offset:offset + required])]
    pixels = width * height
    return {"shape": [bands, height, width], "descr": dtype, "width": width, "height": height,
            "bands": [values[i * pixels:(i + 1) * pixels] for i in range(bands)]}


def parse_uncompressed_tiff_u8(buffer, *, expected_width=None, expected_height=None):
    data = bytes(buffer)
    if len(data) < 16 or data[:2] != b"II" or struct.unpack_from("<H", data, 2)[0] != 42:
        raise ValueError("GeoTIFF invalide ou big-endian non supporté.")
    def read(fmt, offset):
        if offset < 0 or offset + struct.calcsize(fmt) > len(data):
            raise ValueError("GeoTIFF tronqué ou offset hors bornes.")
        return struct.unpack_from(fmt, data, offset)[0]
    ifd = read("<I", 4)
    entries = read("<H", ifd)
    if entries > 256 or ifd + 2 + 12 * entries > len(data):
        raise ValueError("Table IFD GeoTIFF corrompue ou hors bornes.")
    tags = {}
    for i in range(entries):
        position = ifd + 2 + i * 12
        tag, kind, count = struct.unpack_from("<HHI", data, position)
        fmt = {1: "<B", 2: "<B", 3: "<H", 4: "<I"}.get(kind)
        if not fmt or not 0 < count <= 4096:
            continue
        size = struct.calcsize(fmt)
        start = position + 8 if size * count <= 4 else read("<I", position + 8)
        values = [read(fmt, start + k * size) for k in range(count)]
        tags[tag] = values[0] if count == 1 else values
    def scalar(tag, default=None):
        value = tags.get(tag, default)
        return value[0] if isinstance(value, list) else value
    def array(tag):
        value = tags.get(tag, [])
        return value if isinstance(value, list) else [value]
    width, height = scalar(256), scalar(257)
    if scalar(259, 1) != 1:
        raise ValueError("GeoTIFF compressé : demander compression=NONE.")
    if scalar(277, 1) != 1 or array(258) not in ([], [8]) or scalar(262, 1) == 2 or scalar(339, 1) != 1:
        raise ValueError("GeoTIFF non thématique U8 monocanal rejeté.")
    if not all(type(d) is int and 0 < d <= MAX_GRID_DIMENSION for d in (width, height)):
        raise ValueError("Dimensions GeoTIFF invalides ou hors limites.")
    if (expected_width is not None and expected_width != width
        or expected_height is not None and expected_height != height):
        raise ValueError("Dimensions GeoTIFF inattendues.")
    pixels = [0] * (width * height)
    if 324 in tags:
        tile_width, tile_height = scalar(322, width), scalar(323, height)
        if not 0 < tile_width <= MAX_GRID_DIMENSION * 2 or not 0 < tile_height <= MAX_GRID_DIMENSION * 2:
            raise ValueError("Dimensions de tuile GeoTIFF invalides.")
        across = math.ceil(width / tile_width)
        offsets = array(324)
        if len(offsets) < across * math.ceil(height / tile_height):
            raise ValueError("Tuiles GeoTIFF incomplètes.")
        for i, offset in enumerate(offsets):
            for r in range(tile_height):
                row = i // across * tile_height + r
                if row >= height:
                    break
                for c in range(tile_width):
                    col = i % across * tile_width + c
                    if col >= width:
                        break
                    pixels[row * width + col] = read("<B", offset + r * tile_width + c)
    else:
        offsets, counts = array(273), array(279)
        if not offsets or len(offsets) != len(counts):
            raise ValueError("GeoTIFF invalide : bandes manquantes.")
        output = []
        for offset, count in zip(offsets, counts, strict=True):
            if offset < 0 or offset + count > len(data):
                raise ValueError("Bande GeoTIFF hors bornes du buffer.")
            output.extend(data[offset:offset + count])
        if len(output) < width * height:
            raise ValueError("Bande GeoTIFF tronquée.")
        pixels = output[:width * height]
    return {"width": width, "height": height, "pixels": pixels}
