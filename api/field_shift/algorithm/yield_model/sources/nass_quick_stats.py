"""USDA NASS QuickStats annual state yields (SURVEY / ANNUAL / YEAR / TOTAL)."""

from __future__ import annotations

import re
from urllib.parse import urlencode

from field_shift.algorithm.yield_model.config import CONFIG, is_finite, is_integer, js_round
from field_shift.algorithm.yield_model.model_utils import validate_physical_effect_pct
from field_shift.algorithm.yield_model.sources import http
from field_shift.algorithm.yield_model.sources.cache import read_bounded_json, read_cache, write_cache
from field_shift.algorithm.yield_model.sources.crop_history import is_location_in_canada

SAFE_STATE_RE = re.compile(r"^[A-Z]{2}$")

NASS_COMMODITY_MAP = {
    "mais": {
        "commodity_desc": "CORN",
        "class_desc": "ALL CLASSES",
        "util_practice_desc": "GRAIN",
        "statisticcat_desc": "YIELD",
        "unit_desc": "BU / ACRE",
        "toTonnesPerHa": 0.06277,
    },
    "soya": {
        "commodity_desc": "SOYBEANS",
        "class_desc": "ALL CLASSES",
        "statisticcat_desc": "YIELD",
        "unit_desc": "BU / ACRE",
        "toTonnesPerHa": 0.06725,
    },
    "ble": {
        "commodity_desc": "WHEAT",
        "class_desc": "ALL CLASSES",
        "statisticcat_desc": "YIELD",
        "unit_desc": "BU / ACRE",
        "toTonnesPerHa": 0.06725,
    },
    "orge": {
        "commodity_desc": "BARLEY",
        "class_desc": "ALL CLASSES",
        "statisticcat_desc": "YIELD",
        "unit_desc": "BU / ACRE",
        "toTonnesPerHa": 0.0538,
    },
    "patate": {
        "commodity_desc": "POTATOES",
        "class_desc": "ALL CLASSES",
        "statisticcat_desc": "YIELD",
        "unit_desc": "CWT / ACRE",
        "toTonnesPerHa": 0.11209,
    },
    "luzerne": {
        "commodity_desc": "HAY",
        "class_desc": "ALFALFA",
        "statisticcat_desc": "YIELD",
        "unit_desc": "TONS / ACRE",
        "toTonnesPerHa": 2.2417,
    },
}


def infer_us_state_from_lat_lon(lat, lon) -> str | None:
    """Infer US state alpha code from (lat, lon); return None for Canada or outside US."""
    if lat is None or lon is None:
        return None
    try:
        num_lat = float(lat)
        num_lon = float(lon)
    except (TypeError, ValueError):
        return None
    if not is_finite(num_lat) or not is_finite(num_lon):
        return None
    if is_location_in_canada(num_lat, num_lon) or num_lat < 24.5 or num_lat > 49.4:
        return None

    if 40.35 <= num_lat <= 43.5 and -96.6 <= num_lon <= -90.1:
        return "IA"
    if 43.5 <= num_lat <= 49.4 and -97.2 <= num_lon <= -89.5:
        return "MN"
    if 37.0 <= num_lat <= 42.5 and -91.5 <= num_lon <= -87.5:
        return "IL"
    if 42.5 <= num_lat <= 47.1 and -92.9 <= num_lon <= -86.8:
        return "WI"
    if 37.8 <= num_lat <= 41.8 and -88.1 <= num_lon <= -84.8:
        return "IN"
    if 38.4 <= num_lat <= 42.0 and -84.8 <= num_lon <= -80.5:
        return "OH"
    if 41.7 <= num_lat <= 47.5 and -90.4 <= num_lon <= -82.4:
        return "MI"
    if 45.9 <= num_lat <= 49.0 and -104.0 <= num_lon <= -96.5:
        return "ND"
    if 42.5 <= num_lat <= 45.9 and -104.0 <= num_lon <= -96.4:
        return "SD"
    if 40.0 <= num_lat <= 43.0 and -104.0 <= num_lon <= -95.3:
        return "NE"
    if 37.0 <= num_lat <= 40.0 and -102.0 <= num_lon <= -94.6:
        return "KS"
    if 40.5 <= num_lat <= 45.01 and -79.8 <= num_lon <= -73.3:
        return "NY"
    if 42.7 <= num_lat <= 45.01 and -73.3 < num_lon <= -71.5:
        return "VT"
    if 42.7 <= num_lat <= 45.3 and -71.5 < num_lon <= -70.7:
        return "NH"
    if 43.0 <= num_lat <= 47.46 and -71.08 <= num_lon <= -66.9:
        return "ME"
    return None


