"""Regional 64x64 crop history tiles (AAFC Canada + USDA CDL) and US/Canada border logic."""

from __future__ import annotations

import json
import math
from urllib.parse import quote, urlencode

from field_shift.algorithm.yield_model.config import (
    CONFIG,
    SATELLITE_CROP_CODES,
    SATELLITE_CROP_MAPPING_VERSION,
    is_finite,
    is_integer,
    js_round,
)
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
from field_shift.algorithm.yield_model.sources.nasa_modis_ndvi import compute_region_bbox
from field_shift.algorithm.yield_model.sources.raster_parser import parse_npy_grid, parse_uncompressed_tiff_u8


def _interpolate_polyline(x: float, vertices: list[tuple[float, float]]) -> float:
    if x <= vertices[0][0]:
        return vertices[0][1]
    for i in range(len(vertices) - 1):
        x0, y0 = vertices[i]
        x1, y1 = vertices[i + 1]
        if x0 <= x <= x1:
            if x1 == x0:
                return y1
            t = (x - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return vertices[-1][1]


BORDER_LAT_BY_LON_VERTICES: list[tuple[float, float]] = [
    (-141.0, 60.0),
    (-130.0, 54.7),
    (-125.0, 48.5),
    (-123.2, 48.3),
    (-122.75, 49.0),
    (-95.15, 49.0),
    (-94.6, 48.72),
    (-93.4, 48.6),
    (-89.5, 48.0),
    (-87.5, 47.75),
    (-84.75, 46.508),
    (-84.1, 46.508),
    (-83.5, 45.95),
    (-82.42, 43.02),
    (-82.42, 41.68),
    (-81.2, 42.15),
    (-78.905, 42.88),
    (-78.8, 43.63),
    (-76.3, 43.63),
    (-76.1, 44.2),
    (-74.65, 45.0),
    (-71.5, 45.0),
    (-71.08, 45.25),
    (-70.65, 45.79),
    (-70.3, 46.05),
    (-70.0, 46.55),
    (-69.45, 47.46),
    (-69.0, 47.18),
    (-68.6, 47.255),
    (-68.33, 47.36),
    (-67.78, 47.08),
    (-67.78, 45.95),
    (-67.45, 45.55),
    (-66.95, 44.8),
    (-65.0, 43.3),
    (-52.0, 46.0),
]

DETROIT_STCLAIR_LON_BY_LAT: list[tuple[float, float]] = [
    (42.04, -83.12),
    (42.15, -83.11),
    (42.31, -83.045),
    (42.34, -83.01),
    (42.45, -82.9),
    (42.6, -82.5),
    (42.97, -82.415),
    (43.02, -82.415),
]

NIAGARA_RIVER_LON_BY_LAT: list[tuple[float, float]] = [
    (42.85, -78.905),
    (42.9, -78.905),
    (43.05, -79.02),
    (43.09, -79.065),
    (43.27, -79.07),
]


def is_location_in_canada(lat, lon) -> bool:
    """Return True if (lat, lon) is in Canada, False if in the United States or outside."""
    try:
        num_lat = float(lat)
        num_lon = float(lon)
    except (TypeError, ValueError):
        return False

    if (
        not is_finite(num_lat)
        or not is_finite(num_lon)
        or num_lon < -141.0
        or num_lon > -52.0
        or num_lat < 41.65
        or num_lat > 84.0
    ):
        return False

    if 42.04 <= num_lat <= 43.02 and -83.25 <= num_lon <= -82.35:
        river_lon = _interpolate_polyline(num_lat, DETROIT_STCLAIR_LON_BY_LAT)
        return num_lon >= river_lon

    if 42.85 <= num_lat <= 43.27 and -79.15 <= num_lon <= -78.8:
        river_lon = _interpolate_polyline(num_lat, NIAGARA_RIVER_LON_BY_LAT)
        return num_lon <= river_lon

    border_lat = _interpolate_polyline(num_lon, BORDER_LAT_BY_LON_VERTICES)
    return num_lat >= border_lat


def is_border_straddling_bbox(bbox: dict | None) -> bool:
    """Return True if bbox straddles the Canada / United States border."""
    if not isinstance(bbox, dict):
        return False
    min_lat = bbox["minLat"]
    max_lat = bbox["maxLat"]
    min_lon = bbox["minLon"]
    max_lon = bbox["maxLon"]
    mid_lat = (min_lat + max_lat) / 2.0
    mid_lon = (min_lon + max_lon) / 2.0
    sample_points = (
        (min_lat, min_lon),
        (min_lat, max_lon),
        (max_lat, min_lon),
        (max_lat, max_lon),
        (mid_lat, mid_lon),
        (min_lat, mid_lon),
        (max_lat, mid_lon),
        (mid_lat, min_lon),
        (mid_lat, max_lon),
    )
    has_canada = False
    has_us = False
    for p_lat, p_lon in sample_points:
        if is_location_in_canada(p_lat, p_lon):
            has_canada = True
        else:
            has_us = True
        if has_canada and has_us:
            return True
    return False


def _validate_tile_request_params(*, bbox, year, grid_size, lat=None, lon=None) -> dict:
    validate_bbox(bbox)
    try:
        y = float(year)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"Année de tuile satellite invalide (year={year}) : entier [1981, 2030] attendu."
        ) from error
    if not is_integer(y) or y < 1981 or y > 2030:
        raise ValueError(
            f"Année de tuile satellite invalide (year={year}) : entier [1981, 2030] attendu."
        )

    try:
        g = float(grid_size)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"Taille de grille invalide (gridSize={grid_size}) : entier [4, 128] attendu."
        ) from error
    if not is_integer(g) or g < 4 or g > 128:
        raise ValueError(
            f"Taille de grille invalide (gridSize={grid_size}) : entier [4, 128] attendu."
        )

    if lat is not None or lon is not None:
        try:
            num_lat = float(lat)
            num_lon = float(lon)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Coordonnées invalides : ({lat}, {lon})") from error
        if (
            not is_finite(num_lat)
            or not is_finite(num_lon)
            or num_lat < -80
            or num_lat > 80
            or num_lon < -180
            or num_lon > 180
        ):
            raise ValueError(f"Coordonnées invalides : ({lat}, {lon})")

    return {"year": int(y), "gridSize": int(g)}


