"""Real NASA POWER daily history and optional recorded repository snapshots."""
from datetime import datetime
import json
import math
from pathlib import Path
from urllib.parse import urlencode

from field_shift.algorithm.yield_model.config import CONFIG, is_finite, js_round
from field_shift.algorithm.yield_model.sources import http
from field_shift.algorithm.yield_model.sources.cache import read_bounded_json, read_cache, region_cell_key, validate_historical_sampling_params, write_cache
from field_shift.algorithm.yield_model.sources.climate_validation import validate_climate_seasons


def classify_climate_regimes(summaries):
    if not summaries:
        return []
    rains = sorted(s["precipMm"] for s in summaries)
    temps = sorted(s["meanTempC"] for s in summaries)
    n = len(summaries)
    mean_rain, mean_temp = sum(rains) / n, sum(temps) / n
    std_rain = math.sqrt(sum((v - mean_rain) ** 2 for v in rains) / n) or 1
    std_temp = math.sqrt(sum((v - mean_temp) ** 2 for v in temps) / n) or 1
    return [{**s, "rainZScore": js_round((s["precipMm"] - mean_rain) / std_rain, 2),
             "tempZScore": js_round((s["meanTempC"] - mean_temp) / std_temp, 2),
             "regime": "sec" if s["precipMm"] <= rains[math.floor(n * .25)] else
                       "chaud" if s["meanTempC"] >= temps[math.floor(n * .75)] else "normal"}
            for s in summaries]


def summarize_growing_seasons(parameters_by_date):
    by_year = {}
    def valid(v):
        return is_finite(v) and v > -990
    for key, temp in parameters_by_date.get("T2M", {}).items():
        try:
            if len(key) != 8 or not key.isascii() or not key.isdigit():
                continue
            date = datetime.strptime(key, "%Y%m%d")
        except (ValueError, TypeError):
            continue
        if not 5 <= date.month <= 9:
            continue
        maximum, minimum, rain = (parameters_by_date.get(k, {}).get(key) for k in
                                  ("T2M_MAX", "T2M_MIN", "PRECTOTCORR"))
        if not all(valid(v) for v in (temp, maximum, minimum, rain)) or rain < 0 or maximum < minimum:
            continue
        row = by_year.setdefault(date.year, {"days": 0, "temp": 0, "gdd": 0, "heat": 0,
                                             "rain": 0, "dry": 0, "top": [], "root": []})
        row["days"] += 1
        row["temp"] += temp
        row["gdd"] += max(0, (maximum + minimum) / 2 - 10)
        row["heat"] += int(maximum >= 30)
        row["rain"] += rain
        row["dry"] += int(rain < 1)
        for parameter, target in (("GWETTOP", "top"), ("GWETROOT", "root")):
            value = parameters_by_date.get(parameter, {}).get(key)
            if valid(value) and 0 <= value <= 1:
                row[target].append(value)
    def soil_mean(values):
        return js_round(sum(values) / len(values), 3) if values else None
    summaries = [{"year": year, "meanTempC": js_round(a["temp"] / 153, 2),
                  "gddBase10": js_round(a["gdd"], 1), "heatStressDays": a["heat"],
                  "precipMm": js_round(a["rain"], 1), "dryDaysCount": a["dry"],
                  "soilMoistureTop": soil_mean(a["top"]), "soilMoistureRoot": soil_mean(a["root"]),
                  "coverage": {"requiredDays": 153, "completeDays": a["days"]}}
                 for year, a in sorted(by_year.items()) if a["days"] == 153]
    return classify_climate_regimes(summaries)


def load_local_nasa_power_snapshot(*, lat=None, lon=None, start_year=None, end_year=None):
    directory = Path(CONFIG["repoSnapshotsDir"])
    if not directory.exists():
        return None
    for file in sorted(directory.glob("*.json")):
        if file.name.endswith(".meta.json"):
            continue
        try:
            raw = json.loads(file.read_text(encoding="utf-8"))
            snap_lon, snap_lat = map(float, raw["geometry"]["coordinates"][:2])
            if not all(is_finite(v) for v in (snap_lon, snap_lat)):
                continue
            if lat is not None and lon is not None and (abs(snap_lat - float(lat)) > .25 or abs(snap_lon - float(lon)) > .25):
                continue
            seasons = summarize_growing_seasons(raw["properties"]["parameter"])
            if start_year is not None and end_year is not None:
                seasons = classify_climate_regimes([s for s in seasons if start_year <= s["year"] <= end_year])
            validate_climate_seasons(seasons, start_year=start_year, end_year=end_year)
            return {"source": f"Snapshot local NASA POWER ({file.name})",
                    "coordinates": {"lat": snap_lat, "lon": snap_lon}, "seasons": seasons}
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return None


def fetch_nasa_power_series(*, lat, lon, start_year=None, end_year=None):
    v = validate_historical_sampling_params(lat=lat, lon=lon, start_year=start_year, end_year=end_year)
    key = f"{region_cell_key(v['lat'], v['lon'], .5)}_{v['startYear']}_{v['endYear']}"
    def matches(data):
        validate_climate_seasons(data["seasons"], start_year=v["startYear"], end_year=v["endYear"])
        return True
    cached = read_cache("nasa-power", key, matches)
    if cached:
        return {**cached, "fromCache": True}
    snapshot = load_local_nasa_power_snapshot(lat=v["lat"], lon=v["lon"], start_year=v["startYear"], end_year=v["endYear"])
    period = {"startYear": v["startYear"], "endYear": v["endYear"]}
    if snapshot:
        return {**snapshot, "period": period, "fromCache": True}
    params = {"parameters": "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,GWETTOP,GWETROOT,ALLSKY_SFC_SW_DWN",
              "community": "AG", "longitude": v["lon"], "latitude": v["lat"],
              "start": f"{v['startYear']}0101", "end": f"{v['endYear']}1231", "format": "JSON"}
    url = CONFIG["endpoints"]["nasaPowerDaily"] + "?" + urlencode(params)
    response = http.fetch(url, headers={"Accept": "application/json"})
    if not response.ok:
        response.close()
        raise ValueError(f"NASA POWER API HTTP {response.status} sur {url}")
    raw = read_bounded_json(response)
    parameters = raw.get("properties", {}).get("parameter")
    if not parameters:
        raise ValueError("Réponse NASA POWER invalide : properties.parameter manquant.")
    seasons = summarize_growing_seasons(parameters)
    validate_climate_seasons(seasons, start_year=v["startYear"], end_year=v["endYear"])
    return write_cache("nasa-power", key, {"source": "NASA POWER Daily Agroclimatology API (MERRA-2 / GLDAS)",
                       "url": url, "coordinates": {"lat": v["lat"], "lon": v["lon"]},
                       "period": period, "seasons": seasons})
