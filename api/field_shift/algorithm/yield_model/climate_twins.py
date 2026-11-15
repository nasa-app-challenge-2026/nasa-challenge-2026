"""Climate Twins (spatial analogues) and CMIP6 future rotation yield forecasting."""

from __future__ import annotations

import math

from field_shift.algorithm.yield_model.config import CONFIG, CROPS, is_finite, js_round
from field_shift.algorithm.yield_model.model_utils import (
    downgrade_confidence,
    min_confidence,
    physical_effect_interval,
    resolve_pair_evidence,
    validate_current_crop,
    validate_physical_effect_pct,
    validated_rotation_slots,
)
from field_shift.algorithm.yield_model.pair_transitions import (
    build_transition_observations,
    compute_regional_pair_matrix,
)
from field_shift.algorithm.yield_model.rotation import first_year, normalize_cycle_offset
from field_shift.algorithm.yield_model.sources.climate_validation import validate_climate_seasons
from field_shift.algorithm.yield_model.sources.crop_history import fetch_regional_crop_history
from field_shift.algorithm.yield_model.sources.nasa_cmip6_projection import (
    classify_season_against_baseline,
    compute_climate_baseline_stats,
)
from field_shift.algorithm.yield_model.sources.nasa_modis_ndvi import fetch_regional_ndvi_series
from field_shift.algorithm.yield_model.sources.nasa_power import fetch_nasa_power_series

REFERENCE_REGIONS_CATALOG = [
    {
        "id": "qc_nord_cote_nord",
        "name": "Sacré-Cœur / Côte-Nord, Québec (Climat boréal frais)",
        "lat": 48.0,
        "lon": -70.0,
        "hasSatelliteCropMatrix": False,
    },
    {
        "id": "qc_sud_monteregie",
        "name": "Saint-Hyacinthe / Montérégie, Québec (Vallée du Saint-Laurent)",
        "lat": 45.6,
        "lon": -72.9,
        "hasSatelliteCropMatrix": True,
    },
    {
        "id": "us_midwest_iowa",
        "name": "Story County / Ames, Iowa (Corn Belt américain)",
        "lat": 42.015,
        "lon": -93.75,
        "hasSatelliteCropMatrix": True,
    },
]


def _sum(values) -> float:
    total = 0.0
    for v in values:
        total += v
    return total


def load_reference_regions_profiles(*, start_year: int = 2018, end_year: int = 2024, **kwargs) -> list[dict]:
    """Load climate baseline and empirical crop-pair matrices for reference regions."""
    if "startYear" in kwargs:
        start_year = kwargs["startYear"]
    if "endYear" in kwargs:
        end_year = kwargs["endYear"]

    profiles = []
    skipped_regions = []

    for reg in REFERENCE_REGIONS_CATALOG:
        try:
            nasa_power = fetch_nasa_power_series(
                lat=reg["lat"],
                lon=reg["lon"],
                start_year=start_year,
                end_year=end_year,
            )
            baseline_stats = compute_climate_baseline_stats(nasa_power["seasons"])

            pair_matrix = None
            if reg["hasSatelliteCropMatrix"]:
                ndvi_series = fetch_regional_ndvi_series(
                    lat=reg["lat"],
                    lon=reg["lon"],
                    start_year=start_year,
                    end_year=end_year,
                )
                crop_history = fetch_regional_crop_history(
                    lat=reg["lat"],
                    lon=reg["lon"],
                    bbox=ndvi_series["bbox"],
                    grid_size=ndvi_series.get("nrows") or 64,
                    start_year=start_year,
                    end_year=end_year,
                )
                observations = build_transition_observations(
                    ndvi_series=ndvi_series,
                    crop_history=crop_history,
                    climate_seasons=nasa_power["seasons"],
                )
                pair_matrix = compute_regional_pair_matrix(observations)

            profiles.append(
                {
                    "id": reg["id"],
                    "name": reg["name"],
                    "coordinates": {"lat": reg["lat"], "lon": reg["lon"]},
                    "baselineStats": baseline_stats,
                    "pairMatrix": pair_matrix,
                }
            )
        except Exception as err:
            skipped_regions.append({"id": reg["id"], "reason": str(err)})

    if not any(p["pairMatrix"] is not None for p in profiles):
        raise ValueError(
            f"Aucune région de référence avec matrice satellite n'a pu être chargée : {skipped_regions}"
        )

    return profiles