def build_nass_query_params(
    *,
    api_key=None,
    crop_id=None,
    state_alpha=None,
    start_year=None,
    end_year=None,
    **kwargs,
) -> dict[str, str]:
    """Build NASS QuickStats query parameters filtered to final annual survey yields."""
    if api_key is None and "apiKey" in kwargs:
        api_key = kwargs["apiKey"]
    if crop_id is None and "cropId" in kwargs:
        crop_id = kwargs["cropId"]
    if state_alpha is None and "stateAlpha" in kwargs:
        state_alpha = kwargs["stateAlpha"]
    if start_year is None and "startYear" in kwargs:
        start_year = kwargs["startYear"]
    if end_year is None and "endYear" in kwargs:
        end_year = kwargs["endYear"]

    query = NASS_COMMODITY_MAP.get(crop_id)
    if not query:
        raise ValueError(f"Culture NASS inconnue : {crop_id}")

    params = {
        "key": str(api_key),
        "source_desc": "SURVEY",
        "sector_desc": "CROPS",
        "commodity_desc": query["commodity_desc"],
        "class_desc": query["class_desc"],
        "statisticcat_desc": query["statisticcat_desc"],
        "unit_desc": query["unit_desc"],
        "domain_desc": "TOTAL",
        "agg_level_desc": "STATE",
        "freq_desc": "ANNUAL",
        "reference_period_desc": "YEAR",
        "state_alpha": str(state_alpha),
        "year__GE": str(start_year),
        "year__LE": str(end_year),
        "format": "JSON",
    }
    if "util_practice_desc" in query:
        params["util_practice_desc"] = query["util_practice_desc"]
    return params


def extract_annual_survey_yields(rows: list[dict] | None, crop_id: str) -> dict[int, float]:
    """Filter NASS rows to final annual survey yields, rejecting monthly forecasts."""
    query = NASS_COMMODITY_MAP.get(crop_id) or {}
    expected_class = query.get("class_desc") or "ALL CLASSES"
    result: dict[int, float] = {}
    exact_class_matched_year: set[int] = set()

    for r in rows or []:
        if not isinstance(r, dict):
            continue
        try:
            year_num = float(r.get("year"))
        except (TypeError, ValueError):
            continue
        if not is_integer(year_num):
            continue
        year = int(year_num)

        ref_period = r.get("reference_period_desc")
        if ref_period and str(ref_period).upper() != "YEAR":
            continue
        source_desc = r.get("source_desc")
        if source_desc and str(source_desc).upper() != "SURVEY":
            continue
        domain_desc = r.get("domain_desc")
        if domain_desc and str(domain_desc).upper() != "TOTAL":
            continue
        freq_desc = r.get("freq_desc")
        if freq_desc and str(freq_desc).upper() != "ANNUAL":
            continue

        raw_val = str(r.get("Value") if r.get("Value") is not None else "").replace(",", "").strip()
        try:
            val = float(raw_val)
        except (TypeError, ValueError):
            continue
        if not is_finite(val) or val <= 0:
            continue

        row_class = str(r["class_desc"]).upper() if r.get("class_desc") else expected_class
        if row_class == expected_class:
            result[year] = val
            exact_class_matched_year.add(year)
        elif year not in exact_class_matched_year and row_class == "ALL CLASSES":
            result[year] = val

    return result


