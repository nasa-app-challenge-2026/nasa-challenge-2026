"""Regional crop-pair evidence from aligned crop and vegetation-index grids.

This is the Python port of the empirical yield engine: connected history
signatures, one vegetation index per region, positive log-Ridge weather
adjustment, a shared yearly baseline and regularized pair/regime estimates.
Public results retain the existing camelCase JSON contract.
"""

from __future__ import annotations

import math
from collections import defaultdict

from field_shift.algorithm.yield_model.config import CONFIG, CROP_TAXONOMY, is_finite, is_integer, js_round
from field_shift.algorithm.yield_model.model_utils import (
    physical_effect_interval,
    relative_gain_pct,
    validate_physical_effect_pct,
)
from field_shift.algorithm.yield_model.sources.cache import same_bbox, validate_bbox


def _sum(values):
    """Preserve the original engine's left-to-right floating-point reductions."""
    total = 0
    for value in values:
        total += value
    return total


def _year_value(mapping, year):
    """JSON maps have string years; in-process Python callers may use integers."""
    return mapping.get(str(year), mapping.get(year))


def _at(values, index):
    if values is None or not is_integer(index) or index < 0 or index >= len(values):
        return None
    return values[int(index)]


def _family(crop):
    return CROP_TAXONOMY.get(crop, {}).get("family") or None


def _select_consistent_vigor_index(grids_by_year):
    evi_valid = 0
    ndvi_valid = 0
    for grid in (grids_by_year or {}).values():
        for value in (grid or {}).get("eviPixels") or []:
            if is_finite(value) and 0.05 < value <= 1:
                evi_valid += 1
        for value in (grid or {}).get("pixels") or []:
            if is_finite(value) and 0.05 < value <= 1:
                ndvi_valid += 1
    return "EVI" if evi_valid > 0 and evi_valid >= ndvi_valid * 0.5 else "NDVI"


def cluster_pixels_into_distinct_fields(*, crop_ids_by_year, grid_size=64, years):
    """Segment 4-connected pixels sharing the complete multi-year crop history."""
    try:
        size_number = float(grid_size)
    except (TypeError, ValueError) as error:
        raise ValueError("gridSize invalide : entier attendu entre 4 et 128.") from error
    if not is_integer(size_number) or not 4 <= size_number <= 128:
        raise ValueError("gridSize invalide : entier attendu entre 4 et 128.")
    size = int(size_number)
    signatures = []
    for pixel in range(size * size):
        sequence = [_at(_year_value(crop_ids_by_year, year), pixel) or "_" for year in years]
        signatures.append("|".join(sequence) if any(crop != "_" for crop in sequence) else None)

    visited = bytearray(size * size)
    fields = []
    directions = ((-1, 0), (1, 0), (0, -1), (0, 1))
    for pixel, signature in enumerate(signatures):
        if not signature or visited[pixel]:
            continue
        pixels = [pixel]
        visited[pixel] = 1
        head = 0
        while head < len(pixels):
            current = pixels[head]
            head += 1
            row, col = divmod(current, size)
            for row_delta, col_delta in directions:
                next_row, next_col = row + row_delta, col + col_delta
                if not 0 <= next_row < size or not 0 <= next_col < size:
                    continue
                neighbor = next_row * size + next_col
                if not visited[neighbor] and signatures[neighbor] == signature:
                    visited[neighbor] = 1
                    pixels.append(neighbor)
        fields.append({
            "fieldId": len(fields) + 1,
            "pixelIndices": pixels,
            "pixelCount": len(pixels),
            "areaHa": js_round(len(pixels) * 6.25, 2),
            "signature": signature,
        })
    return fields


def _is_interior_pure_pixel(pixel, current, crop, size):
    row, col = divmod(pixel, size)
    if row <= 0 or row >= size - 1 or col <= 0 or col >= size - 1:
        return False
    return (
        current[(row - 1) * size + col] == crop
        and current[(row + 1) * size + col] == crop
        and current[row * size + col - 1] == crop
        and current[row * size + col + 1] == crop
    )