def compute_normalized_climate_distance(
    target_climate: dict, region_baseline_stats: dict
) -> float:
    """Compute standardized weighted Euclidean agro-climatic distance."""
    means = region_baseline_stats["means"]
    stds = region_baseline_stats["stds"]
    weights = CONFIG["hyperparameters"]["climateDistanceWeights"]

    gdd_z = (target_climate["gddBase10"] - means["gddBase10"]) / max(40.0, stds["gddBase10"])
    temp_z = (target_climate["meanTempC"] - means["meanTempC"]) / max(0.4, stds["meanTempC"])
    heat_z = (target_climate["heatStressDays"] - means["heatStressDays"]) / max(
        2.0, stds["heatStressDays"]
    )
    rain_z = (target_climate["precipMm"] - means["precipMm"]) / max(30.0, stds["precipMm"])

    weighted_sq = (
        weights["gddBase10"] * gdd_z ** 2
        + weights["meanTempC"] * temp_z ** 2
        + weights["heatStressDays"] * heat_z ** 2
        + weights["precipMm"] * rain_z ** 2
    )
    return js_round(math.sqrt(weighted_sq), 3)


def find_climate_twin(
    *,
    projected_seasons=None,
    local_baseline_stats=None,
    candidate_regions=None,
    farm_coordinates=None,
    **kwargs,
) -> dict | None:
    """Identify the closest warmer reference region (Climate Twin) for projected_seasons."""
    if projected_seasons is None and "projectedSeasons" in kwargs:
        projected_seasons = kwargs["projectedSeasons"]
    if local_baseline_stats is None and "localBaselineStats" in kwargs:
        local_baseline_stats = kwargs["localBaselineStats"]
    if candidate_regions is None and "candidateRegions" in kwargs:
        candidate_regions = kwargs["candidateRegions"]
    if farm_coordinates is None and "farmCoordinates" in kwargs:
        farm_coordinates = kwargs["farmCoordinates"]

    validate_climate_seasons(projected_seasons)

    tail_len = min(5, len(projected_seasons))
    tail_window = projected_seasons[-tail_len:]

    def _mean_of(values):
        return _sum(values) / len(values)

    target_future_climate = {
        "gddBase10": js_round(_mean_of([s["gddBase10"] for s in tail_window]), 1),
        "meanTempC": js_round(_mean_of([s["meanTempC"] for s in tail_window]), 2),
        "heatStressDays": js_round(_mean_of([s["heatStressDays"] for s in tail_window]), 1),
        "precipMm": js_round(_mean_of([s["precipMm"] for s in tail_window]), 1),
    }

    with_matrices = [
        r
        for r in (candidate_regions or [])
        if isinstance(r, dict)
        and isinstance(r.get("pairMatrix"), dict)
        and len(r["pairMatrix"].get("pairs") or {}) > 0
    ]
    if not with_matrices:
        return None

    def _is_same_location(reg: dict) -> bool:
        if not farm_coordinates:
            return False
        coords = reg.get("coordinates") or {}
        return (
            abs(coords.get("lat", 0.0) - farm_coordinates["lat"]) < 0.25
            and abs(coords.get("lon", 0.0) - farm_coordinates["lon"]) < 0.25
        )

    external_regions = [r for r in with_matrices if not _is_same_location(r)]
    local_gdd = local_baseline_stats["means"]["gddBase10"]
    local_temp = local_baseline_stats["means"]["meanTempC"]
    warming_gdd = target_future_climate["gddBase10"] - local_gdd
    warmer_external_regions = [
        r
        for r in external_regions
        if r["baselineStats"]["means"]["gddBase10"] > local_gdd
    ]

    if not warmer_external_regions:
        return {
            "targetFutureClimate": target_future_climate,
            "warmingDeltaGdd": js_round(warming_gdd, 1),
            "warmingDeltaTempC": js_round(
                target_future_climate["meanTempC"] - local_temp, 2
            ),
            "bestTwin": None,
            "status": "no_warmer_twin_in_catalog",
            "reason": (
                "Aucune région de référence plus chaude dans le catalogue — "
                "prévision basée sur la matrice locale modulée par les régimes futurs CMIP6 (alpha = 0)."
            ),
            "candidatesRanked": [],
        }

    decay = CONFIG["hyperparameters"]["similarityDecayFactor"]
    ranked = []
    for reg in warmer_external_regions:
        distance = compute_normalized_climate_distance(
            target_future_climate, reg["baselineStats"]
        )
        similarity_pct = int(js_round(100.0 * math.exp(-decay * distance), 0))
        ranked.append(
            {
                "id": reg["id"],
                "name": reg["name"],
                "coordinates": reg["coordinates"],
                "isExternalTwin": not _is_same_location(reg),
                "distance": distance,
                "similarityPct": similarity_pct,
                "baselineMeans": reg["baselineStats"]["means"],
                "baselineStats": reg["baselineStats"],
                "pairMatrix": reg["pairMatrix"],
            }
        )
    ranked.sort(key=lambda item: item["distance"])

    return {
        "targetFutureClimate": target_future_climate,
        "warmingDeltaGdd": js_round(warming_gdd, 1),
        "warmingDeltaTempC": js_round(target_future_climate["meanTempC"] - local_temp, 2),
        "bestTwin": ranked[0],
        "status": "warmer_twin_found",
        "candidatesRanked": ranked,
    }


