"""Real remote sources and bounded, validated local caches for the yield model."""

from __future__ import annotations

from field_shift.algorithm.yield_model.sources.cache import (
    MAX_HTTP_RESPONSE_BYTES,
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
from field_shift.algorithm.yield_model.sources.climate_validation import validate_climate_seasons
from field_shift.algorithm.yield_model.sources.crop_history import (
    fetch_aafc_canada_bbox_tile,
    fetch_regional_crop_history,
    fetch_usda_cdl_bbox_tile,
    is_border_straddling_bbox,
    is_location_in_canada,
    lat_lon_to_albers_epsg5070,
    merge_cross_border_tiles_by_year,
)
from field_shift.algorithm.yield_model.sources.nasa_cmip6_projection import (
    classify_season_against_baseline,
    compute_climate_baseline_stats,
    fetch_future_climate_projection,
    recalibrate_seasons_with_baseline,
)
from field_shift.algorithm.yield_model.sources.nasa_modis_ndvi import (
    build_bbox_grid_coordinates,
    compute_region_bbox,
    fetch_regional_ndvi_series,
    search_hls30m_granules,
)
from field_shift.algorithm.yield_model.sources.nasa_power import (
    classify_climate_regimes,
    fetch_nasa_power_series,
    load_local_nasa_power_snapshot,
    summarize_growing_seasons,
)
from field_shift.algorithm.yield_model.sources.nass_quick_stats import (
    NASS_COMMODITY_MAP,
    build_nass_query_params,
    calibrate_pair_matrix_with_nass_yields,
    extract_annual_survey_yields,
    fetch_nass_state_yields,
    infer_us_state_from_lat_lon,
)
from field_shift.algorithm.yield_model.sources.raster_parser import parse_npy_grid, parse_uncompressed_tiff_u8

__all__ = [
    "MAX_HTTP_RESPONSE_BYTES",
    "NASS_COMMODITY_MAP",
    "bbox_cache_key",
    "build_bbox_grid_coordinates",
    "build_nass_query_params",
    "calibrate_pair_matrix_with_nass_yields",
    "classify_climate_regimes",
    "classify_season_against_baseline",
    "compute_climate_baseline_stats",
    "compute_region_bbox",
    "extract_annual_survey_yields",
    "fetch_aafc_canada_bbox_tile",
    "fetch_future_climate_projection",
    "fetch_nasa_power_series",
    "fetch_nass_state_yields",
    "fetch_regional_crop_history",
    "fetch_regional_ndvi_series",
    "fetch_usda_cdl_bbox_tile",
    "infer_us_state_from_lat_lon",
    "is_border_straddling_bbox",
    "is_location_in_canada",
    "lat_lon_to_albers_epsg5070",
    "load_local_nasa_power_snapshot",
    "merge_cross_border_tiles_by_year",
    "number_text",
    "parse_npy_grid",
    "parse_uncompressed_tiff_u8",
    "read_bounded_buffer",
    "read_bounded_json",
    "read_cache",
    "recalibrate_seasons_with_baseline",
    "region_cell_key",
    "same_bbox",
    "search_hls30m_granules",
    "summarize_growing_seasons",
    "validate_bbox",
    "validate_climate_seasons",
    "validate_historical_sampling_params",
    "write_cache",
]