def fetch_nass_state_yields(
    *,
    lat=None,
    lon=None,
    state_alpha=None,
    start_year=None,
    end_year=None,
    **kwargs,
) -> dict:
    """Fetch official USDA NASS annual state yields when in the US and API key is set."""
    if state_alpha is None and "stateAlpha" in kwargs:
        state_alpha = kwargs["stateAlpha"]
    if start_year is None:
        start_year = kwargs.get("startYear", CONFIG["sampling"]["startYear"])
    if end_year is None:
        end_year = kwargs.get("endYear", CONFIG["sampling"]["endYear"])

    resolved_state = (
        str(state_alpha).upper()
        if state_alpha is not None
        else infer_us_state_from_lat_lon(lat, lon)
    )
    if resolved_state is None:
        return {
            "available": False,
            "stateAlpha": None,
            "reason": (
                "Localisation hors États-Unis (ou État non spécifié) — "
                "USDA NASS couvre uniquement les États-Unis."
            ),
            "yieldsByCropYear": {},
        }

    if not SAFE_STATE_RE.fullmatch(resolved_state):
        raise ValueError(
            f"Code d'État NASS invalide (2 lettres majuscules attendues) : {state_alpha}"
        )

    api_key = CONFIG["credentials"].get("nassApiKey")
    if not api_key:
        return {
            "available": False,
            "stateAlpha": resolved_state,
            "reason": (
                "Variable USDA_NASS_API_KEY absente — écarts en % de vigueur satellite uniquement."
            ),
            "yieldsByCropYear": {},
        }

    s_year = int(float(start_year))
    e_year = int(float(end_year))
    cache_key = f"nass_{resolved_state}_{s_year}_{e_year}"
    cached = read_cache("nass-quickstats", cache_key)
    if cached:
        return {**cached, "fromCache": True}

    yields_by_crop_year = {}
    for crop_id in NASS_COMMODITY_MAP:
        params = build_nass_query_params(
            api_key=api_key,
            crop_id=crop_id,
            state_alpha=resolved_state,
            start_year=s_year,
            end_year=e_year,
        )
        url = f"{CONFIG['endpoints']['usdaNassQuickStats']}?{urlencode(params)}"
        response = http.fetch(url)
        if not response.ok:
            response.close()
            continue
        data = read_bounded_json(response)
        extracted = extract_annual_survey_yields((data or {}).get("data") or [], crop_id)
        yields_by_crop_year[crop_id] = {str(k): v for k, v in extracted.items()}

    return write_cache(
        "nass-quickstats",
        cache_key,
        {
            "available": True,
            "source": "USDA NASS QuickStats API (SURVEY / ANNUAL / YEAR)",
            "stateAlpha": resolved_state,
            "yieldsByCropYear": yields_by_crop_year,
        },
    )


def calibrate_pair_matrix_with_nass_yields(pair_matrix: dict, nass_yields: dict | None) -> dict:
    """Attach state-level conditional physical yield estimates to pair_matrix."""
    if (
        not isinstance(nass_yields, dict)
        or not nass_yields.get("available")
        or not nass_yields.get("stateAlpha")
        or not isinstance(pair_matrix, dict)
        or not isinstance(pair_matrix.get("pairs"), dict)
    ):
        return pair_matrix

    mean_yield_by_crop = {}
    for crop_id, year_map in (nass_yields.get("yieldsByCropYear") or {}).items():
        if not isinstance(year_map, dict):
            continue
        vals = list(year_map.values())
        if any(not is_finite(v) or v < 0 for v in vals):
            raise ValueError(
                f"Rendement NASS invalide pour {crop_id} : valeur finie non négative attendue."
            )
        if vals:
            mean_native = 0.0
            for value in vals:
                mean_native += value / len(vals)
            meta = NASS_COMMODITY_MAP.get(crop_id) or {}
            mean_tonnes_per_ha = mean_native * (meta.get("toTonnesPerHa") or 1.0)
            if not is_finite(mean_native) or not is_finite(mean_tonnes_per_ha):
                raise ValueError(f"Conversion NASS non finie pour {crop_id}.")
            mean_yield_by_crop[crop_id] = {
                "meanNative": js_round(mean_native, 2),
                "nativeUnit": meta.get("unit_desc") or "UNIT / ACRE",
                "meanTonnesPerHa": js_round(mean_tonnes_per_ha, 2),
            }

    for stat in pair_matrix["pairs"].values():
        ref = mean_yield_by_crop.get(stat.get("to"))
        if not ref:
            continue
        delta_factor = validate_physical_effect_pct(stat.get("meanEffectPct")) / 100.0
        expected_tonnes_per_ha = ref["meanTonnesPerHa"] * (1.0 + delta_factor)
        delta_native = ref["meanNative"] * delta_factor
        if not is_finite(expected_tonnes_per_ha) or not is_finite(delta_native):
            raise ValueError("Estimation NASS non finie.")
        stat["calibratedYield"] = {
            "nature": "conditional_yield_estimate",
            "empiricallyCalibrated": False,
            "assumption": "relative_vigor_anomaly_equals_relative_yield_anomaly",
            "relativeVigorToYieldSlope": 1,
            "stateAlpha": nass_yields["stateAlpha"],
            "calibrationMethod": "linear_proportional_to_state_mean",
            "baselineTonnesPerHa": ref["meanTonnesPerHa"],
            "deltaTonnesPerHa": js_round(ref["meanTonnesPerHa"] * delta_factor, 3),
            "expectedTonnesPerHa": js_round(expected_tonnes_per_ha, 2),
            "baselineNative": ref["meanNative"],
            "deltaNative": js_round(delta_native, 2),
            "nativeUnit": ref["nativeUnit"],
        }

    return pair_matrix

