"""One reader per data service: the HTTP request, and the values read from its answer.

    read_soil          SoilGrids 2.0 (ISRIC)         sand, clay, organic matter (0–15 cm)
    read_elevations    Copernicus DEM (Open-Meteo)   elevations of a list of points
    read_climatology   NASA POWER climatology        annual rain, soil moisture of the season
    read_storm         NASA POWER hourly             intensity of the reference storm
    read_season_ndvi   MODIS MOD13Q1 / MYD13Q1       NDVI of the growing season (Planetary
                       (Planetary Computer)          Computer: the whole year in one request)
    read_et_ratio      MODIS MOD16A2 (ORNL DAAC)     ET / PET of the growing season

A reader never guesses: an error, an unexpected answer or a missing value raises `SourceError`,
with the name of the dataset and the reason in French.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Any, Final

import httpx

from field_shift.algorithm.config.soil_protection import (
    ORGANIC_MATTER_PER_CARBON,
    STORM_YEARS,
    TOPSOIL_DEPTH_CM,
)
from field_shift.algorithm.soil_protection.forcing import (
    MONTH_NAMES,
    SeriesError,
    YearMonth,
    evapotranspiration_ratio,
    growing_season_months,
    mean_over_months,
    season_label,
    storm_intensity,
    two_month_windows,
)
from field_shift.algorithm.soil_protection.site_conditions import SiteReading
from field_shift.data_access.data_source_config import DataEndpoint
from field_shift.data_access.modis_ndvi import ModisNdviClient, NdviUnavailableError
from field_shift.data_access.soilgrids import NoSoilError, SoilGridsClient, SoilGridsError

#: 6 decimals: 0.1 m, finer than any elevation model.
COORDINATE_DECIMALS: Final = 6
#: The hourly series of ten years is a large answer (about 90 000 values).
SLOW_TIMEOUT_S: Final = 120.0
#: The ORNL DAAC subset service takes 40 to 60 s a request (2026-11-15).
ANNUAL_ET_DATASET: Final = "MODIS MOD16A3GF (NASA, Planetary Computer)"
MODIS_TIMEOUT_S: Final = 180.0
POWER_FILL_VALUE: Final = -999.0
DAYS_PER_YEAR: Final = 365.25
MONTH_KEYS: Final = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV",
                     "DEC")  # fmt: skip

#: SoilGrids layers averaged over the top 15 cm, with their thickness (cm).
SOILGRIDS_DEPTHS: Final = (("0-5cm", 5.0), ("5-15cm", 10.0))
if sum(thickness for _, thickness in SOILGRIDS_DEPTHS) != TOPSOIL_DEPTH_CM:
    raise RuntimeError("SOILGRIDS_DEPTHS must cover TOPSOIL_DEPTH_CM")
#: Unit each SoilGrids property is converted to (value / d_factor).
SOILGRIDS_UNITS: Final = {"sand": "%", "clay": "%", "soc": "g/kg"}

#: MODIS products and bands on the ORNL DAAC subset service, with their scale and valid range.
NDVI_PRODUCT: Final = ("MOD13Q1", "250m_16_days_NDVI", 0.0001, range(-2000, 10001))
ET_PRODUCT: Final = ("MOD16A2", "ET_500m", 0.1, range(0, 32701))
PET_PRODUCT: Final = ("MOD16A2", "PET_500m", 0.1, range(0, 32701))


class SourceError(RuntimeError):
    """A data service could not give its values."""

    def __init__(self, dataset: str, reason: str) -> None:
        super().__init__(f"{dataset} : {reason}")
        self.dataset = dataset
        self.reason = reason


def _number(value: float) -> str:
    return f"{value:.4g}".replace(".", ",")


def _coordinate(value: float) -> str:
    return f"{value:.{COORDINATE_DECIMALS}f}"


def get_json(
    http: httpx.Client,
    endpoint: DataEndpoint,
    params: Any,
    url: str | None = None,
    timeout: float | None = None,
) -> Any:
    """The JSON answer of a GET to the service; SourceError for any failure."""
    headers = {"Accept": "application/json", **endpoint.headers}
    try:
        extra = {} if timeout is None else {"timeout": timeout}
        response = http.get(url or endpoint.url, params=params, headers=headers, **extra)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as error:
        raise SourceError(
            endpoint.dataset, f"le service a répondu {error.response.status_code}"
        ) from error
    except httpx.HTTPError as error:
        raise SourceError(endpoint.dataset, f"le service n’a pas répondu ({error})") from error
    except ValueError as error:
        raise SourceError(endpoint.dataset, "réponse illisible (pas du JSON)") from error


def _at(document: Any, endpoint: DataEndpoint, *path: str | int) -> Any:
    """The value at a path of a JSON document; SourceError when the answer has another shape."""
    current = document
    for key in path:
        try:
            current = current[key]
        except (KeyError, IndexError, TypeError):
            where = ".".join(str(k) for k in path)
            raise SourceError(endpoint.dataset, f"réponse inattendue ({where} absent)") from None
    return current


def _real(value: Any, endpoint: DataEndpoint, what: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise SourceError(endpoint.dataset, f"{what} : valeur absente") from None
    if math.isnan(number) or number == POWER_FILL_VALUE:
        raise SourceError(endpoint.dataset, f"{what} : valeur absente")
    return number


# --- SoilGrids ------------------------------------------------------------------------------------


def read_soil(soilgrids: SoilGridsClient, lat: float, lon: float) -> list[SiteReading]:
    """Sand and clay (%), and the organic matter (%) = organic carbon × 1.724, averaged over the
    top 15 cm (weighted by the thickness of the layers). SoilGrids is read on its WCS (shared
    with the plan: the same point is never read twice)."""
    try:
        means = soilgrids.mean_over(lat, lon, SOILGRIDS_DEPTHS, tuple(SOILGRIDS_UNITS))
    except NoSoilError as error:
        raise SourceError(
            soilgrids.dataset,
            "pas de donnée de sol au centre de la section : eau, zone urbaine ou hors de la carte",
        ) from error
    except SoilGridsError as error:
        raise SourceError(soilgrids.dataset, str(error)) from error
    sand, clay, carbon_g_kg = means["sand"], means["clay"], means["soc"]
    depth = "moyenne pondérée des couches 0–5 et 5–15 cm"
    organic_matter = carbon_g_kg / 10 * ORGANIC_MATTER_PER_CARBON
    return [
        SiteReading("sand_pct", sand, soilgrids.dataset, depth),
        SiteReading("clay_pct", clay, soilgrids.dataset, depth),
        SiteReading(
            "organic_matter_pct",
            organic_matter,
            soilgrids.dataset,
            f"carbone organique du sol ({_number(carbon_g_kg)} g/kg, {depth}) × "
            f"{_number(ORGANIC_MATTER_PER_CARBON)} (facteur de Van Bemmelen)",
        ),
    ]


# --- Elevations -----------------------------------------------------------------------------------


def read_elevations(
    http: httpx.Client, endpoint: DataEndpoint, points: Sequence[tuple[float, float]]
) -> list[float]:
    """The elevation (m) of each (lon, lat) point, in the same order."""
    params = {
        "latitude": ",".join(_coordinate(lat) for _, lat in points),
        "longitude": ",".join(_coordinate(lon) for lon, _ in points),
    }
    elevations = _at(get_json(http, endpoint, params), endpoint, "elevation")
    if not isinstance(elevations, list) or len(elevations) != len(points):
        raise SourceError(
            endpoint.dataset, f"{len(points)} altitudes demandées, réponse différente"
        )
    return [_real(value, endpoint, "altitude") for value in elevations]


# --- NASA POWER -----------------------------------------------------------------------------------


def read_climatology(
    http: httpx.Client, endpoint: DataEndpoint, lat: float, lon: float
) -> list[SiteReading]:
    """Annual rain (mm) and relative saturation of the surface soil over the growing season."""
    params = {
        "parameters": "PRECTOTCORR,GWETTOP",
        "community": "AG",
        "latitude": _coordinate(lat),
        "longitude": _coordinate(lon),
        "format": "JSON",
    }
    parameters = _at(get_json(http, endpoint, params), endpoint, "properties", "parameter")
    daily_rain = _real(_at(parameters, endpoint, "PRECTOTCORR", "ANN"), endpoint, "pluie")
    wetness = {
        month: _real(_at(parameters, endpoint, "GWETTOP", key), endpoint, "GWETTOP")
        for month, key in enumerate(MONTH_KEYS, start=1)
    }
    months = growing_season_months(lat)
    names = (MONTH_NAMES[months[0] - 1], MONTH_NAMES[months[-1] - 1])
    return [
        SiteReading(
            "annual_rain_mm",
            daily_rain * DAYS_PER_YEAR,
            endpoint.dataset,
            f"climatologie de la pluie corrigée (PRECTOTCORR, {_number(daily_rain)} mm/jour) "
            f"× {DAYS_PER_YEAR} jours".replace(".", ","),
        ),
        SiteReading(
            "soil_saturation",
            mean_over_months(wetness, months),
            endpoint.dataset,
            f"humidité relative du sol de surface (GWETTOP), moyenne climatologique de "
            f"{names[0]} à {names[1]}, à la place de SMAP",
        ),
    ]


def read_storm(
    http: httpx.Client, endpoint: DataEndpoint, lat: float, lon: float, today: date
) -> SiteReading:
    """Intensity of the reference storm: mean of the annual maxima of the hourly rain over the
    last complete years."""
    last = today.year - 1
    first = last - STORM_YEARS + 1
    params = {
        "parameters": "PRECTOTCORR",
        "community": "AG",
        "latitude": _coordinate(lat),
        "longitude": _coordinate(lon),
        "start": f"{first}0101",
        "end": f"{last}1231",
        "format": "JSON",
    }
    document = get_json(http, endpoint, params, timeout=SLOW_TIMEOUT_S)
    series = _at(document, endpoint, "properties", "parameter", "PRECTOTCORR")
    if not isinstance(series, Mapping):
        raise SourceError(endpoint.dataset, "réponse inattendue (série horaire)")
    try:
        storm = storm_intensity({str(k): float(v) for k, v in series.items()})
    except (SeriesError, TypeError, ValueError) as error:
        raise SourceError(endpoint.dataset, str(error)) from error
    return SiteReading(
        "storm_intensity_mm_h",
        storm.intensity_mm_h,
        endpoint.dataset,
        f"moyenne des maxima annuels de la pluie horaire (PRECTOTCORR) de {storm.years[0]} à "
        f"{storm.years[-1]} ; maille d’environ 50 km : sous-estime les averses locales",
    )


# --- MODIS (ORNL DAAC subset service) -------------------------------------------------------------


def _modis_date(day: date) -> str:
    return f"A{day.year}{day.timetuple().tm_yday:03d}"


def _modis_window(
    http: httpx.Client,
    endpoint: DataEndpoint,
    product: tuple[str, str, float, range],
    lat: float,
    lon: float,
    window: tuple[date, date],
) -> dict[str, float]:
    """The valid values of one band over one window (calendar date → scaled value)."""
    name, band, scale, valid = product
    start, end = window
    params = {
        "latitude": _coordinate(lat),
        "longitude": _coordinate(lon),
        "band": band,
        "startDate": _modis_date(start),
        "endDate": _modis_date(end),
        "kmAboveBelow": 0,
        "kmLeftRight": 0,
    }
    document = get_json(
        http, endpoint, params, url=f"{endpoint.url}/{name}/subset", timeout=MODIS_TIMEOUT_S
    )
    values: dict[str, float] = {}
    for composite in _at(document, endpoint, "subset"):
        raw = _at(composite, endpoint, "data", 0)
        if isinstance(raw, int | float) and int(raw) in valid:
            values[str(_at(composite, endpoint, "calendar_date"))] = raw * scale
    return values


def _modis_bands(
    http: httpx.Client,
    endpoint: DataEndpoint,
    products: Sequence[tuple[str, str, float, range]],
    lat: float,
    lon: float,
    season: Sequence[YearMonth],
) -> list[dict[str, float]]:
    """The values of several bands over the season. The service gives one band and two months
    per request, 40 to 60 s each (2026-11-15): every (band, window) is asked at the same time."""
    windows = two_month_windows(season)
    jobs = [(product, window) for product in products for window in windows]
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        parts = list(
            pool.map(lambda job: _modis_window(http, endpoint, job[0], lat, lon, job[1]), jobs)
        )
    bands: list[dict[str, float]] = [{} for _ in products]
    for (product, _), values in zip(jobs, parts, strict=True):
        bands[list(products).index(product)].update(values)
    return bands


def read_season_ndvi(
    client: ModisNdviClient, lat: float, lon: float, season: Sequence[YearMonth]
) -> SiteReading:
    """Mean NDVI of the growing season at the centre of the section (250 m pixel): the MODIS
    composites of Terra and Aqua whose first day is in the season."""
    months = set(season)
    values: list[float] = []
    try:
        for year in sorted({year for year, _ in season}):
            for day, ndvi in client.year_series(lat, lon, year):
                if (int(day[:4]), int(day[5:7])) in months:
                    values.append(ndvi)
    except NdviUnavailableError as error:
        raise SourceError(client.dataset, str(error)) from error
    if not values:
        raise SourceError(client.dataset, f"aucun NDVI valide ({season_label(season)})")
    return SiteReading(
        "ndvi",
        sum(values) / len(values),
        "MODIS MOD13Q1 / MYD13Q1 (NASA, Planetary Computer)",
        f"moyenne des {len(values)} composites de 16 jours (Terra et Aqua) de "
        f"{season_label(season)}, pixel de 250 m au centre de la section",
    )


def read_et_ratio(
    http: httpx.Client, endpoint: DataEndpoint, lat: float, lon: float, season: Sequence[YearMonth]
) -> SiteReading:
    """ΣET / ΣPET of the growing season at the centre of the section (500 m pixel)."""
    actual, potential = _modis_bands(http, endpoint, (ET_PRODUCT, PET_PRODUCT), lat, lon, season)
    try:
        ratio = evapotranspiration_ratio(actual, potential)
    except SeriesError as error:
        raise SourceError(endpoint.dataset, f"{error} ({season_label(season)})") from error
    return SiteReading(
        "root_activity",
        ratio,
        "MODIS MOD16A2 (NASA, ORNL DAAC)",
        f"ET réelle / ET potentielle sur {len(set(actual) & set(potential))} composites de "
        f"8 jours de {season_label(season)}, pixel de 500 m, à la place d’ECOSTRESS",
    )


def read_annual_et_ratio(
    client: ModisNdviClient, lat: float, lon: float, season: Sequence[YearMonth], why: str
) -> SiteReading:
    """ΣET / ΣPET of the year of the season, MODIS MOD16A3GF (Planetary Computer): when the
    ORNL DAAC, which serves the 8-day composites of the season, does not answer (`why`)."""
    try:
        ratio, year = client.annual_et_ratio(lat, lon, season[-1][0])
    except NdviUnavailableError as error:
        raise SourceError(
            ANNUAL_ET_DATASET, f"{error} (après l’échec de l’ORNL DAAC : {why})"
        ) from error
    return SiteReading(
        "root_activity",
        ratio,
        ANNUAL_ET_DATASET,
        f"ET réelle / ET potentielle de l’année {year} (et non de la saison : le service ORNL "
        f"DAAC de MOD16A2 n’a pas répondu, {why}), pixel de 500 m, à la place d’ECOSTRESS",
    )
