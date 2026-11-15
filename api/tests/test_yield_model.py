"""Tests for the Python port of algo-rendement (field_shift.algorithm.yield_model)."""

from __future__ import annotations

import json
import struct
from pathlib import Path
from unittest.mock import patch

import pytest

from field_shift.algorithm.yield_model import (
    blend_pair_effect_for_season,
    build_transition_observations,
    calibrate_pair_matrix_with_nass_yields,
    compute_climate_baseline_stats,
    compute_regional_pair_matrix,
    evaluate_rotation_yield_from_pairs,
    extract_annual_survey_yields,
    find_best_multi_crop_rotations_for_yield,
    find_climate_twin,
    forecast_future_rotation_yield,
    infer_us_state_from_lat_lon,
    is_border_straddling_bbox,
    is_location_in_canada,
    normalize_cycle_offset,
    parse_npy_grid,
    parse_uncompressed_tiff_u8,
    read_cache,
    recalibrate_seasons_with_baseline,
    run_regional_yield_pipeline,
    validate_cycle_years,
    validate_regime,
    write_cache,
)

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "yield_js_parity.json"
PARITY_CASES = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize(
    "case",
    PARITY_CASES,
    ids=[f"{idx}_{c['operation']}" for idx, c in enumerate(PARITY_CASES)],
)
def test_js_to_python_engine_parity(case: dict) -> None:
    op = case["operation"]
    inp = case["input"]
    expected = case["expected"]

    if op == "baseline":
        actual = compute_climate_baseline_stats(inp)
    elif op == "recalibrate":
        actual = recalibrate_seasons_with_baseline(inp["seasons"], inp["baseline"])
    elif op == "evaluate":
        actual = evaluate_rotation_yield_from_pairs(**inp)
    elif op == "blend":
        actual = blend_pair_effect_for_season(**inp)
    elif op == "forecast":
        actual = forecast_future_rotation_yield(**inp)
    elif op == "optimize":
        actual = find_best_multi_crop_rotations_for_yield(**inp)
    elif op == "observations":
        actual = build_transition_observations(**inp)
    elif op == "matrix":
        actual = compute_regional_pair_matrix(inp)
    elif op == "twin":
        actual = find_climate_twin(**inp)
    else:
        pytest.fail(f"Unknown parity operation: {op}")

    assert actual == expected


def test_us_canada_border_precision_and_nass_geography() -> None:
    # Canadian cities (including tricky border zones: Beauce, Côte-du-Sud, Windsor, Sault ON, Fort Erie)
    canadian_points = [
        ("Saint-Hyacinthe QC", 45.63, -72.95),
        ("Saint-Georges-de-Beauce QC", 46.12, -70.67),
        ("Lac-Mégantic QC", 45.58, -70.88),
        ("Montmagny QC", 46.98, -70.55),
        ("Saint-Jean-Port-Joli QC", 47.21, -70.27),
        ("Windsor ON", 42.31, -83.03),
        ("Sarnia ON", 42.97, -82.40),
        ("Sault Ste. Marie ON", 46.52, -84.33),
        ("Fort Erie ON", 42.90, -78.93),
        ("Niagara Falls ON", 43.09, -79.08),
    ]
    for label, lat, lon in canadian_points:
        assert is_location_in_canada(lat, lon) is True, f"{label} should be in Canada"
        assert infer_us_state_from_lat_lon(lat, lon) is None, f"{label} must not get a US state"

    # US border cities
    us_points = [
        ("Ames IA", 42.03, -93.62, "IA"),
        ("Detroit MI", 42.33, -83.05, "MI"),
        ("Port Huron MI", 42.97, -82.43, "MI"),
        ("Sault Ste. Marie MI", 46.49, -84.35, "MI"),
        ("Buffalo NY", 42.88, -78.87, "NY"),
        ("Niagara Falls NY", 43.09, -79.04, "NY"),
        ("Presque Isle ME", 46.68, -68.01, "ME"),
    ]
    for label, lat, lon, expected_state in us_points:
        assert is_location_in_canada(lat, lon) is False, f"{label} should be in the US"
        assert infer_us_state_from_lat_lon(lat, lon) == expected_state

    assert is_border_straddling_bbox(
        {"minLat": 44.92, "maxLat": 45.08, "minLon": -73.0, "maxLon": -72.8}
    )


def test_nass_annual_survey_filtering_rejects_forecasts() -> None:
    rows = [
        {
            "year": 2023,
            "reference_period_desc": "YEAR",
            "source_desc": "SURVEY",
            "domain_desc": "TOTAL",
            "freq_desc": "ANNUAL",
            "class_desc": "ALL CLASSES",
            "Value": "201.0",
        },
        {
            "year": 2023,
            "reference_period_desc": "YEAR - AUG FORECAST",
            "source_desc": "SURVEY",
            "domain_desc": "TOTAL",
            "freq_desc": "ANNUAL",
            "class_desc": "ALL CLASSES",
            "Value": "155.0",
        },
        {
            "year": 2023,
            "reference_period_desc": "YEAR",
            "source_desc": "CENSUS",
            "domain_desc": "TOTAL",
            "freq_desc": "ANNUAL",
            "class_desc": "ALL CLASSES",
            "Value": "180.0",
        },
    ]
    extracted = extract_annual_survey_yields(rows, "mais")
    assert extracted == {2023: 201.0}


