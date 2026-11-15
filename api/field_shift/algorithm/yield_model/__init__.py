"""Regional relative-vigor model migrated from the validated JavaScript implementation.

Official observations and projections are inputs; estimated yield changes retain the
explicit, uncalibrated 1:1 vigor-to-yield assumption.
"""

from __future__ import annotations

from field_shift.algorithm.yield_model.climate_twins import (
    REFERENCE_REGIONS_CATALOG,
    blend_pair_effect_for_season,
    compute_normalized_climate_distance,
    compute_yearly_blending_alpha,
    find_climate_twin,
    forecast_future_rotation_yield,
    load_reference_regions_profiles,
)
from field_shift.algorithm.yield_model.config import (
    CONFIG,
    CROP_IDS,
    CROP_TAXONOMY,
    CROPS,
    SATELLITE_CROP_CODES,
    SATELLITE_CROP_MAPPING_VERSION,
    js_round,
)
from field_shift.algorithm.yield_model.model_utils import (
    MAX_ROTATION_YEARS,
    confidence_from_counts,
    downgrade_confidence,
    min_confidence,
    physical_effect_interval,
    relative_gain_pct,
    resolve_pair_evidence,
    validate_current_crop,
    validate_physical_effect_pct,
    validated_rotation_slots,
)
from field_shift.algorithm.yield_model.pair_transitions import (
    build_transition_observations,
    cluster_pixels_into_distinct_fields,
    compute_regional_pair_matrix,
)
from field_shift.algorithm.yield_model.rotation import (
    current_crop_conflict,
    cycle_length,
    entry_start,
    first_year,
    lock_reason,
    normalize_cycle_offset,
    planting_starts,
    rotation_errors,
    to_slots,
)
from field_shift.algorithm.yield_model.sources import (
    NASS_COMMODITY_MAP,
    build_bbox_grid_coordinates,
    build_nass_query_params,
    calibrate_pair_matrix_with_nass_yields,
    classify_climate_regimes,
    classify_season_against_baseline,
    compute_climate_baseline_stats,
    compute_region_bbox,
    extract_annual_survey_yields,
    fetch_aafc_canada_bbox_tile,
    fetch_future_climate_projection,
    fetch_nasa_power_series,
    fetch_nass_state_yields,
    fetch_regional_crop_history,
    fetch_regional_ndvi_series,
    fetch_usda_cdl_bbox_tile,
    infer_us_state_from_lat_lon,
    is_border_straddling_bbox,
    is_location_in_canada,
    lat_lon_to_albers_epsg5070,
    load_local_nasa_power_snapshot,
    merge_cross_border_tiles_by_year,
    parse_npy_grid,
    parse_uncompressed_tiff_u8,
    read_cache,
    recalibrate_seasons_with_baseline,
    region_cell_key,
    search_hls30m_granules,
    summarize_growing_seasons,
    validate_bbox,
    validate_climate_seasons,
    validate_historical_sampling_params,
    write_cache,
)
from field_shift.algorithm.yield_model.yield_optimizer import (
    compute_unobserved_pair_penalty,
    evaluate_rotation_yield_from_pairs,
    find_best_multi_crop_rotations_for_yield,
    validate_cycle_years,
    validate_regime,
)