def lat_lon_to_albers_epsg5070(lat_deg: float, lon_deg: float) -> dict:
    """Official NAD83 Conus Albers (EPSG:5070) projection."""
    a = 6378137.0
    e2 = 0.0066943800229
    e = math.sqrt(e2)
    rad = math.pi / 180.0

    phi1 = 29.5 * rad
    phi2 = 45.5 * rad
    phi0 = 23.0 * rad
    lam0 = -96.0 * rad
    phi = float(lat_deg) * rad
    lam = float(lon_deg) * rad

    def calc_m(p: float) -> float:
        return math.cos(p) / math.sqrt(1.0 - e2 * math.sin(p) ** 2)

    def calc_q(p: float) -> float:
        sin_p = math.sin(p)
        return (1.0 - e2) * (
            sin_p / (1.0 - e2 * sin_p ** 2)
            - (1.0 / (2.0 * e)) * math.log((1.0 - e * sin_p) / (1.0 + e * sin_p))
        )

    m1 = calc_m(phi1)
    m2 = calc_m(phi2)
    q0 = calc_q(phi0)
    q1 = calc_q(phi1)
    q2 = calc_q(phi2)
    q = calc_q(phi)

    n = (m1 ** 2 - m2 ** 2) / (q2 - q1)
    c_val = m1 ** 2 + n * q1
    rho0 = (a * math.sqrt(c_val - n * q0)) / n
    rho = (a * math.sqrt(c_val - n * q)) / n
    theta = n * (lam - lam0)

    x = rho * math.sin(theta)
    y = rho0 - rho * math.cos(theta)
    return {"x": js_round(x, 2), "y": js_round(y, 2)}


def _map_crop_code(mapping: dict, raw_code: int) -> str | None:
    return mapping.get(str(raw_code), mapping.get(raw_code))