def compute_yearly_blending_alpha(
    *,
    projected_season=None,
    local_baseline_stats=None,
    twin_baseline_stats=None,
    **kwargs,
) -> float:
    """Compute annual climate-twin blending weight alpha(y) in [0, 1]."""
    if projected_season is None and "projectedSeason" in kwargs:
        projected_season = kwargs["projectedSeason"]
    if local_baseline_stats is None and "localBaselineStats" in kwargs:
        local_baseline_stats = kwargs["localBaselineStats"]
    if twin_baseline_stats is None and "twinBaselineStats" in kwargs:
        twin_baseline_stats = kwargs["twinBaselineStats"]

    if not twin_baseline_stats:
        return 0
    local_gdd = local_baseline_stats["means"]["gddBase10"]
    twin_gdd = (twin_baseline_stats.get("means") or {}).get("gddBase10", local_gdd)
    delta_twin_gdd = twin_gdd - local_gdd
    season_warming_gdd = max(0.0, projected_season["gddBase10"] - local_gdd)

    if delta_twin_gdd > 40:
        raw_alpha = season_warming_gdd / delta_twin_gdd
        return js_round(min(1.0, max(0.0, raw_alpha)), 3)
    return 0


def _resolve_pair_effect_for_region(
    pair_stat: dict | None,
    projected_season: dict,
    reference_baseline_stats: dict | None,
) -> dict | None:
    if not pair_stat:
        return None

    regime_in_region = (
        classify_season_against_baseline(projected_season, reference_baseline_stats)
        if isinstance(reference_baseline_stats, dict)
        and reference_baseline_stats.get("thresholds")
        else projected_season.get("regime") or "normal"
    )

    evidence = resolve_pair_evidence(pair_stat, regime_in_region)
    by_regime = pair_stat.get("byRegime") or {}
    regime_entry = by_regime.get(regime_in_region)
    normal_entry = by_regime.get("normal")
    min_samples_mod = CONFIG["sampling"]["minRegimeSamplesForStressModulation"]

    effect = evidence["meanEffectPct"]

    def _half_width(entry: dict) -> float:
        if entry.get("stdErrorPct") is not None:
            return entry["stdErrorPct"]
        return max(
            entry["meanEffectPct"] - entry["intervalPct"][0],
            entry["intervalPct"][1] - entry["meanEffectPct"],
        )

    base_half_width = _half_width(evidence)

    if (
        regime_in_region in ("sec", "chaud")
        and regime_entry
        and normal_entry
        and regime_entry.get("sampleCount", 0) >= min_samples_mod
        and normal_entry.get("sampleCount", 0) >= min_samples_mod
    ):
        normal_evidence = resolve_pair_evidence(pair_stat, "normal")
        stress_delta = evidence["meanEffectPct"] - normal_evidence["meanEffectPct"]
        means = (reference_baseline_stats or {}).get("means") or {}
        stds = (reference_baseline_stats or {}).get("stds") or {}
        # Unknown moisture: 0.55 gives a factor of exactly 1, no modulation (not a measure).
        root_wetness = (
            means["soilMoistureRoot"]
            if means.get("soilMoistureRoot") is not None
            else 0.55
        )
        soil_vulnerability_factor = max(0.75, min(1.35, (1.0 - root_wetness) / 0.45))
        region_rain_mean = (
            means["precipMm"]
            if means.get("precipMm") is not None
            else projected_season["precipMm"]
        )
        region_rain_std = stds.get("precipMm") or 50.0
        region_rain_z = (projected_season["precipMm"] - region_rain_mean) / region_rain_std
        drought_intensity = max(0.0, -region_rain_z) * 0.15
        stress_factor = soil_vulnerability_factor * (1.0 + drought_intensity)
        effect = normal_evidence["meanEffectPct"] + stress_delta * stress_factor
        validate_physical_effect_pct(effect, "Extrapolation du stress climatique")
        if stress_factor != 1:
            base_half_width = (
                abs(stress_factor) * base_half_width
                + abs(1.0 - stress_factor) * _half_width(normal_evidence)
            )
            evidence = {
                **evidence,
                "sampleCount": min(evidence["sampleCount"], normal_evidence["sampleCount"]),
                "effectiveYearsCount": min(
                    evidence["effectiveYearsCount"],
                    normal_evidence["effectiveYearsCount"],
                ),
                "confidence": min_confidence(
                    evidence["confidence"], normal_evidence["confidence"]
                ),
            }

    rounded_effect = validate_physical_effect_pct(js_round(effect, 2))
    return {
        "regimeUsed": regime_in_region,
        "meanEffectPct": rounded_effect,
        "intervalPct": physical_effect_interval(
            rounded_effect,
            [
                min(rounded_effect, js_round(rounded_effect - base_half_width, 1)),
                max(rounded_effect, js_round(rounded_effect + base_half_width, 1)),
            ],
        ),
        "sampleCount": evidence["sampleCount"],
        "effectiveYearsCount": evidence["effectiveYearsCount"],
        "regimeSampleCount": evidence["regimeSampleCount"],
        "confidence": evidence["confidence"],
    }