def run_regional_yield_pipeline(
    *,
    lat,
    lon,
    start_year=None,
    end_year=None,
    half_window_km=None,
    cycle_years=4,
    current_crop=None,
    available_crops=None,
    min_distinct_crops=2,
    regime="all",
    future_start_year=2027,
    future_end_year=2040,
    scenario="ssp245",
    **kwargs,
) -> dict:
    """Execute the full regional yield, climate-twin and CMIP6 rotation pipeline."""
    if start_year is None:
        start_year = kwargs.get("startYear", CONFIG["sampling"]["startYear"])
    if end_year is None:
        end_year = kwargs.get("endYear", CONFIG["sampling"]["endYear"])
    if half_window_km is None:
        half_window_km = kwargs.get(
            "halfWindowKm", CONFIG["sampling"]["halfWindowKm"]
        )
    if "cycleYears" in kwargs:
        cycle_years = kwargs["cycleYears"]
    if current_crop is None and "currentCrop" in kwargs:
        current_crop = kwargs["currentCrop"]
    if available_crops is None and "availableCrops" in kwargs:
        available_crops = kwargs["availableCrops"]
    if "minDistinctCrops" in kwargs:
        min_distinct_crops = kwargs["minDistinctCrops"]
    if "futureStartYear" in kwargs:
        future_start_year = kwargs["futureStartYear"]
    if "futureEndYear" in kwargs:
        future_end_year = kwargs["futureEndYear"]

    valid = validate_historical_sampling_params(
        lat=lat,
        lon=lon,
        start_year=start_year,
        end_year=end_year,
        half_window_km=half_window_km,
    )
    validate_cycle_years(cycle_years)
    validate_regime(regime)
    validate_current_crop(current_crop)

    nasa_power = fetch_nasa_power_series(
        lat=valid["lat"],
        lon=valid["lon"],
        start_year=valid["startYear"],
        end_year=valid["endYear"],
    )
    ndvi_series = fetch_regional_ndvi_series(
        lat=valid["lat"],
        lon=valid["lon"],
        start_year=valid["startYear"],
        end_year=valid["endYear"],
        half_window_km=valid["halfWindowKm"],
    )
    crop_history = fetch_regional_crop_history(
        lat=valid["lat"],
        lon=valid["lon"],
        bbox=ndvi_series["bbox"],
        grid_size=ndvi_series.get("nrows") or 64,
        half_window_km=valid["halfWindowKm"],
        start_year=valid["startYear"],
        end_year=valid["endYear"],
    )

    try:
        hls_granules_sample = search_hls30m_granules(
            lat=valid["lat"], lon=valid["lon"], year=valid["endYear"]
        )
    except Exception:
        hls_granules_sample = []

    try:
        nass_yields = fetch_nass_state_yields(
            lat=valid["lat"],
            lon=valid["lon"],
            start_year=valid["startYear"],
            end_year=valid["endYear"],
        )
    except Exception:
        nass_yields = {"available": False}

    observations = build_transition_observations(
        ndvi_series=ndvi_series,
        crop_history=crop_history,
        climate_seasons=nasa_power["seasons"],
    )
    pair_matrix = calibrate_pair_matrix_with_nass_yields(
        compute_regional_pair_matrix(observations),
        nass_yields,
    )

    climate_projection = fetch_future_climate_projection(
        lat=valid["lat"],
        lon=valid["lon"],
        historical_seasons=nasa_power["seasons"],
        start_year=future_start_year,
        end_year=future_end_year,
        scenario=scenario,
    )
    reference_regions = load_reference_regions_profiles(
        start_year=valid["startYear"], end_year=valid["endYear"]
    )
    climate_twin = find_climate_twin(
        projected_seasons=climate_projection["projectedSeasons"],
        local_baseline_stats=climate_projection["baselineStats"],
        candidate_regions=reference_regions,
        farm_coordinates={"lat": valid["lat"], "lon": valid["lon"]},
    )

    best_rotations = find_best_multi_crop_rotations_for_yield(
        pair_matrix=pair_matrix,
        cycle_years=cycle_years,
        available_crops=available_crops,
        current_crop=current_crop,
        min_distinct_crops=min_distinct_crops,
        regime=regime,
        top_k=5,
        projected_seasons=climate_projection["projectedSeasons"],
        twin_match=climate_twin,
        local_baseline_stats=climate_projection["baselineStats"],
    )

    best_twin = climate_twin.get("bestTwin") if climate_twin else None
    return {
        "interpretation": {
            "metric": "equal_weight_annual_relative_vigor",
            "yieldMapping": "conditional_1_to_1_relative_anomalies",
            "empiricalYieldValidation": False,
            "rotationEffect": "observational_association",
            "twinTheory": "progressive_transfer_from_warmer_climate_analogue",
            "uncertainty": "model_envelope_not_validated_coverage",
        },
        "region": {
            "lat": valid["lat"],
            "lon": valid["lon"],
            "halfWindowKm": valid["halfWindowKm"],
            "period": {"startYear": valid["startYear"], "endYear": valid["endYear"]},
        },
        "sourcesUsed": {
            "climate": nasa_power["source"],
            "ndvi": ndvi_series["source"],
            "cropMap": crop_history["source"],
            "cmip6Projection": climate_projection["source"],
            "hls30mGranulesFound": len(hls_granules_sample),
            "nassCalibration": bool(nass_yields.get("available")),
        },
        "climateSeasons": nasa_power["seasons"],
        "climateProjection": {
            "scenario": climate_projection["scenario"],
            "period": climate_projection["period"],
            "baselineStats": climate_projection["baselineStats"],
            "projectedSeasons": climate_projection["projectedSeasons"],
        },
        "climateTwin": (
            {
                "status": climate_twin.get("status"),
                "reason": climate_twin.get("reason"),
                "targetFutureClimate": climate_twin["targetFutureClimate"],
                "warmingDeltaGdd": climate_twin["warmingDeltaGdd"],
                "warmingDeltaTempC": climate_twin["warmingDeltaTempC"],
                "bestTwin": (
                    {
                        "id": best_twin["id"],
                        "name": best_twin["name"],
                        "coordinates": best_twin["coordinates"],
                        "distance": best_twin["distance"],
                        "similarityPct": best_twin["similarityPct"],
                        "baselineMeans": best_twin["baselineMeans"],
                    }
                    if best_twin
                    else None
                ),
                "candidatesRanked": [
                    {
                        "id": c["id"],
                        "name": c["name"],
                        "distance": c["distance"],
                        "similarityPct": c["similarityPct"],
                        "baselineMeans": c["baselineMeans"],
                    }
                    for c in (climate_twin.get("candidatesRanked") or [])
                ],
            }
            if climate_twin
            else None
        ),
        "pairMatrix": pair_matrix,
        "bestRotations": best_rotations,
    }