def _transition_fields(previous_crop, current_crop):
    previous_family = _family(previous_crop)
    current_family = _family(current_crop)
    same_species = previous_crop == current_crop
    return {
        "prevCrop": previous_crop,
        "currCrop": current_crop,
        "pairKey": f"{previous_crop}>{current_crop}",
        "isMonoculture": same_species,
        "sameSpecies": same_species,
        "sameBotanicalFamily": previous_family is not None and previous_family == current_family,
        "prevFamily": previous_family,
        "currFamily": current_family,
    }


def build_transition_observations(
    *,
    ndvi_series=None,
    crop_history=None,
    climate_seasons=None,
    **kwargs,
):
    """Build field/year observations, or the historical point-format fallback."""
    if ndvi_series is None and "ndviSeries" in kwargs:
        ndvi_series = kwargs["ndviSeries"]
    if crop_history is None and "cropHistory" in kwargs:
        crop_history = kwargs["cropHistory"]
    if climate_seasons is None and "climateSeasons" in kwargs:
        climate_seasons = kwargs["climateSeasons"]
    ndvi_series = ndvi_series or {}
    crop_history = crop_history or {}
    climate_by_year = {season.get("year"): season for season in climate_seasons or []}
    grids_by_year = ndvi_series.get("gridsByYear") or {}
    vigor_index_used = _select_consistent_vigor_index(grids_by_year)
    band_key = "eviPixels" if vigor_index_used == "EVI" else "pixels"
    observations = []
    crop_ids_by_year = crop_history.get("cropIdsByYear")

    if crop_ids_by_year is not None:
        validate_bbox(ndvi_series.get("bbox"))
        validate_bbox(crop_history.get("bbox"))
        if (
            not same_bbox(ndvi_series.get("bbox"), crop_history.get("bbox"))
            or ndvi_series.get("nrows") != crop_history.get("gridSize")
            or ndvi_series.get("ncols") != crop_history.get("gridSize")
        ):
            raise ValueError("Grilles de cultures et de vigueur désalignées (bbox ou dimensions).")
        years = sorted(int(year) for year in crop_ids_by_year)
        grid_size = int(crop_history.get("gridSize") or ndvi_series.get("nrows") or 64)
        coordinates = ndvi_series.get("pixelCoordinates") or []
        distinct_fields = cluster_pixels_into_distinct_fields(
            crop_ids_by_year=crop_ids_by_year, grid_size=grid_size, years=years,
        )
        for previous_year, current_year in zip(years, years[1:]):
            if current_year != previous_year + 1:
                continue
            previous = _year_value(crop_ids_by_year, previous_year) or []
            current = _year_value(crop_ids_by_year, current_year) or []
            grid = _year_value(grids_by_year, current_year)
            if grid is None or not previous or not current:
                continue
            if len(previous) != grid_size ** 2 or len(current) != grid_size ** 2:
                raise ValueError("Grille de cultures incomplète.")
            band = grid.get(band_key)
            if band is None:
                continue
            if len(band) != grid_size ** 2:
                raise ValueError("Grille de vigueur incomplète.")
            climate = climate_by_year.get(current_year)
            if climate is None:
                raise ValueError(f"Saison climatique manquante pour {current_year}.")

            for field in distinct_fields:
                representative = field["pixelIndices"][0]
                previous_crop = previous[representative]
                current_crop = current[representative]
                if not previous_crop or not current_crop:
                    continue
                sum_weighted_vigor = 0
                sum_weights = 0
                interior_count = 0
                for pixel in field["pixelIndices"]:
                    value = band[pixel]
                    if is_finite(value) and 0.08 < value <= 1:
                        pure = _is_interior_pure_pixel(pixel, current, current_crop, grid_size)
                        weight = 2.0 if pure else 1.0
                        if pure:
                            interior_count += 1
                        sum_weighted_vigor += value * weight
                        sum_weights += weight
                if sum_weights == 0:
                    continue
                coordinate = _at(coordinates, representative) or {}
                observations.append({
                    "fieldId": field["fieldId"],
                    "pixelCount": field["pixelCount"],
                    "interiorPixelCount": interior_count,
                    "areaHa": field["areaHa"],
                    "vigorIndexUsed": vigor_index_used,
                    "lat": coordinate.get("lat"),
                    "lon": coordinate.get("lon"),
                    "prevYear": previous_year,
                    "currYear": current_year,
                    **_transition_fields(previous_crop, current_crop),
                    "ndvi": js_round(sum_weighted_vigor / sum_weights, 4),
                    "climate": climate,
                })
        return observations

    for point in crop_history.get("historyByPoint") or []:
        crops_by_year = point.get("cropsByYear") or {}
        years = sorted(int(year) for year in crops_by_year)
        for previous_year, current_year in zip(years, years[1:]):
            if current_year != previous_year + 1:
                continue
            previous_crop = (_year_value(crops_by_year, previous_year) or {}).get("cropId")
            current_crop = (_year_value(crops_by_year, current_year) or {}).get("cropId")
            if not previous_crop or not current_crop:
                continue
            grid = _year_value(grids_by_year, current_year) or {}
            vigor = _at(grid.get(band_key), point.get("pixelIndex"))
            if not is_finite(vigor) or vigor <= 0.08 or vigor > 1:
                continue
            observation = {
                "fieldId": point["pixelIndex"] + 1,
                "pixelCount": 1,
                "interiorPixelCount": 0,
                "areaHa": 6.25,
                "vigorIndexUsed": vigor_index_used,
                "prevYear": previous_year,
                "currYear": current_year,
                **_transition_fields(previous_crop, current_crop),
                "ndvi": vigor,
                "climate": climate_by_year.get(current_year),
            }
            for coordinate in ("lat", "lon"):
                if coordinate in point:
                    observation[coordinate] = point[coordinate]
            observations.append(observation)
    return observations