def fetch_aafc_canada_bbox_tile(*, bbox: dict, year: int, grid_size: int = 64, **kwargs) -> list[dict]:
    """Fetch uncompressed 8-bit GeoTIFF crop inventory tile from AAFC Canada."""
    if "gridSize" in kwargs:
        grid_size = kwargs["gridSize"]
    valid = _validate_tile_request_params(bbox=bbox, year=year, grid_size=grid_size)
    bbox_str = ",".join(
        number_text(float(bbox[k])) for k in ("minLon", "minLat", "maxLon", "maxLat")
    )
    params = {
        "bbox": bbox_str,
        "bboxSR": "4326",
        "imageSR": "4326",
        "size": f"{valid['gridSize']},{valid['gridSize']}",
        "interpolation": "RSP_NearestNeighbor",
        "pixelType": "U8",
        "format": "tiff",
        "compression": "NONE",
        "f": "image",
    }
    url = (
        f"{CONFIG['endpoints']['aafcCropInventoryRest']}/"
        f"{valid['year']}/ImageServer/exportImage?{urlencode(params)}"
    )
    response = http.fetch(url)
    if not response.ok:
        response.close()
        raise ValueError(f"AAFC exportImage HTTP {response.status} ({valid['year']})")
    buf = read_bounded_buffer(response)
    parsed = parse_uncompressed_tiff_u8(
        buf, expected_width=valid["gridSize"], expected_height=valid["gridSize"]
    )
    aafc_map = SATELLITE_CROP_CODES["aafcCanada"]
    return [
        {"rawCode": raw_code, "cropId": _map_crop_code(aafc_map, raw_code)}
        for raw_code in parsed["pixels"]
    ]


def fetch_usda_cdl_bbox_tile(
    *, lat, lon, bbox: dict, year: int, grid_size: int = 64, **kwargs
) -> list[dict] | None:
    """Fetch USDA Cropland Data Layer (.npy) tile via Planetary Computer STAC/TiTiler."""
    if "gridSize" in kwargs:
        grid_size = kwargs["gridSize"]
    valid = _validate_tile_request_params(
        bbox=bbox, year=year, grid_size=grid_size, lat=lat, lon=lon
    )
    body = json.dumps(
        {
            "collections": ["usda-cdl"],
            "intersects": {"type": "Point", "coordinates": [float(lon), float(lat)]},
            "datetime": f"{valid['year']}-01-01T00:00:00Z/{valid['year']}-12-31T23:59:59Z",
            "limit": 5,
        }
    )
    stac_res = http.fetch(
        CONFIG["endpoints"]["planetaryComputerStac"],
        method="POST",
        headers={"Content-Type": "application/json"},
        body=body,
    )
    if not stac_res.ok:
        stac_res.close()
        return None
    stac_json = read_bounded_json(stac_res)
    features = (stac_json or {}).get("features") or []
    item = next(
        (f for f in features if isinstance(f, dict) and (f.get("assets") or {}).get("cropland")),
        None,
    )
    if not item:
        return None

    bbox_str = ",".join(
        number_text(float(bbox[k])) for k in ("minLon", "minLat", "maxLon", "maxLat")
    )
    encoded_item = quote(str(item["id"]), safe="")
    url = (
        f"https://planetarycomputer.microsoft.com/api/data/v1/item/crop/{bbox_str}.npy"
        f"?collection=usda-cdl&item={encoded_item}"
        f"&assets=cropland&width={valid['gridSize']}&height={valid['gridSize']}&coord_crs=epsg:4326"
    )
    res = http.fetch(url)
    if not res.ok:
        res.close()
        return None
    buf = read_bounded_buffer(res)
    parsed = parse_npy_grid(
        buf, expected_width=valid["gridSize"], expected_height=valid["gridSize"]
    )
    raw_codes = parsed["bands"][0] if parsed["bands"] else []
    usda_map = SATELLITE_CROP_CODES["usdaCdl"]
    return [
        {"rawCode": raw_code, "cropId": _map_crop_code(usda_map, raw_code)}
        for raw_code in raw_codes
    ]


def _fetch_tiles_for_provider(
    *, provider: str, lat: float, lon: float, region_bbox: dict, grid_size: int, years: list[int]
) -> dict[int, list[dict] | None]:
    tiles_by_year = {}
    for year in years:
        if provider == "AAFC_CANADA":
            tiles_by_year[year] = fetch_aafc_canada_bbox_tile(
                bbox=region_bbox, year=year, grid_size=grid_size
            )
        else:
            tiles_by_year[year] = fetch_usda_cdl_bbox_tile(
                lat=lat, lon=lon, bbox=region_bbox, year=year, grid_size=grid_size
            )
    return tiles_by_year