def blend_pair_effect_for_season(
    *,
    pair_key=None,
    projected_season=None,
    alpha=None,
    local_pair_matrix=None,
    twin_pair_matrix=None,
    local_baseline_stats=None,
    twin_baseline_stats=None,
    unobserved_penalty_pct=-2.0,
    **kwargs,
) -> dict:
    """Blend local and climate-twin pair effects according to annual weight alpha."""
    if pair_key is None and "pairKey" in kwargs:
        pair_key = kwargs["pairKey"]
    if projected_season is None and "projectedSeason" in kwargs:
        projected_season = kwargs["projectedSeason"]
    if local_pair_matrix is None and "localPairMatrix" in kwargs:
        local_pair_matrix = kwargs["localPairMatrix"]
    if twin_pair_matrix is None and "twinPairMatrix" in kwargs:
        twin_pair_matrix = kwargs["twinPairMatrix"]
    if local_baseline_stats is None and "localBaselineStats" in kwargs:
        local_baseline_stats = kwargs["localBaselineStats"]
    if twin_baseline_stats is None and "twinBaselineStats" in kwargs:
        twin_baseline_stats = kwargs["twinBaselineStats"]
    if "unobservedPenaltyPct" in kwargs:
        unobserved_penalty_pct = kwargs["unobservedPenaltyPct"]

    if not is_finite(alpha) or alpha < 0 or alpha > 1:
        raise ValueError("Poids du jumeau ou pénalité de paire invalide.")
    validate_physical_effect_pct(unobserved_penalty_pct, "Pénalité de paire inconnue")

    def _lookup(matrix: dict | None) -> dict | None:
        if not isinstance(matrix, dict):
            return None
        pairs = matrix.get("pairs")
        if not isinstance(pairs, dict) or pair_key not in pairs:
            return None
        return pairs[pair_key]

    local = (
        _resolve_pair_effect_for_region(
            _lookup(local_pair_matrix), projected_season, local_baseline_stats
        )
        if alpha < 1
        else None
    )
    twin = (
        _resolve_pair_effect_for_region(
            _lookup(twin_pair_matrix),
            projected_season,
            twin_baseline_stats or local_baseline_stats,
        )
        if alpha > 0
        else None
    )
    half_w = CONFIG["hyperparameters"]["unobservedHalfWidthPct"]
    unknown = {
        "meanEffectPct": unobserved_penalty_pct,
        "intervalPct": physical_effect_interval(
            unobserved_penalty_pct,
            [unobserved_penalty_pct - half_w, unobserved_penalty_pct + half_w],
        ),
        "sampleCount": 0,
        "effectiveYearsCount": 0,
        "confidence": "faible",
    }
    components = [
        c
        for c in (
            {"weight": 1 - alpha, "evidence": local or unknown, "observed": bool(local)},
            {"weight": alpha, "evidence": twin or unknown, "observed": bool(twin)},
        )
        if c["weight"] > 0
    ]

    def _weighted(fn) -> float:
        return _sum(c["weight"] * fn(c["evidence"]) for c in components)

    observed_weight = _sum(c["weight"] * (1 if c["observed"] else 0) for c in components)
    mean_effect_pct = validate_physical_effect_pct(
        js_round(_weighted(lambda e: e["meanEffectPct"]), 2)
    )
    return {
        "pairKey": pair_key,
        "observed": observed_weight >= 1.0 - 1e-12,
        "observedWeight": observed_weight,
        "meanEffectPct": mean_effect_pct,
        "intervalPct": physical_effect_interval(
            mean_effect_pct,
            [
                min(mean_effect_pct, js_round(_weighted(lambda e: e["intervalPct"][0]), 1)),
                max(mean_effect_pct, js_round(_weighted(lambda e: e["intervalPct"][1]), 1)),
            ],
        ),
        "localEffectPct": local["meanEffectPct"] if local is not None else None,
        "twinEffectPct": twin["meanEffectPct"] if twin is not None else None,
        "localRegimeUsed": local["regimeUsed"] if local is not None else None,
        "twinRegimeUsed": twin["regimeUsed"] if twin is not None else None,
        "alphaTwin": alpha,
        "sampleCount": min(c["evidence"]["sampleCount"] for c in components),
        "effectiveYearsCount": min(c["evidence"]["effectiveYearsCount"] for c in components),
        "confidence": min_confidence(*(c["evidence"]["confidence"] for c in components)),
    }