__all__ = [
    "CONFIG",
    "CROPS",
    "CROP_IDS",
    "CROP_TAXONOMY",
    "MAX_ROTATION_YEARS",
    "NASS_COMMODITY_MAP",
    "REFERENCE_REGIONS_CATALOG",
    "SATELLITE_CROP_CODES",
    "SATELLITE_CROP_MAPPING_VERSION",
    "blend_pair_effect_for_season",
    "build_bbox_grid_coordinates",
    "build_nass_query_params",
    "build_transition_observations",
    "calibrate_pair_matrix_with_nass_yields",
    "classify_climate_regimes",
    "classify_season_against_baseline",
    "cluster_pixels_into_distinct_fields",
    "compute_climate_baseline_stats",
    "compute_normalized_climate_distance",
    "compute_region_bbox",
    "compute_regional_pair_matrix",
    "compute_unobserved_pair_penalty",
    "compute_yearly_blending_alpha",
    "confidence_from_counts",
    "current_crop_conflict",
    "cycle_length",
    "downgrade_confidence",
    "entry_start",
    "evaluate_rotation_yield_from_pairs",
    "extract_annual_survey_yields",
    "fetch_aafc_canada_bbox_tile",
    "fetch_future_climate_projection",
    "fetch_nasa_power_series",
    "fetch_nass_state_yields",
    "fetch_regional_crop_history",
    "fetch_regional_ndvi_series",
    "fetch_usda_cdl_bbox_tile",
    "find_best_multi_crop_rotations_for_yield",
    "find_climate_twin",
    "first_year",
    "forecast_future_rotation_yield",
    "infer_us_state_from_lat_lon",
    "is_border_straddling_bbox",
    "is_location_in_canada",
    "js_round",
    "lat_lon_to_albers_epsg5070",
    "load_local_nasa_power_snapshot",
    "load_reference_regions_profiles",
    "lock_reason",
    "merge_cross_border_tiles_by_year",
    "min_confidence",
    "normalize_cycle_offset",
    "parse_npy_grid",
    "parse_uncompressed_tiff_u8",
    "physical_effect_interval",
    "planting_starts",
    "read_cache",
    "recalibrate_seasons_with_baseline",
    "region_cell_key",
    "relative_gain_pct",
    "resolve_pair_evidence",
    "rotation_errors",
    "run_regional_yield_pipeline",
    "search_hls30m_granules",
    "summarize_growing_seasons",
    "to_slots",
    "validate_bbox",
    "validate_climate_seasons",
    "validate_current_crop",
    "validate_cycle_years",
    "validate_historical_sampling_params",
    "validate_physical_effect_pct",
    "validate_regime",
    "validated_rotation_slots",
    "write_cache",
]
