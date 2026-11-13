"""Validation and normalisation of NASA POWER daily point responses.

* structure validated with Pydantic (fails loudly on any unexpected shape);
* the fill value announced in the header (-999 in practice) becomes ``None``;
* units are checked and converted to °C and mm/day; an unknown unit is an error, never a
  guess;
* every parameter must cover exactly the same dates.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, ConfigDict, ValidationError

from fieldshift.domain.climate.series import ClimateSeries, DailyRecord
from fieldshift.domain.provenance import ParameterInfo

DEFINITIONS = {
    "T2M": "The average air (dry bulb) temperature at 2 meters above the surface of the earth.",
    "T2M_MAX": (
        "The maximum hourly air (dry bulb) temperature at 2 meters above the surface of the "
        "earth in the period of interest."
    ),
    "T2M_MIN": (
        "The minimum hourly air (dry bulb) temperature at 2 meters above the surface of the "
        "earth in the period of interest."
    ),
    "PRECTOTCORR": "The average MERRA-2 bias corrected total precipitation at the surface of the earth.",
}
"""Official definitions, retrieved from the POWER system manager on 2026-11-10."""

_CELSIUS: Mapping[str, Callable[[float], float]] = {
    "C": lambda value: value,
    "K": lambda value: value - 273.15,
}
_MM_PER_DAY: Mapping[str, Callable[[float], float]] = {
    "mm/day": lambda value: value,
}
CONVERTERS: Mapping[str, Mapping[str, Callable[[float], float]]] = {
    "T2M": _CELSIUS,
    "T2M_MAX": _CELSIUS,
    "T2M_MIN": _CELSIUS,
    "PRECTOTCORR": _MM_PER_DAY,
}
NORMALISED_UNITS = {"T2M": "°C", "T2M_MAX": "°C", "T2M_MIN": "°C", "PRECTOTCORR": "mm/jour"}


class PowerResponseError(ValueError):
    """The response does not have the expected content."""


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class _Geometry(_Model):
    coordinates: list[float]


class _Properties(_Model):
    parameter: dict[str, dict[str, float | None]]


class _Api(_Model):
    version: str | None = None
    name: str | None = None


class _Header(_Model):
    api: _Api | None = None
    sources: list[str] = []
    fill_value: float = -999.0
    time_standard: str | None = None


class _ParameterMeta(_Model):
    units: str
    longname: str


class _DailyPointResponse(_Model):
    geometry: _Geometry
    properties: _Properties
    header: _Header
    parameters: dict[str, _ParameterMeta]
    messages: list[str] = []


@dataclass(frozen=True, slots=True)
class ParsedDailyResponse:
    series: ClimateSeries
    api_version: str | None
    upstream_sources: tuple[str, ...]
    parameters: tuple[ParameterInfo, ...]
    elevation_m: float | None
    time_standard: str | None
    messages: tuple[str, ...]


def _convert(parameter: str, unit: str, raw: float | None, fill_value: float) -> float | None:
    if raw is None or raw == fill_value or not math.isfinite(raw):
        return None
    return CONVERTERS[parameter][unit](raw)


def parse_daily_point(body: bytes) -> ParsedDailyResponse:
    try:
        payload = _DailyPointResponse.model_validate_json(body)
    except ValidationError as error:
        raise PowerResponseError(
            f"unexpected NASA POWER response structure ({error.error_count()} problem(s))"
        ) from error

    values = payload.properties.parameter
    for parameter, converters in CONVERTERS.items():
        if parameter not in values or parameter not in payload.parameters:
            raise PowerResponseError(f"parameter {parameter} missing from the response")
        unit = payload.parameters[parameter].units
        if unit not in converters:
            raise PowerResponseError(f"unexpected unit {unit!r} for {parameter}")

    dates = sorted(values["T2M"])
    for parameter in CONVERTERS:
        if sorted(values[parameter]) != dates:
            raise PowerResponseError(f"dates of {parameter} differ from those of T2M")

    fill = payload.header.fill_value
    units = {parameter: payload.parameters[parameter].units for parameter in CONVERTERS}
    try:
        records = [
            DailyRecord(
                day=datetime.strptime(key, "%Y%m%d").date(),  # noqa: DTZ007 - calendar date only
                t_mean_c=_convert("T2M", units["T2M"], values["T2M"][key], fill),
                t_max_c=_convert("T2M_MAX", units["T2M_MAX"], values["T2M_MAX"][key], fill),
                t_min_c=_convert("T2M_MIN", units["T2M_MIN"], values["T2M_MIN"][key], fill),
                precipitation_mm=_convert(
                    "PRECTOTCORR", units["PRECTOTCORR"], values["PRECTOTCORR"][key], fill
                ),
            )
            for key in dates
        ]
        series = ClimateSeries(records)
    except ValueError as error:
        raise PowerResponseError(f"invalid dates in NASA POWER response: {error}") from error

    coordinates = payload.geometry.coordinates
    return ParsedDailyResponse(
        series=series,
        api_version=payload.header.api.version if payload.header.api else None,
        upstream_sources=tuple(payload.header.sources),
        parameters=tuple(
            ParameterInfo(
                code=parameter,
                name=payload.parameters[parameter].longname,
                unit=NORMALISED_UNITS[parameter],
                definition=DEFINITIONS[parameter],
            )
            for parameter in CONVERTERS
        ),
        elevation_m=coordinates[2] if len(coordinates) >= 3 else None,
        time_standard=payload.header.time_standard,
        messages=tuple(payload.messages),
    )
