"""Shared configuration, crop mapping and rounding for the Python yield engine."""

from __future__ import annotations

import json
import math
import os
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from pathlib import Path

_DIRECTORY = Path(__file__).resolve().parent
REPO_ROOT = _DIRECTORY.parents[3]
_SETTINGS = json.loads((_DIRECTORY / "settings.json").read_text(encoding="utf-8"))


def is_finite(value: object) -> bool:
    """Unlike bool-as-int Python arithmetic, match Number.isFinite's numeric contract."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def is_integer(value: object) -> bool:
    return is_finite(value) and float(value).is_integer()


def js_round(value: float, digits: int = 0) -> float:
    """Match Number(value.toFixed(digits)), including binary ties, for JSON parity."""
    if not is_finite(value):
        return float(value)
    if abs(value) >= 1e21:
        return float(value)
    with localcontext() as context:
        context.prec = 400
        try:
            return float(Decimal.from_float(float(value)).quantize(
                Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP
            ))
        except InvalidOperation as error:
            raise ValueError("Arrondi numérique impossible.") from error


def parse_env_number(raw: object, fallback: float, *, minimum=-math.inf, maximum=math.inf):
    if raw is None or str(raw).strip() == "":
        return fallback
    try:
        value = float(raw)
    except (ValueError, TypeError):
        return fallback
    if not math.isfinite(value) or value < minimum or value > maximum:
        return fallback
    return int(value) if value.is_integer() else value


CONFIG = {
    "cacheDir": os.environ.get("ALGO_CACHE_DIR") or str(REPO_ROOT / "algo-rendement" / ".cache"),
    "httpTimeoutMs": parse_env_number(os.environ.get("ALGO_HTTP_TIMEOUT_MS"), 15000,
                                    minimum=1000, maximum=120000),
    "repoSnapshotsDir": str(REPO_ROOT / "data" / "snapshots" / "nasa-power"),
    "credentials": {"earthdataToken": os.environ.get("NASA_EARTHDATA_TOKEN", ""),
                    "nassApiKey": os.environ.get("USDA_NASS_API_KEY", "")},
    "endpoints": _SETTINGS["endpoints"],
    "sampling": _SETTINGS["sampling"],
    "hyperparameters": _SETTINGS["hyperparameters"],
}
for _key, _env in (("startYear", "ALGO_START_YEAR"), ("endYear", "ALGO_END_YEAR")):
    CONFIG["sampling"][_key] = parse_env_number(os.environ.get(_env), CONFIG["sampling"][_key],
                                               minimum=1981, maximum=2030)
CONFIG["sampling"]["halfWindowKm"] = parse_env_number(
    os.environ.get("ALGO_WINDOW_KM"), 8, minimum=1, maximum=25
)
CROPS = _SETTINGS["crops"]
CROP_IDS = list(CROPS)
CROP_TAXONOMY = _SETTINGS["cropTaxonomy"]
SATELLITE_CROP_CODES = _SETTINGS["satelliteCropCodes"]
SATELLITE_CROP_MAPPING_VERSION = _SETTINGS["satelliteCropMappingVersion"]