def forecast_future_rotation_yield(
    *,
    rotation=None,
    current_crop=None,
    offset=0,
    projected_seasons=None,
    local_pair_matrix=None,
    twin_match=None,
    local_baseline_stats=None,
    unobserved_penalty_pct=-2.0,
    historical_confidence=None,
    **kwargs,
) -> dict:
    """Forecast year-by-year future rotation yield over projected_seasons."""
    if current_crop is None and "currentCrop" in kwargs:
        current_crop = kwargs["currentCrop"]
    if projected_seasons is None and "projectedSeasons" in kwargs:
        projected_seasons = kwargs["projectedSeasons"]
    if local_pair_matrix is None and "localPairMatrix" in kwargs:
        local_pair_matrix = kwargs["localPairMatrix"]
    if twin_match is None and "twinMatch" in kwargs:
        twin_match = kwargs["twinMatch"]
    if local_baseline_stats is None and "localBaselineStats" in kwargs:
        local_baseline_stats = kwargs["localBaselineStats"]
    if "unobservedPenaltyPct" in kwargs:
        unobserved_penalty_pct = kwargs["unobservedPenaltyPct"]
    if historical_confidence is None and "historicalConfidence" in kwargs:
        historical_confidence = kwargs["historicalConfidence"]

    validate_current_crop(current_crop)
    slots = validated_rotation_slots(rotation)
    cycle_len = len(slots)
    safe_offset = normalize_cycle_offset(offset, cycle_len)

    if cycle_len == 0 or not projected_seasons:
        return {
            "meanFutureYieldGainPct": 0,
            "futureYieldGainRangePct": [0, 0],
            "confidence": "faible",
            "yearlyForecast": [],
        }

    validate_climate_seasons(projected_seasons)
    validate_physical_effect_pct(unobserved_penalty_pct, "Pénalité de paire inconnue")
    best_twin = (twin_match or {}).get("bestTwin") if isinstance(twin_match, dict) else None
    twin_pair_matrix = best_twin.get("pairMatrix") if isinstance(best_twin, dict) else None
    twin_baseline_stats = (
        best_twin.get("baselineStats") if isinstance(best_twin, dict) else None
    )
    twin_distance = (
        best_twin.get("distance", 0)
        if isinstance(best_twin, dict) and best_twin.get("distance") is not None
        else 0
    )
    if not is_finite(twin_distance) or twin_distance < 0:
        raise ValueError("Distance au jumeau climatique invalide.")

    hyper = CONFIG["hyperparameters"]
    horizon_uncertainty_per_year_pct = hyper["horizonUncertaintyPerYearPct"]
    twin_distance_uncertainty_factor = hyper["twinDistanceUncertaintyFactor"]
    long_horizon_downgrade_years = hyper["longHorizonConfidenceDowngradeYears"]

    yearly_forecast = []
    baseline_end_year = (local_baseline_stats.get("period") or {}).get(
        "endYear", projected_seasons[0]["year"] - 1
    )
    sum_gain = 0.0
    sum_low = 0.0
    sum_high = 0.0
    evaluated_transitions_count = 0
    observed_weight_sum = 0.0
    min_sample_in_horizon = math.inf
    confidence = "elevee"

    prev_crop = (
        current_crop
        or slots[(safe_offset - 1 + cycle_len) % cycle_len].get("crop")
        or first_year({"rotation": rotation, "offset": safe_offset}).get("crop")
    )

    for idx, season in enumerate(projected_seasons):
        slot = slots[(safe_offset + idx) % cycle_len]
        curr_crop = slot["crop"]

        alpha = compute_yearly_blending_alpha(
            projected_season=season,
            local_baseline_stats=local_baseline_stats,
            twin_baseline_stats=twin_baseline_stats,
        )

        is_multi_year_continuation = (
            curr_crop == prev_crop and (CROPS.get(curr_crop, {}).get("years") or 1) > 1
        )
        pair_key = f"{prev_crop}>{curr_crop}"
        blended = blend_pair_effect_for_season(
            pair_key=pair_key,
            projected_season=season,
            alpha=alpha,
            local_pair_matrix=local_pair_matrix,
            twin_pair_matrix=twin_pair_matrix,
            local_baseline_stats=local_baseline_stats,
            twin_baseline_stats=twin_baseline_stats,
            unobserved_penalty_pct=unobserved_penalty_pct,
        )

        horizon_uncertainty_pct = js_round(
            horizon_uncertainty_per_year_pct * max(0, season["year"] - baseline_end_year)
            + twin_distance_uncertainty_factor * alpha * twin_distance,
            2,
        )
        low_pct, high_pct = physical_effect_interval(
            blended["meanEffectPct"],
            [
                min(
                    blended["meanEffectPct"],
                    js_round(blended["intervalPct"][0] - horizon_uncertainty_pct, 1),
                ),
                max(
                    blended["meanEffectPct"],
                    js_round(blended["intervalPct"][1] + horizon_uncertainty_pct, 1),
                ),
            ],
        )

        evaluated_transitions_count += 1
        observed_weight_sum += blended["observedWeight"]
        min_sample_in_horizon = min(min_sample_in_horizon, blended["sampleCount"])
        confidence = min_confidence(confidence, blended["confidence"])
        sum_gain += blended["meanEffectPct"]
        sum_low += low_pct
        sum_high += high_pct

        yearly_forecast.append(
            {
                "year": season["year"],
                "stepInHorizon": idx + 1,
                "fromCrop": prev_crop,
                "crop": curr_crop,
                "pairKey": pair_key,
                "observed": blended["observed"],
                "sampleCount": blended["sampleCount"],
                "effectiveYearsCount": blended["effectiveYearsCount"],
                "confidence": blended["confidence"],
                "isMultiYearContinuation": is_multi_year_continuation,
                "projectedRegime": season.get("regime"),
                "twinRegimeUsed": blended["twinRegimeUsed"],
                "projectedTempC": season["meanTempC"],
                "projectedGdd10": season["gddBase10"],
                "projectedPrecipMm": season["precipMm"],
                "alphaTwin": alpha,
                "expectedYieldGainPct": blended["meanEffectPct"],
                "localComponentPct": blended["localEffectPct"],
                "twinComponentPct": blended["twinEffectPct"],
                "intervalPct": [low_pct, high_pct],
            }
        )
        prev_crop = curr_crop

    denom = max(1, evaluated_transitions_count)
    mean_future_yield_gain_pct = validate_physical_effect_pct(
        js_round(sum_gain / denom, 2)
    )
    future_yield_gain_range_pct = physical_effect_interval(
        mean_future_yield_gain_pct,
        [
            min(mean_future_yield_gain_pct, js_round(sum_low / denom, 1)),
            max(mean_future_yield_gain_pct, js_round(sum_high / denom, 1)),
        ],
    )
    observed_share = js_round(observed_weight_sum / denom, 2)

    if historical_confidence:
        confidence = min_confidence(confidence, historical_confidence)

    if projected_seasons[-1]["year"] - baseline_end_year >= long_horizon_downgrade_years:
        confidence = downgrade_confidence(confidence)

    regime_counts = {"normal": 0, "sec": 0, "chaud": 0}
    for s in projected_seasons:
        reg = s.get("regime")
        regime_counts[reg] = regime_counts.get(reg, 0) + 1

    first_alpha = yearly_forecast[0]["alphaTwin"] if yearly_forecast else 0
    last_alpha = yearly_forecast[-1]["alphaTwin"] if yearly_forecast else 0
    mean_alpha = js_round(
        _sum(y["alphaTwin"] for y in yearly_forecast) / len(yearly_forecast), 3
    )

    return {
        "meanFutureYieldGainPct": mean_future_yield_gain_pct,
        "aggregation": "equal_weight_annual_relative_vigor",
        "futureYieldGainRangePct": future_yield_gain_range_pct,
        "observedShare": observed_share,
        "minSampleInHorizon": int(min_sample_in_horizon)
        if is_finite(min_sample_in_horizon)
        else 0,
        "confidence": confidence,
        "horizonYearsCount": len(projected_seasons),
        "alphaTrajectory": {
            "startYearAlpha": first_alpha,
            "endYearAlpha": last_alpha,
            "meanAlpha": mean_alpha,
        },
        "futureRegimeDistribution": regime_counts,
        "yearlyForecast": yearly_forecast,
    }