def test_security_and_validation_guards() -> None:
    # Windows reserved names & path traversal rejected in cache
    for bad_key in ("CON", "NUL", "PRN", "AUX", "COM1", "LPT1", "../secret", "a/b"):
        with pytest.raises(ValueError):
            write_cache("nasa-power", bad_key, {"seasons": []})
        with pytest.raises(ValueError):
            read_cache("nasa-power", bad_key)

    # Regime whitelist
    with pytest.raises(ValueError):
        validate_regime("constructor")

    # Cycle years bounds
    for bad_years in (0, 1, 7, 2.5, "abc"):
        with pytest.raises(ValueError):
            validate_cycle_years(bad_years)

    # Offset normalization and validation
    assert normalize_cycle_offset(-1, 4) == 3
    assert normalize_cycle_offset(-5, 4) == 3
    with pytest.raises(ValueError):
        normalize_cycle_offset(1.5, 4)

    # Optimizer filters unknown / prototype crop names without recursion error
    res = find_best_multi_crop_rotations_for_yield(
        pair_matrix={"pairs": {}},
        cycle_years=2,
        available_crops=["mais", "soya", "constructor", "__proto__", "toString"],
    )
    assert isinstance(res, list)


def test_geotiff_and_npy_strict_binary_validation() -> None:
    # Reject 3-channel RGB GeoTIFF (SamplesPerPixel=3, Photometric=2)
    buf = bytearray(256)
    buf[0:2] = b"II"
    struct.pack_into("<H", buf, 2, 42)
    struct.pack_into("<I", buf, 4, 8)
    tags = [
        (256, 3, 1, 2),   # Width = 2
        (257, 3, 1, 2),   # Height = 2
        (258, 3, 1, 8),   # BitsPerSample = 8
        (259, 3, 1, 1),   # Compression = 1
        (262, 3, 1, 2),   # Photometric = 2 (RGB)
        (273, 4, 1, 128), # StripOffsets = 128
        (277, 3, 1, 3),   # SamplesPerPixel = 3
        (279, 4, 1, 12),  # StripByteCounts = 12
    ]
    struct.pack_into("<H", buf, 8, len(tags))
    for i, (t, k, c, v) in enumerate(tags):
        pos = 10 + i * 12
        struct.pack_into("<HHI", buf, pos, t, k, c)
        if k == 3:
            struct.pack_into("<H", buf, pos + 8, v)
        else:
            struct.pack_into("<I", buf, pos + 8, v)
    with pytest.raises(ValueError, match="non thématique"):
        parse_uncompressed_tiff_u8(bytes(buf), expected_width=2, expected_height=2)

    # Reject Fortran-order .npy
    header_str = "{'descr': '<i2', 'fortran_order': True, 'shape': (2, 2), }"
    padding = (16 - ((10 + len(header_str) + 1) % 16)) % 16
    header_bytes = (header_str + " " * padding + "\n").encode("latin1")
    npy_buf = (
        b"\x93NUMPY\x01\x00"
        + struct.pack("<H", len(header_bytes))
        + header_bytes
        + b"\x00" * 8
    )
    with pytest.raises(ValueError, match="Fortran"):
        parse_npy_grid(npy_buf)


def test_end_to_end_cached_pipeline_saint_hyacinthe_and_iowa() -> None:
    from field_shift.algorithm.yield_model import load_reference_regions_profiles

    with patch(
        "field_shift.algorithm.yield_model.search_hls30m_granules", return_value=[]
    ):
        qc_res = run_regional_yield_pipeline(
            lat=45.6, lon=-72.9, cycle_years=4, current_crop="mais"
        )
        assert qc_res["sourcesUsed"]["nassCalibration"] is False
        assert qc_res["climateTwin"]["status"] == "warmer_twin_found"
        assert qc_res["climateTwin"]["bestTwin"]["id"] == "us_midwest_iowa"
        assert len(qc_res["bestRotations"]) > 0

        ref_regions = load_reference_regions_profiles()
        iowa_reg = next(r for r in ref_regions if r["id"] == "us_midwest_iowa")
        ia_twin = find_climate_twin(
            projected_seasons=qc_res["climateProjection"]["projectedSeasons"],
            local_baseline_stats=iowa_reg["baselineStats"],
            candidate_regions=ref_regions,
            farm_coordinates={"lat": 42.015, "lon": -93.75},
        )
        assert ia_twin["status"] == "no_warmer_twin_in_catalog"
        assert ia_twin["bestTwin"] is None

