"""NASA NEX-GDDP-CMIP6 daily climate projections via NASA POWER Projection API."""

from __future__ import annotations

import math
import re
from urllib.parse import urlencode

from field_shift.algorithm.yield_model.config import is_finite, is_integer, js_round
from field_shift.algorithm.yield_model.sources import http
from field_shift.algorithm.yield_model.sources.cache import (
    number_text,
    read_bounded_json,
    read_cache,
    region_cell_key,
    write_cache,
)
from field_shift.algorithm.yield_model.sources.climate_validation import validate_climate_seasons
from field_shift.algorithm.yield_model.sources.nasa_power import summarize_growing_seasons

POWER_PROJECTION_ENDPOINT = "https://power.larc.nasa.gov/api/projection/daily/point"
ALLOWED_SCENARIOS = frozenset({"ssp126", "ssp245", "ssp370"})
SAFE_MODEL_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


def _sum(values) -> float:
    total = 0.0
    for value in values:
        total += value
    return total


def _mean(values: list[float]) -> float:
    return _sum(values) / len(values)


def _std(values: list[float], mean_val: float) -> float:
    variance = _sum((v - mean_val) ** 2 for v in values) / max(1, len(values) - 1)
    return math.sqrt(variance) or 1.0


def compute_climate_baseline_stats(historical_seasons: list[dict]) -> dict:
    """Compute historical reference statistics (mean, std, quartiles, trends)."""
    validate_climate_seasons(historical_seasons)
    n = len(historical_seasons)
    if n == 0:
        raise ValueError(
            "Aucune saison historique disponible pour établir la référence climatique."
        )

    gdds = [float(s["gddBase10"]) for s in historical_seasons]
    temps = [float(s["meanTempC"]) for s in historical_seasons]
    heats = [float(s["heatStressDays"]) for s in historical_seasons]
    rains = [float(s["precipMm"]) for s in historical_seasons]
    roots = [
        float(s["soilMoistureRoot"])
        for s in historical_seasons
        if is_finite(s.get("soilMoistureRoot")) and 0 <= s["soilMoistureRoot"] <= 1
    ]

    sorted_rains = sorted(rains)
    sorted_temps = sorted(temps)

    mean_gdd = _mean(gdds)
    mean_temp = _mean(temps)
    mean_heat = _mean(heats)
    mean_rain = _mean(rains)
    mean_root = _mean(roots) if roots else 0.5

    std_gdd = _std(gdds, mean_gdd)
    std_temp = _std(temps, mean_temp)
    std_heat = _std(heats, mean_heat)
    std_rain = _std(rains, mean_rain)

    years = [int(s["year"]) for s in historical_seasons]
    mean_year = _mean(years)
    s_yy = _sum((y - mean_year) ** 2 for y in years) or 1.0
    gdd_slope_per_year = (
        _sum((y - mean_year) * (gdds[i] - mean_gdd) for i, y in enumerate(years)) / s_yy
    )
    temp_slope_per_year = (
        _sum((y - mean_year) * (temps[i] - mean_temp) for i, y in enumerate(years)) / s_yy
    )

    return {
        "period": {
            "startYear": min(years),
            "endYear": max(years),
            "yearsCount": n,
        },
        "means": {
            "gddBase10": js_round(mean_gdd, 1),
            "meanTempC": js_round(mean_temp, 2),
            "heatStressDays": js_round(mean_heat, 1),
            "precipMm": js_round(mean_rain, 1),
            "soilMoistureRoot": js_round(mean_root, 3),
        },
        "stds": {
            "gddBase10": js_round(std_gdd, 1),
            "meanTempC": js_round(std_temp, 2),
            "heatStressDays": js_round(std_heat, 1),
            "precipMm": js_round(std_rain, 1),
        },
        "thresholds": {
            "p25RainMm": sorted_rains[math.floor(n * 0.25)],
            "p75TempC": sorted_temps[math.floor(n * 0.75)],
        },
        "observedTrends": {
            "gddPerDecade": js_round(gdd_slope_per_year * 10, 1),
            "tempCPerDecade": js_round(temp_slope_per_year * 10, 2),
        },
    }


def classify_season_against_baseline(season: dict, baseline_stats: dict) -> str:
    """Classify a season into 'sec', 'chaud', or 'normal' against baseline thresholds."""
    thresholds = baseline_stats["thresholds"]
    if season["precipMm"] <= thresholds["p25RainMm"]:
        return "sec"
    if season["meanTempC"] >= thresholds["p75TempC"]:
        return "chaud"
    return "normal"


def recalibrate_seasons_with_baseline(
    raw_seasons: list[dict] | None, baseline_stats: dict
) -> list[dict]:
    """Recompute Z-scores, deltas, secular deltas and regimes against baseline_stats."""
    if not raw_seasons:
        return []
    means = baseline_stats["means"]
    stds = baseline_stats["stds"]

    sorted_seasons = sorted(
        raw_seasons,
        key=lambda s: s.get("year") if isinstance(s, dict) and is_finite(s.get("year")) else 0,
    )
    validate_climate_seasons(sorted_seasons)

    recalibrated = []
    for s in sorted_seasons:
        rain_z = js_round((s["precipMm"] - means["precipMm"]) / stds["precipMm"], 2)
        temp_z = js_round((s["meanTempC"] - means["meanTempC"]) / stds["meanTempC"], 2)
        regime = classify_season_against_baseline(s, baseline_stats)
        recalibrated.append(
            {
                "year": s["year"],
                "meanTempC": s["meanTempC"],
                "gddBase10": s["gddBase10"],
                "heatStressDays": s["heatStressDays"],
                "precipMm": s["precipMm"],
                "rainZScore": rain_z,
                "tempZScore": temp_z,
                "deltaGddVsBaseline": js_round(s["gddBase10"] - means["gddBase10"], 1),
                "deltaTempCVsBaseline": js_round(s["meanTempC"] - means["meanTempC"], 2),
                "secularDeltaGdd": js_round(max(0.0, s["gddBase10"] - means["gddBase10"]), 1),
                "secularDeltaTempC": js_round(max(0.0, s["meanTempC"] - means["meanTempC"]), 2),
                "regime": regime,
            }
        )
    return recalibrated