def merge_cross_border_tiles_by_year(
    primary_tiles_by_year: dict | None,
    secondary_tiles_by_year: dict | None,
    years: list[int],
    n_pixels: int,
) -> dict:
    """Merge primary and secondary crop tiles pixel by pixel for cross-border boxes."""
    merged = {}
    primary_count = 0
    secondary_added_count = 0

    for y in years:
        p_tile = (primary_tiles_by_year or {}).get(
            y, (primary_tiles_by_year or {}).get(str(y))
        ) or []
        s_tile = (secondary_tiles_by_year or {}).get(
            y, (secondary_tiles_by_year or {}).get(str(y))
        ) or []
        row = []
        for i in range(n_pixels):
            p_cell = p_tile[i] if i < len(p_tile) else None
            s_cell = s_tile[i] if i < len(s_tile) else None
            if p_cell and p_cell.get("cropId"):
                row.append(p_cell)
                primary_count += 1
            elif s_cell and s_cell.get("cropId"):
                row.append(s_cell)
                secondary_added_count += 1
            else:
                row.append(p_cell or s_cell or {"rawCode": 0, "cropId": None})
        merged[y] = row

    return {
        "mergedTilesByYear": merged,
        "primaryCount": primary_count,
        "secondaryAddedCount": secondary_added_count,
    }


def _count_recognized_crop_pixels(tiles_by_year: dict, years: list[int]) -> int:
    total = 0
    for y in years:
        tile = tiles_by_year.get(y, tiles_by_year.get(str(y))) or []
        for cell in tile:
            if isinstance(cell, dict) and cell.get("cropId"):
                total += 1
    return total


