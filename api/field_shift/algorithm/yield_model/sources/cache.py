"""Atomic JSON caches, strict source validation and 10 MiB HTTP bounds."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import uuid
from decimal import Decimal
from pathlib import Path

from field_shift.algorithm.yield_model.config import CONFIG, CROP_TAXONOMY, is_finite, is_integer
from field_shift.algorithm.yield_model.sources.climate_validation import validate_climate_seasons

MAX_HTTP_RESPONSE_BYTES = 10 * 1024 * 1024


def validate_bbox(bbox):
    if (not isinstance(bbox, dict)
        or not all(is_finite(bbox.get(k)) for k in ("minLon", "minLat", "maxLon", "maxLat"))
        or bbox["minLon"] < -180 or bbox["maxLon"] > 180
        or bbox["minLat"] < -90 or bbox["maxLat"] > 90
        or bbox["minLon"] >= bbox["maxLon"] or bbox["minLat"] >= bbox["maxLat"]):
        raise ValueError("Boîte englobante (bbox) invalide ou hors bornes.")
    return bbox


def same_bbox(a, b):
    return (isinstance(a, dict) and isinstance(b, dict)
            and all(is_finite(a.get(k)) and is_finite(b.get(k))
                    and abs(a[k] - b[k]) < 1e-8
                    for k in ("minLon", "minLat", "maxLon", "maxLat")))


def number_text(value):
    """JSON.stringify-compatible spelling for geographical cache keys and URLs."""
    if value == 0:
        return "0"
    text = json.dumps(value, allow_nan=False)
    if "e" in text.lower() and 1e-6 <= abs(value) < 1e21:
        return format(Decimal(text), "f").rstrip("0").rstrip(".") if "." in format(Decimal(text), "f") else format(Decimal(text), "f")
    return re.sub(r"e([+-])0+(\d+)", r"e\1\2", text.removesuffix(".0"))


def bbox_cache_key(bbox):
    validate_bbox(bbox)
    text = "[" + ",".join(number_text(bbox[k]) for k in
                          ("minLon", "minLat", "maxLon", "maxLat")) + "]"
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _year_entries(value):
    return (isinstance(value, dict) and 0 < len(value) <= 21
            and all(re.fullmatch(r"\d{4}", str(y)) and 1981 <= int(y) <= 2030 for y in value))


def _valid_payload(namespace, data):
    if namespace == "nasa-power":
        return bool(validate_climate_seasons(data.get("seasons")))
    if namespace in ("modis-ndvi", "crop-history"):
        validate_bbox(data.get("bbox"))
        def grid_size(value):
            return is_integer(value) and 4 <= value <= 128
        if namespace == "crop-history":
            size, years = data.get("gridSize"), data.get("cropIdsByYear")
            return (grid_size(size) and _year_entries(years)
                    and all(isinstance(row, list) and len(row) in (0, size ** 2)
                            and all(c is None or isinstance(c, str) and c in CROP_TAXONOMY for c in row)
                            for row in years.values()))
        rows, cols, years = data.get("nrows"), data.get("ncols"), data.get("gridsByYear")
        def band_valid(band):
            return (isinstance(band, list) and len(band) == rows * cols
                    and all(v is None or is_finite(v) and -0.2 <= v <= 1 for v in band))
        return (grid_size(rows) and grid_size(cols) and _year_entries(years)
                and all(isinstance(grid, dict) and band_valid(grid.get("pixels"))
                        and (not grid.get("eviPixels") or band_valid(grid["eviPixels"]))
                        for grid in years.values()))
    if namespace == "cmip6-projection":
        return bool(validate_climate_seasons(data.get("projectedSeasons"))) and isinstance(data.get("baselineStats"), dict)
    if namespace == "nass-quickstats":
        return isinstance(data.get("yieldsByCropYear"), dict)
    return True


def _cache_path(namespace, key):
    for segment in (namespace, key):
        if (not isinstance(segment, str) or not re.fullmatch(r"[A-Za-z0-9._+-]+", segment)
            or ".." in segment
            or re.match(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..+)?$", segment, re.I)):
            raise ValueError(f"Clé ou espace de cache invalide : {namespace}/{key}")
    root = Path(CONFIG["cacheDir"]).resolve()
    target = (root / namespace / f"{key}.json").resolve()
    if not target.is_relative_to(root / namespace) or not (root / namespace).is_relative_to(root):
        raise ValueError("Accès hors du dossier de cache refusé.")
    return target


def read_cache(namespace, key, validator=None):
    path = _cache_path(namespace, key)
    try:
        if path.stat().st_size > MAX_HTTP_RESPONSE_BYTES:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(data, dict) or not _valid_payload(namespace, data)
            or validator is not None and not validator(data)):
            return None
        return data
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return None


def write_cache(namespace, key, data):
    target = _cache_path(namespace, key)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f"{target.name}.{os.getpid()}.{uuid.uuid4()}.tmp")
    try:
        temporary.write_text(json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return data


def _number(value):
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError) as error:
        raise ValueError("Valeur numérique invalide.") from error
    if not math.isfinite(number):
        raise ValueError("Valeur numérique non finie.")
    return number


def region_cell_key(lat, lon, step=0.1):
    lat, lon = _number(lat), _number(lon)
    if not is_finite(step) or not 0 < step <= 1:
        raise ValueError("Pas de cellule invalide.")
    if not -80 <= lat <= 80 or not -180 <= lon <= 180:
        raise ValueError("Coordonnées géographiques invalides ou hors zone agricole.")
    return f"lat{math.floor(lat / step + 0.5) * step:.2f}_lon{math.floor(lon / step + 0.5) * step:.2f}"


def validate_historical_sampling_params(*, lat, lon, start_year=None, end_year=None, grid_size=64, half_window_km=8):
    lat, lon = _number(lat), _number(lon)
    start_year = CONFIG["sampling"]["startYear"] if start_year is None else _number(start_year)
    end_year = CONFIG["sampling"]["endYear"] if end_year is None else _number(end_year)
    grid_size, half_window_km = _number(grid_size), _number(half_window_km)
    if not -80 <= lat <= 80 or not -180 <= lon <= 180:
        raise ValueError("Coordonnées géographiques invalides ou hors zone agricole [-80°, +80°].")
    if not (is_integer(start_year) and is_integer(end_year) and 1981 <= start_year <= end_year <= 2030 and end_year - start_year <= 20):
        raise ValueError("Plage d'années historiques invalide.")
    if not is_integer(grid_size) or not 4 <= grid_size <= 128:
        raise ValueError("Taille de grille invalide.")
    if not 1 <= half_window_km <= 25:
        raise ValueError("Demi-fenêtre régionale invalide.")
    return {"lat": lat, "lon": lon, "startYear": int(start_year), "endYear": int(end_year),
            "gridSize": int(grid_size), "halfWindowKm": half_window_km}


def read_bounded_buffer(response, max_bytes=MAX_HTTP_RESPONSE_BYTES):
    headers = getattr(response, "headers", {})
    try:
        content_length = float(headers.get("content-length", headers.get("Content-Length", 0)) or 0)
    except (ValueError, TypeError):
        content_length = 0
    try:
        if content_length > max_bytes:
            raise ValueError("Réponse HTTP trop volumineuse.")
        chunks, total = [], 0
        while True:
            chunk = response.read(min(65536, max_bytes + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ValueError("Flux HTTP interrompu : dépassement de la limite de taille.")
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        if hasattr(response, "close"):
            response.close()


def read_bounded_json(response, max_bytes=MAX_HTTP_RESPONSE_BYTES):
    return json.loads(read_bounded_buffer(response, max_bytes).decode("utf-8"))
