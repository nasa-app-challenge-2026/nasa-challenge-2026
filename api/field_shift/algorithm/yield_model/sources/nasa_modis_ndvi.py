"""Regional 64x64 MODIS MOD13Q1 v061 NDVI/EVI tiles and HLS 30m STAC metadata."""

from __future__ import annotations

import json
import math
from urllib.parse import quote, urlencode

from field_shift.algorithm.yield_model.config import CONFIG, is_finite, js_round
from field_shift.algorithm.yield_model.sources import http
from field_shift.algorithm.yield_model.sources.cache import (
    bbox_cache_key,
    number_text,
    read_bounded_buffer,
    read_bounded_json,
    read_cache,
    region_cell_key,
    same_bbox,
    validate_bbox,
    validate_historical_sampling_params,
    write_cache,
)
from field_shift.algorithm.yield_model.sources.raster_parser import parse_npy_grid

MODIS_SCALE_FACTOR = 0.0001


def compute_region_bbox(lat, lon, half_window_km=8) -> dict:
    """Compute WGS84 bounding box around (lat, lon) for half_window_km."""
    try:
        num_lat = float(lat)
        num_lon = float(lon)
        hw_km = float(half_window_km)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"Coordonnées ou demi-fenêtre invalides pour compute_region_bbox : ({lat}, {lon}, {half_window_km})"
        ) from error

    if (
        not is_finite(num_lat)
        or not is_finite(num_lon)
        or num_lat < -80
        or num_lat > 80
        or num_lon < -180
        or num_lon > 180
    ):
        raise ValueError(
            f"Coordonnées hors zone valide [-80°, +80°] pour computeRegionBbox : ({lat}, {lon})"
        )
    if not is_finite(hw_km) or hw_km < 1 or hw_km > 25:
        raise ValueError(
            f"Demi-fenêtre régionale invalide pour computeRegionBbox (halfWindowKm={half_window_km})"
        )

    d_lat = hw_km / 111.32
    d_lon = hw_km / (111.32 * math.cos((num_lat * math.pi) / 180.0))
    return validate_bbox(
        {
            "minLon": js_round(num_lon - d_lon, 5),
            "minLat": js_round(num_lat - d_lat, 5),
            "maxLon": js_round(num_lon + d_lon, 5),
            "maxLat": js_round(num_lat + d_lat, 5),
        }
    )


def build_bbox_grid_coordinates(bbox: dict, width: int = 64, height: int = 64) -> list[dict]:
    """Build pixel center coordinates (lat, lon) for each (row, col) of bbox."""
    min_lon = bbox["minLon"]
    min_lat = bbox["minLat"]
    max_lon = bbox["maxLon"]
    max_lat = bbox["maxLat"]
    d_lon = (max_lon - min_lon) / width
    d_lat = (max_lat - min_lat) / height

    coords = []
    for r in range(height):
        lat = js_round(max_lat - (r + 0.5) * d_lat, 6)
        for c in range(width):
            lon = js_round(min_lon + (c + 0.5) * d_lon, 6)
            index = r * width + c
            coords.append({"index": index, "row": r, "col": c, "lat": lat, "lon": lon})
    return coords


def _find_modis_summer_item(*, lat: float, lon: float, year: int) -> dict | None:
    body = json.dumps(
        {
            "collections": ["modis-13Q1-061"],
            "intersects": {"type": "Point", "coordinates": [lon, lat]},
            "datetime": f"{year}-07-15T00:00:00Z/{year}-08-10T23:59:59Z",
            "limit": 2,
        }
    )
    response = http.fetch(
        CONFIG["endpoints"]["planetaryComputerStac"],
        method="POST",
        headers={"Content-Type": "application/json"},
        body=body,
    )
    if not response.ok:
        response.close()
        raise ValueError(f"STAC modis-13Q1-061 a répondu HTTP {response.status} ({year})")
    data = read_bounded_json(response)
    features = (data or {}).get("features") or []
    return features[0] if features else None


def _fetch_modis_bbox_tile(*, item_id: str, bbox: dict, width: int = 64, height: int = 64) -> dict:
    bbox_str = ",".join(
        number_text(bbox[k]) for k in ("minLon", "minLat", "maxLon", "maxLat")
    )
    encoded_item = quote(str(item_id), safe="")
    url = (
        f"https://planetarycomputer.microsoft.com/api/data/v1/item/crop/{bbox_str}.npy"
        f"?collection=modis-13Q1-061&item={encoded_item}"
        f"&assets=250m_16_days_NDVI&assets=250m_16_days_EVI"
        f"&width={width}&height={height}&coord_crs=epsg:4326"
    )
    response = http.fetch(url)
    if not response.ok:
        response.close()
        raise ValueError(f"TiTiler MODIS crop .npy HTTP {response.status}")
    buf = read_bounded_buffer(response)
    parsed = parse_npy_grid(buf, expected_width=width, expected_height=height)
    raw_ndvi_band = parsed["bands"][0] if len(parsed["bands"]) > 0 else []
    raw_evi_band = parsed["bands"][1] if len(parsed["bands"]) > 1 else []

    pixels = [
        js_round(v * MODIS_SCALE_FACTOR, 4) if -2000 < v <= 10000 else None
        for v in raw_ndvi_band
    ]
    evi_pixels = [
        js_round(v * MODIS_SCALE_FACTOR, 4) if -2000 < v <= 10000 else None
        for v in raw_evi_band
    ]
    return {"pixels": pixels, "eviPixels": evi_pixels}