def _compute_weather_adjusted_ndvi(observations):
    """Fit centered log-Ridge, then remove the multiplicative weather effect."""
    with_climate = [observation for observation in observations if observation.get("climate") is not None]
    if len(with_climate) < 6:
        return [{**observation, "adjustedNdvi": observation["ndvi"]} for observation in observations]

    def climate_value(observation, key):
        value = observation["climate"].get(key)
        return 0 if value is None else value

    count = len(with_climate)
    mean_y = _sum(math.log(observation["ndvi"]) for observation in with_climate) / count
    mean_rain = _sum(climate_value(observation, "rainZScore") for observation in with_climate) / count
    mean_temp = _sum(climate_value(observation, "tempZScore") for observation in with_climate) / count
    ridge_lambda = CONFIG["hyperparameters"]["ridgeLambda"]
    s_rr = ridge_lambda
    s_tt = ridge_lambda
    s_rt = 0
    s_ry = 0
    s_ty = 0
    for observation in with_climate:
        rain = climate_value(observation, "rainZScore") - mean_rain
        temp = climate_value(observation, "tempZScore") - mean_temp
        response = math.log(observation["ndvi"]) - mean_y
        s_rr += rain * rain
        s_tt += temp * temp
        s_rt += rain * temp
        s_ry += rain * response
        s_ty += temp * response
    determinant = s_rr * s_tt - s_rt * s_rt
    if not is_finite(determinant) or determinant <= 0:
        raise ValueError("Ajustement météo impossible : système Ridge non fini ou singulier.")
    beta_rain = (s_tt * s_ry - s_rt * s_ty) / determinant
    beta_temp = (s_rr * s_ty - s_rt * s_ry) / determinant
    adjusted = []
    for observation in observations:
        if observation.get("climate") is None:
            adjusted.append({**observation, "adjustedNdvi": observation["ndvi"]})
            continue
        weather_effect = (
            beta_rain * climate_value(observation, "rainZScore")
            + beta_temp * climate_value(observation, "tempZScore")
        )
        try:
            vigor = math.exp(math.log(observation["ndvi"]) - weather_effect)
        except OverflowError as error:
            raise ValueError("Ajustement météo impossible : vigueur corrigée non positive ou non finie.") from error
        if not is_finite(vigor) or vigor <= 0:
            raise ValueError("Ajustement météo impossible : vigueur corrigée non positive ou non finie.")
        adjusted.append({**observation, "adjustedNdvi": vigor})
    return adjusted