def _unwrap_scenario_param(param_obj: object, scenario: str) -> dict:
    if (
        not isinstance(param_obj, dict)
        or scenario not in param_obj
        or not isinstance(param_obj[scenario], dict)
    ):
        raise ValueError(
            f"Scénario {scenario} absent de la réponse NASA POWER Projection."
        )
    return param_obj[scenario]


def fetch_future_climate_projection(
    *,
    lat,
    lon,
    historical_seasons=None,
    start_year=2027,
    end_year=2040,
    scenario="ssp245",
    model="ensemble",
    **kwargs,
) -> dict:
    """Fetch CMIP6 projected growing seasons from NASA POWER Projection API."""
    if historical_seasons is None and "historicalSeasons" in kwargs:
        historical_seasons = kwargs["historicalSeasons"]
    if "startYear" in kwargs:
        start_year = kwargs["startYear"]
    if "endYear" in kwargs:
        end_year = kwargs["endYear"]

    clean_scenario = str(scenario or "ssp245").lower()
    if clean_scenario not in ALLOWED_SCENARIOS:
        allowed_str = ", ".join(sorted(ALLOWED_SCENARIOS))
        raise ValueError(
            f'Scénario CMIP6 invalide : "{scenario}". Valeurs autorisées : {allowed_str}'
        )
    clean_model = str(model or "ensemble")
    if not SAFE_MODEL_RE.fullmatch(clean_model):
        raise ValueError(f'Identifiant de modèle CMIP6 invalide : "{model}"')

    try:
        s_year = float(start_year)
        e_year = float(end_year)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"Plage d'années de projection invalide : {start_year}–{end_year}"
        ) from error

    if (
        not is_integer(s_year)
        or not is_integer(e_year)
        or s_year < 2015
        or e_year > 2100
        or e_year < s_year
        or e_year - s_year > 80
    ):
        raise ValueError(
            f"Plage d'années de projection invalide : {start_year}–{end_year}"
        )
    s_year_int, e_year_int = int(s_year), int(e_year)

    baseline_stats = compute_climate_baseline_stats(historical_seasons)
    cell = region_cell_key(lat, lon, 0.25)
    cache_key = f"cmip6_{cell}_{clean_scenario}_{clean_model}_{s_year_int}_{e_year_int}"

    def _matches(data: dict) -> bool:
        validate_climate_seasons(
            data.get("projectedSeasons"), start_year=s_year_int, end_year=e_year_int
        )
        return data.get("scenario") == clean_scenario and data.get("model") == clean_model

    cached = read_cache("cmip6-projection", cache_key, _matches)
    if cached:
        return {
            **cached,
            "baselineStats": baseline_stats,
            "projectedSeasons": recalibrate_seasons_with_baseline(
                cached["projectedSeasons"], baseline_stats
            ),
            "fromCache": True,
        }

    num_lat, num_lon = float(lat), float(lon)
    params = {
        "parameters": "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR",
        "community": "AG",
        "longitude": number_text(num_lon),
        "latitude": number_text(num_lat),
        "start": f"{s_year_int}0101",
        "end": f"{e_year_int}1231",
        "model": clean_model,
        "scenario": clean_scenario,
        "time-standard": "UTC",
        "format": "JSON",
    }
    url = f"{POWER_PROJECTION_ENDPOINT}?{urlencode(params)}"
    response = http.fetch(url, headers={"Accept": "application/json"})
    if not response.ok:
        response.close()
        raise ValueError(
            f"NASA POWER Projection API (NEX-GDDP-CMIP6) a répondu HTTP {response.status} sur {url}"
        )

    raw = read_bounded_json(response)
    parameter = (raw or {}).get("properties", {}).get("parameter")
    if not isinstance(parameter, dict):
        raise ValueError(
            "Réponse NASA POWER Projection API invalide : properties.parameter manquant."
        )

    unwrapped = {
        "T2M": _unwrap_scenario_param(parameter.get("T2M"), clean_scenario),
        "T2M_MAX": _unwrap_scenario_param(parameter.get("T2M_MAX"), clean_scenario),
        "T2M_MIN": _unwrap_scenario_param(parameter.get("T2M_MIN"), clean_scenario),
        "PRECTOTCORR": _unwrap_scenario_param(parameter.get("PRECTOTCORR"), clean_scenario),
    }
    projected_seasons = validate_climate_seasons(
        recalibrate_seasons_with_baseline(
            summarize_growing_seasons(unwrapped), baseline_stats
        ),
        start_year=s_year_int,
        end_year=e_year_int,
    )
    if not projected_seasons:
        raise ValueError(
            f"Aucune saison estivale projetée retournée par NASA NEX-GDDP-CMIP6 pour ({lat}, {lon}) sur {s_year_int}–{e_year_int}."
        )

    payload = {
        "source": f"NASA POWER Projection API (NEX-GDDP-CMIP6 · {clean_model} · {clean_scenario})",
        "nature": "model_projection",
        "scenario": clean_scenario,
        "model": clean_model,
        "coordinates": {"lat": num_lat, "lon": num_lon},
        "period": {"startYear": s_year_int, "endYear": e_year_int},
        "baselineStats": baseline_stats,
        "projectedSeasons": projected_seasons,
    }
    return write_cache("cmip6-projection", cache_key, payload)