def fetch_regional_crop_history(
    *,
    lat,
    lon,
    bbox=None,
    grid_size=64,
    half_window_km=8,
    start_year=None,
    end_year=None,
    **kwargs,
) -> dict:
    """Fetch complete 64x64 regional crop tiles across [start_year, end_year]."""
    if "gridSize" in kwargs:
        grid_size = kwargs["gridSize"]
    if "halfWindowKm" in kwargs:
        half_window_km = kwargs["halfWindowKm"]
    if start_year is None and "startYear" in kwargs:
        start_year = kwargs["startYear"]
    if end_year is None and "endYear" in kwargs:
        end_year = kwargs["endYear"]

    valid = validate_historical_sampling_params(
        lat=lat,
        lon=lon,
        start_year=start_year,
        end_year=end_year,
        grid_size=grid_size,
        half_window_km=half_window_km,
    )
    primary_is_canada = is_location_in_canada(valid["lat"], valid["lon"])
    provider = "AAFC_CANADA" if primary_is_canada else "USDA_CDL"
    region_bbox = bbox or compute_region_bbox(
        valid["lat"], valid["lon"], valid["halfWindowKm"]
    )
    validate_bbox(region_bbox)
    border_straddling = is_border_straddling_bbox(region_bbox)

    hw_str = number_text(valid["halfWindowKm"])
    legacy_suffix = (
        f"{region_cell_key(valid['lat'], valid['lon'], 0.05)}_"
        f"{valid['startYear']}_{valid['endYear']}_"
        f"{valid['gridSize']}x{valid['gridSize']}_{hw_str}km"
    )
    cell_suffix = f"{legacy_suffix}_{bbox_cache_key(region_bbox)}"
    primary_cache_key = f"bbox_{provider}_{cell_suffix}"
    alt_provider = "USDA_CDL" if provider == "AAFC_CANADA" else "AAFC_CANADA"
    alt_cache_key = f"bbox_{alt_provider}_{cell_suffix}"
    merged_cache_key = f"bbox_MERGED_{cell_suffix}"
    expected_years = list(range(valid["startYear"], valid["endYear"] + 1))

    def _matches(data: dict) -> bool:
        crop_ids_by_year = data.get("cropIdsByYear") or {}
        version = data.get("cropMappingVersion")
        version_ok = version == SATELLITE_CROP_MAPPING_VERSION or (
            version is None
            and not any(
                "luzerne" in (crops or []) for crops in crop_ids_by_year.values()
            )
        )
        return (
            version_ok
            and same_bbox(data.get("bbox"), region_bbox)
            and data.get("gridSize") == valid["gridSize"]
            and len(crop_ids_by_year) == len(expected_years)
            and all(str(y) in crop_ids_by_year or y in crop_ids_by_year for y in expected_years)
        )

    for candidate_key in (
        merged_cache_key,
        primary_cache_key,
        alt_cache_key,
        f"bbox_MERGED_{legacy_suffix}",
        f"bbox_{provider}_{legacy_suffix}",
        f"bbox_{alt_provider}_{legacy_suffix}",
    ):
        cached = read_cache("crop-history", candidate_key, _matches)
        if cached:
            return {**cached, "fromCache": True}

    n_pixels = valid["gridSize"] * valid["gridSize"]
    tiles_by_year = _fetch_tiles_for_provider(
        provider=provider,
        lat=valid["lat"],
        lon=valid["lon"],
        region_bbox=region_bbox,
        grid_size=valid["gridSize"],
        years=expected_years,
    )
    primary_recognized = _count_recognized_crop_pixels(tiles_by_year, expected_years)

    if border_straddling or primary_recognized == 0:
        try:
            alt_tiles = _fetch_tiles_for_provider(
                provider=alt_provider,
                lat=valid["lat"],
                lon=valid["lon"],
                region_bbox=region_bbox,
                grid_size=valid["gridSize"],
                years=expected_years,
            )
        except Exception:
            alt_tiles = {}
        alt_recognized = _count_recognized_crop_pixels(alt_tiles, expected_years)

        if primary_recognized == 0 and alt_recognized > 0:
            provider = alt_provider
            tiles_by_year = alt_tiles
        elif primary_recognized > 0 and alt_recognized > 0:
            merged_res = merge_cross_border_tiles_by_year(
                tiles_by_year, alt_tiles, expected_years, n_pixels
            )
            if merged_res["secondaryAddedCount"] > 0:
                provider = "AAFC_CANADA+USDA_CDL"
                tiles_by_year = merged_res["mergedTilesByYear"]

    recognized_count = _count_recognized_crop_pixels(tiles_by_year, expected_years)
    if recognized_count == 0:
        raise ValueError(
            f"Aucune donnée satellite de cultures (AAFC / USDA CDL) trouvée autour de ({valid['lat']}, {valid['lon']}) sur {valid['startYear']}–{valid['endYear']}."
        )

    crop_ids_by_year = {}
    crop_counts_by_year = {}
    for year in expected_years:
        tile = tiles_by_year.get(year) or []
        crops_list = [cell.get("cropId") if isinstance(cell, dict) else None for cell in tile]
        crop_ids_by_year[str(year)] = crops_list
        counts = {}
        for c in crops_list:
            if c:
                counts[c] = counts.get(c, 0) + 1
        crop_counts_by_year[str(year)] = counts

    if provider == "AAFC_CANADA+USDA_CDL":
        source_label = (
            f"Fusion transfrontalière AAC Canada + USDA CDL "
            f"(Tuile matricielle {valid['gridSize']}×{valid['gridSize']} = {n_pixels} pixels)"
        )
        final_cache_key = merged_cache_key
    elif provider == "AAFC_CANADA":
        source_label = (
            f"AAC / AAFC Inventaire annuel des cultures "
            f"(Tuile matricielle {valid['gridSize']}×{valid['gridSize']} = {n_pixels} pixels)"
        )
        final_cache_key = f"bbox_{provider}_{cell_suffix}"
    else:
        source_label = (
            f"USDA NASS Cropland Data Layer "
            f"(Tuile matricielle {valid['gridSize']}×{valid['gridSize']} = {n_pixels} pixels)"
        )
        final_cache_key = f"bbox_{provider}_{cell_suffix}"

    payload = {
        "source": source_label,
        "provider": provider,
        "cropMappingVersion": SATELLITE_CROP_MAPPING_VERSION,
        "excludedSatelliteClasses": (
            [
                {
                    "provider": "AAFC_CANADA",
                    "rawCode": 122,
                    "reason": "pasture_forage_not_alfalfa_specific",
                }
            ]
            if "AAFC_CANADA" in provider
            else []
        ),
        "borderStraddling": border_straddling,
        "bbox": region_bbox,
        "gridSize": valid["gridSize"],
        "sampledPointsCount": n_pixels,
        "cropCountsByYear": crop_counts_by_year,
        "cropIdsByYear": crop_ids_by_year,
    }
    return write_cache("crop-history", final_cache_key, payload)