def _field_reliability_weight(item):
    return min(3.0, 1.0 + 0.5 * (item.get("interiorPixelCount") or 0))


def _cluster_robust_std_error(items, raw_mean, prior_std_pct, prior_dof=4):
    count = len(items)
    if count == 0:
        return prior_std_pct
    weighted_squared_differences = 0
    weight_total = 0
    for item in items:
        weight = _field_reliability_weight(item)
        difference = item["deltaPct"] - raw_mean
        weighted_squared_differences += weight * difference * difference
        weight_total += weight
    sample_variance = (
        (weighted_squared_differences / weight_total) * (count / (count - 1))
        if count > 1 and weight_total > 0 else 0
    )
    field_component_variance = (
        ((count - 1) * sample_variance + prior_dof * prior_std_pct ** 2)
        / (max(1, count + prior_dof - 1) * count)
    )
    by_year = defaultdict(list)
    for item in items:
        by_year[item.get("year")].append(item)
    effective_years = len(by_year)
    year_means = []
    for year_items in by_year.values():
        weighted_sum = 0
        weight_total = 0
        for item in year_items:
            weight = _field_reliability_weight(item)
            weighted_sum += weight * item["deltaPct"]
            weight_total += weight
        year_means.append(weighted_sum / max(1, weight_total))
    mean_of_years = _sum(year_means) / max(1, effective_years)
    between_year_variance = (
        _sum((value - mean_of_years) ** 2 for value in year_means) / (effective_years - 1)
        if effective_years > 1 else 0
    )
    year_prior_std = prior_std_pct * 0.25
    year_component_variance = (
        ((effective_years - 1) * between_year_variance + 2 * year_prior_std ** 2)
        / (max(1, effective_years + 1) * max(1, effective_years))
    )
    return math.sqrt(field_component_variance + year_component_variance)


def _mean_vigor(observations):
    return _sum(observation["adjustedNdvi"] for observation in observations) / max(1, len(observations))