def fetch_regional_ndvi_series(
    *,
    lat,
    lon,
    start_year=None,
    end_year=None,
    half_window_km=8,
    grid_size=64,
    **kwargs,
) -> dict:
    """Fetch 64x64 regional MODIS NDVI & EVI summer peak grids for [start_year, end_year]."""
    if start_year is None and "startYear" in kwargs:
        start_year = kwargs["startYear"]
    if end_year is None and "endYear" in kwargs:
        end_year = kwargs["endYear"]
    if "halfWindowKm" in kwargs:
        half_window_km = kwargs["halfWindowKm"]
    if "gridSize" in kwargs:
        grid_size = kwargs["gridSize"]

    valid = validate_historical_sampling_params(
        lat=lat,
        lon=lon,
        start_year=start_year,
        end_year=end_year,
        grid_size=grid_size,
        half_window_km=half_window_km,
    )
    bbox = compute_region_bbox(valid["lat"], valid["lon"], valid["halfWindowKm"])
    hw_str = number_text(valid["halfWindowKm"])
    legacy_key = (
        f"bbox_{region_cell_key(valid['lat'], valid['lon'], 0.05)}_"
        f"{valid['startYear']}_{valid['endYear']}_"
        f"{valid['gridSize']}x{valid['gridSize']}_{hw_str}km"
    )
    cache_key = f"{legacy_key}_{bbox_cache_key(bbox)}"
    expected_years = list(range(valid["startYear"], valid["endYear"] + 1))

    def _matches(data: dict) -> bool:
        grids = data.get("gridsByYear") or {}
        return (
            same_bbox(data.get("bbox"), bbox)
            and data.get("nrows") == valid["gridSize"]
            and data.get("ncols") == valid["gridSize"]
            and len(grids) == len(expected_years)
            and all(str(y) in grids or y in grids for y in expected_years)
        )

    cached = read_cache("modis-ndvi", cache_key, _matches) or read_cache(
        "modis-ndvi", legacy_key, _matches
    )
    if cached:
        return {**cached, "fromCache": True}

    pixel_coordinates = build_bbox_grid_coordinates(
        bbox, valid["gridSize"], valid["gridSize"]
    )
    grids_by_year = {}
    n_pixels = valid["gridSize"] * valid["gridSize"]

    for year in expected_years:
        item = _find_modis_summer_item(lat=valid["lat"], lon=valid["lon"], year=year)
        if not item:
            grids_by_year[str(year)] = {
                "year": year,
                "itemId": None,
                "pixels": [None] * n_pixels,
                "eviPixels": [None] * n_pixels,
            }
            continue
        tile = _fetch_modis_bbox_tile(
            item_id=item["id"],
            bbox=bbox,
            width=valid["gridSize"],
            height=valid["gridSize"],
        )
        grids_by_year[str(year)] = {
            "year": year,
            "itemId": item["id"],
            "pixels": tile["pixels"],
            "eviPixels": tile["eviPixels"],
        }

    payload = {
        "source": (
            f"NASA MODIS MOD13Q1 v061 (Grille régionale {valid['gridSize']}×{valid['gridSize']} = "
            f"{n_pixels} pixels, NDVI & EVI)"
        ),
        "coordinates": {"lat": valid["lat"], "lon": valid["lon"]},
        "bbox": bbox,
        "nrows": valid["gridSize"],
        "ncols": valid["gridSize"],
        "halfWindowKm": valid["halfWindowKm"],
        "pixelCoordinates": pixel_coordinates,
        "gridsByYear": grids_by_year,
    }
    return write_cache("modis-ndvi", cache_key, payload)


def search_hls30m_granules(*, lat, lon, year, max_cloud_cover=20, **kwargs) -> list[dict]:
    """Query NASA CMR-STAC LPCLOUD for HLS 30m (Landsat + Sentinel-2) summer scenes."""
    if "maxCloudCover" in kwargs:
        max_cloud_cover = kwargs["maxCloudCover"]

    valid = validate_historical_sampling_params(
        lat=lat, lon=lon, start_year=year, end_year=year
    )
    delta = 0.02
    bbox_str = ",".join(
        number_text(v)
        for v in (
            valid["lon"] - delta,
            valid["lat"] - delta,
            valid["lon"] + delta,
            valid["lat"] + delta,
        )
    )
    datetime_str = (
        f"{valid['startYear']}-07-01T00:00:00Z/{valid['startYear']}-08-25T23:59:59Z"
    )
    params = {
        "collections": "HLSL30.v2.0,HLSS30.v2.0",
        "bbox": bbox_str,
        "datetime": datetime_str,
        "limit": "10",
    }
    url = f"{CONFIG['endpoints']['cmrStacSearch']}?{urlencode(params)}"
    headers = {"Accept": "application/geo+json"}
    if CONFIG["credentials"].get("earthdataToken"):
        headers["Authorization"] = f"Bearer {CONFIG['credentials']['earthdataToken']}"

    response = http.fetch(url, headers=headers)
    if not response.ok:
        response.close()
        raise ValueError(f"NASA CMR-STAC LPCLOUD a répondu HTTP {response.status}")

    data = read_bounded_json(response)
    features = [
        f
        for f in (data or {}).get("features") or []
        if ((f.get("properties") or {}).get("eo:cloud_cover") or 0) <= max_cloud_cover
    ]
    return [
        {
            "id": f.get("id"),
            "collection": f.get("collection"),
            "datetime": (f.get("properties") or {}).get("datetime"),
            "cloudCover": (f.get("properties") or {}).get("eo:cloud_cover"),
            "redBandHref": ((f.get("assets") or {}).get("B04") or {}).get("href"),
            "nirBandHref": (((f.get("assets") or {}).get("B8A") or {}).get("href"))
            or (((f.get("assets") or {}).get("B05") or {}).get("href")),
        }
        for f in features
    ]