def compute_regional_pair_matrix(observations):
    """Estimate observed crop-pair effects, intervals, regimes and confidence."""
    for observation in observations:
        vigor = observation.get("ndvi")
        if not is_finite(vigor) or vigor <= 0 or vigor > 1:
            raise ValueError("Observation de vigueur invalide : valeur finie dans ]0, 1] attendue.")
        for key in ("rainZScore", "tempZScore"):
            value = (observation.get("climate") or {}).get(key)
            if value is not None and not is_finite(value):
                raise ValueError(f"Covariable météo invalide : {key}.")

    distinct_field_ids = {observation.get("fieldId") for observation in observations}
    total_pixels_covered = _sum(observation.get("pixelCount") or 1 for observation in observations)
    vigor_index_used = (observations[0].get("vigorIndexUsed") if observations else None) or "EVI"
    parameters = CONFIG["hyperparameters"]
    pair_prior_strength = parameters["pairPriorStrengthK"]
    regime_prior_strength = parameters["regimePriorStrengthK"]
    baseline_prior_strength = parameters["monocultureBaselinePriorK"]
    minimum_prior_std = parameters["minCropPriorStdPct"]
    by_target_crop = defaultdict(list)
    for observation in observations:
        by_target_crop[observation.get("currCrop")].append(observation)
    pair_deltas = defaultdict(list)
    prior_std_by_crop = {}

    for crop, crop_observations in by_target_crop.items():
        adjusted = _compute_weather_adjusted_ndvi(crop_observations)
        by_year = defaultdict(list)
        for observation in adjusted:
            by_year[observation.get("currYear")].append(observation)
        global_mean = _mean_vigor(adjusted)
        global_mono = [observation for observation in adjusted if observation.get("isMonoculture")]
        global_rot = [observation for observation in adjusted if not observation.get("isMonoculture")]
        raw_global_mono_mean = _mean_vigor(global_mono) if global_mono else global_mean
        raw_global_rot_mean = _mean_vigor(global_rot) if global_rot else global_mean
        global_mono_weight = len(global_mono) / (len(global_mono) + baseline_prior_strength)
        regularized_global_mono_mean = (
            global_mono_weight * raw_global_mono_mean + (1 - global_mono_weight) * global_mean
        )
        global_unified_baseline = 0.5 * regularized_global_mono_mean + 0.5 * raw_global_rot_mean
        crop_deltas_for_prior = []

        for year_observations in by_year.values():
            year_mean = _mean_vigor(year_observations)
            mono_year = [observation for observation in year_observations if observation.get("isMonoculture")]
            rot_year = [observation for observation in year_observations if not observation.get("isMonoculture")]
            raw_mono_year_mean = _mean_vigor(mono_year) if mono_year else regularized_global_mono_mean
            raw_rot_year_mean = _mean_vigor(rot_year) if rot_year else raw_global_rot_mean
            mono_year_weight = len(mono_year) / (len(mono_year) + baseline_prior_strength)
            regularized_mono_year_mean = (
                mono_year_weight * raw_mono_year_mean + (1 - mono_year_weight) * year_mean
            )
            rot_year_weight = len(rot_year) / (len(rot_year) + baseline_prior_strength)
            regularized_rot_year_mean = (
                rot_year_weight * raw_rot_year_mean + (1 - rot_year_weight) * year_mean
            )
            unified_baseline = (
                0.5 * regularized_mono_year_mean + 0.5 * regularized_rot_year_mean
            ) or global_unified_baseline

            for observation in year_observations:
                if not is_finite(unified_baseline) or unified_baseline <= 0:
                    raise ValueError("Référence de vigueur non positive ou non finie.")
                delta = validate_physical_effect_pct((observation["adjustedNdvi"] / unified_baseline - 1) * 100)
                delta_vs_mono = (
                    ((observation["adjustedNdvi"] - regularized_mono_year_mean) / regularized_mono_year_mean) * 100
                    if regularized_mono_year_mean > 0 else delta
                )
                crop_deltas_for_prior.append(delta)
                pair_deltas[observation.get("pairKey")].append({
                    "fieldId": observation.get("fieldId"),
                    "pixelCount": observation.get("pixelCount") or 1,
                    "interiorPixelCount": observation.get("interiorPixelCount") or 0,
                    "currCrop": observation.get("currCrop"),
                    "deltaPct": delta,
                    "deltaVsMonoPct": delta_vs_mono,
                    "year": observation.get("currYear"),
                    "regime": (observation.get("climate") or {}).get("regime") or "normal",
                    "ndvi": observation["ndvi"],
                    "adjustedNdvi": observation["adjustedNdvi"],
                })
        mean_delta = _sum(crop_deltas_for_prior) / max(1, len(crop_deltas_for_prior))
        std_delta = (
            math.sqrt(_sum((value - mean_delta) ** 2 for value in crop_deltas_for_prior) / (len(crop_deltas_for_prior) - 1))
            if len(crop_deltas_for_prior) > 1 else minimum_prior_std * 2
        )
        prior_std_by_crop[crop] = max(minimum_prior_std, std_delta)

    pairs = {}
    for pair_key, items in pair_deltas.items():
        previous_crop, current_crop = pair_key.split(">")[:2]
        count = len(items)
        unique_fields_count = len({item["fieldId"] for item in items})
        effective_years_count = len({item["year"] for item in items})
        total_pixels = _sum(item["pixelCount"] for item in items)
        prior_std = prior_std_by_crop.get(current_crop) or 7.5
        weighted_sum = 0
        weight_total = 0
        for item in items:
            weight = _field_reliability_weight(item)
            weighted_sum += item["deltaPct"] * weight
            weight_total += weight
        raw_mean = weighted_sum / max(1, weight_total)
        shrinkage = count / (count + pair_prior_strength)
        mean = raw_mean * shrinkage
        std_error = _cluster_robust_std_error(items, raw_mean, prior_std, pair_prior_strength)
        by_regime = {}
        for regime in ("normal", "sec", "chaud"):
            subset = [item for item in items if item["regime"] == regime]
            sub_count = len(subset)
            if sub_count == 0:
                by_regime[regime] = None
                continue
            sub_weighted_sum = 0
            sub_weight_total = 0
            for item in subset:
                weight = _field_reliability_weight(item)
                sub_weighted_sum += weight * item["deltaPct"]
                sub_weight_total += weight
            sub_raw_mean = sub_weighted_sum / max(1, sub_weight_total)
            sub_shrinkage = sub_count / (sub_count + regime_prior_strength)
            sub_mean = js_round(sub_shrinkage * sub_raw_mean + (1 - sub_shrinkage) * mean, 2)
            sub_std_error = _cluster_robust_std_error(subset, sub_raw_mean, prior_std, regime_prior_strength)
            by_regime[regime] = {
                "rawMeanEffectPct": js_round(sub_raw_mean, 2),
                "meanEffectPct": sub_mean,
                "stdErrorPct": js_round(sub_std_error, 2),
                "intervalPct": physical_effect_interval(sub_mean, [
                    min(sub_mean, js_round(sub_mean - sub_std_error, 1)),
                    max(sub_mean, js_round(sub_mean + sub_std_error, 1)),
                ]),
                "sampleCount": sub_count,
                "effectiveYearsCount": len({item["year"] for item in subset}),
            }
        previous_family = _family(previous_crop)
        current_family = _family(current_crop)
        if count >= CONFIG["sampling"]["minSamplesHighConfidence"] and effective_years_count >= 3:
            confidence = "elevee"
        elif count >= CONFIG["sampling"]["minSamplesMediumConfidence"] and effective_years_count >= 2:
            confidence = "moyenne"
        else:
            confidence = "faible"
        rounded_mean = js_round(mean, 2)
        rounded_std_error = js_round(std_error, 2)
        pairs[pair_key] = {
            "from": previous_crop,
            "to": current_crop,
            "pairKey": pair_key,
            "prevCrop": previous_crop,
            "currCrop": current_crop,
            "prevFamily": previous_family,
            "currFamily": current_family,
            "sameSpecies": previous_crop == current_crop,
            "sameBotanicalFamily": previous_family is not None and previous_family == current_family,
            "isMonoculture": previous_crop == current_crop,
            "rawMeanEffectPct": js_round(raw_mean, 2),
            "meanEffectPct": rounded_mean,
            "gainVsMonoculturePct": None,
            "stdErrorPct": rounded_std_error,
            "intervalPct": physical_effect_interval(rounded_mean, [
                min(rounded_mean, js_round(rounded_mean - rounded_std_error, 1)),
                max(rounded_mean, js_round(rounded_mean + rounded_std_error, 1)),
            ]),
            "sampleCount": count,
            "distinctFieldsCount": unique_fields_count,
            "effectiveYearsCount": effective_years_count,
            "pixelObservationsCount": total_pixels,
            "confidence": confidence,
            "byRegime": by_regime,
        }
    for pair_stat in pairs.values():
        monoculture = pairs.get(f"{pair_stat['to']}>{pair_stat['to']}")
        pair_stat["gainVsMonoculturePct"] = (
            relative_gain_pct(pair_stat["meanEffectPct"], monoculture["meanEffectPct"])
            if monoculture is not None else None
        )
    return {
        "referenceBaselineType": "unified_balanced_regional_baseline",
        "effectInterpretation": "observational_relative_vigor",
        "weatherAdjustmentMethod": "centered_log_ridge",
        "fieldSegmentationMethod": "connected_crop_history_signatures",
        "vigorIndexUsed": vigor_index_used,
        "totalDistinctFieldsInRegion": len(distinct_field_ids),
        "totalFieldTransitions": len(observations),
        "totalPixelTransitions": total_pixels_covered,
        "totalObservations": len(observations),
        "observedPairsCount": len(pairs),
        "pairs": pairs,
    }
