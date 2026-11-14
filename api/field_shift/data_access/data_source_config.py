"""THE place where the addresses of the NASA and partner data sources are configured.

Every value the server reads from the outside has one entry in `DATA_SOURCES` below: the dataset
it comes from, its default address (None while the team has not chosen a service) and how to read
the value in the answer. An address can be set or replaced WITHOUT TOUCHING THE CODE, in two ways:

1. A JSON file (easiest: copy `data_sources.example.json` to `data_sources.json` in
   `backend/server` and paste the addresses):

       {
         "slope_pct": {
           "url": "https://example.org/srtm/slope?lat={lat}&lon={lon}",
           "jsonPath": "data.slope_percent"
         },
         "soil_saturation": {
           "url": "https://example.org/smap?latitude={lat}&longitude={lon}",
           "jsonPath": "results.0.sm_surface_wetness",
           "scale": 0.01,
           "headers": {"Authorization": "Bearer <jeton Earthdata>"}
         }
       }

   The file read is `data_sources.json` in the folder the server is started from, or the one
   named by the environment variable `FIELD_SHIFT_DATA_SOURCES`.

2. Environment variables, which win over the file (KEY is the key of the source in capitals):

       FIELD_SHIFT_URL_<KEY>         the address          FIELD_SHIFT_URL_SLOPE_PCT=https://…
       FIELD_SHIFT_JSON_PATH_<KEY>   where the value is   FIELD_SHIFT_JSON_PATH_SLOPE_PCT=data.slope
       FIELD_SHIFT_SCALE_<KEY>       unit conversion      FIELD_SHIFT_SCALE_SOIL_SATURATION=0.01

   An empty address (`FIELD_SHIFT_URL_<KEY>=`) switches a source off.

What an address must be, for the sources read "at a point" (all but `power_daily`):
  - an HTTP GET address where `{lat}` and `{lon}` are replaced by the coordinates of the section
    (decimal degrees, WGS84);
  - that answers JSON; `jsonPath` is the path to the number in it, with dots between the keys and
    list positions ("properties.parameter.PRECTOTCORR.ANN", "results.0.value");
  - the number, multiplied by `scale`, must be in the unit of the variable (see
    `SITE_VARIABLES`); a value outside the valid range of the variable is ignored.

A source that is not configured, does not answer or gives a wrong value never fails a request:
the model uses its default value and the answer says so (`origin` of each site value).
`GET /data-sources` shows the configuration the server is running with.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Final

from field_shift.algorithm.soil_protection.site_conditions import SITE_VARIABLES

#: Environment variable naming the JSON file of the data sources.
CONFIG_FILE_ENV: Final = "FIELD_SHIFT_DATA_SOURCES"
#: File read when the variable is not set, if it exists in the working directory.
DEFAULT_CONFIG_FILE: Final = "data_sources.json"
URL_ENV_PREFIX: Final = "FIELD_SHIFT_URL_"
JSON_PATH_ENV_PREFIX: Final = "FIELD_SHIFT_JSON_PATH_"
SCALE_ENV_PREFIX: Final = "FIELD_SHIFT_SCALE_"

#: Key of the daily weather of the farm (NASA POWER), read by the plan with its own parser.
POWER_DAILY: Final = "power_daily"
#: Mean days in a year: NASA POWER gives the climatology of the rain in mm/day.
DAYS_PER_YEAR: Final = 365.25


@dataclass(frozen=True)
class DataEndpoint:
    """One value read from the outside and where to read it.

    key        name of the source in the configuration; for the point sources, the name of the
               site variable it fills (a field of `SiteConditions`)
    dataset    the NASA or partner dataset the value comes from (shown as its origin)
    provides   what the value is, in a few words
    url        address of the service; None: the source is not configured
    json_path  path to the number in the JSON answer (point sources)
    scale      the number read × scale = the value in the unit of the variable
    headers    HTTP headers sent with the request (an Earthdata token, an API key)
    """

    key: str
    dataset: str
    provides: str
    url: str | None = None
    json_path: str = "value"
    scale: float = 1.0
    headers: Mapping[str, str] = field(default_factory=dict)

    @property
    def is_configured(self) -> bool:
        return bool(self.url)


#: Every data source of the server with its default configuration. The team fills the addresses
#: in `data_sources.json` or in the environment (see the module documentation).
DATA_SOURCES: Final[tuple[DataEndpoint, ...]] = (
    DataEndpoint(
        POWER_DAILY,
        dataset="NASA POWER",
        provides="Météo quotidienne de la ferme (plan des rotations, POST /plan)",
        url="https://power.larc.nasa.gov/api/temporal/daily/point",
    ),
    # Step 1 — static properties of the soil and of the relief
    DataEndpoint("slope_pct", "SRTM (NASA Earthdata)", "Pente du terrain, en %"),
    DataEndpoint("slope_length_m", "SRTM (NASA Earthdata)", "Longueur de pente, en m"),
    DataEndpoint("sand_pct", "USDA SSURGO", "Teneur en sable, en %"),
    DataEndpoint("clay_pct", "USDA SSURGO", "Teneur en argile, en %"),
    DataEndpoint("organic_matter_pct", "USDA SSURGO", "Matière organique, en %"),
    DataEndpoint("ksat_mm_h", "USDA SSURGO", "Conductivité hydraulique à saturation, en mm/h"),
    DataEndpoint("k_factor", "USDA SSURGO", "Érodibilité K de RUSLE, en unités SI"),
    # Step 3 — vigour of the vegetation
    DataEndpoint("ndvi", "Landsat 8/9, MODIS / VIIRS", "NDVI moyen de la saison de croissance"),
    DataEndpoint("root_activity", "ECOSTRESS", "Évapotranspiration réelle / potentielle, 0 à 1"),
    # Step 4 — rain and soil moisture
    DataEndpoint(
        "annual_rain_mm",
        dataset="NASA POWER",
        provides="Pluie annuelle moyenne, en mm",
        url=(
            "https://power.larc.nasa.gov/api/temporal/climatology/point"
            "?parameters=PRECTOTCORR&community=AG&latitude={lat}&longitude={lon}&format=JSON"
        ),
        json_path="properties.parameter.PRECTOTCORR.ANN",
        scale=DAYS_PER_YEAR,
    ),
    DataEndpoint("r_factor", "GPM IMERG", "Érosivité R de RUSLE, en MJ·mm/(ha·h·an)"),
    DataEndpoint("storm_intensity_mm_h", "GPM IMERG", "Intensité d’une forte averse, en mm/h"),
    DataEndpoint("soil_saturation", "SMAP", "Saturation du sol en surface, 0 (sec) à 1 (saturé)"),
)

_point_keys = {source.key for source in DATA_SOURCES} - {POWER_DAILY}
if not _point_keys <= set(SITE_VARIABLES):  # a point source must fill a known site variable
    raise RuntimeError(f"Unknown site variables: {sorted(_point_keys - set(SITE_VARIABLES))}")


class DataSourceConfigError(ValueError):
    """The configuration of the data sources cannot be read (the message says what is wrong)."""


@dataclass(frozen=True)
class DataSourceConfig:
    """The data sources as configured for this run of the server."""

    sources: Mapping[str, DataEndpoint] = field(
        default_factory=lambda: {source.key: source for source in DATA_SOURCES}
    )

    @classmethod
    def load(cls, environment: Mapping[str, str] | None = None) -> DataSourceConfig:
        """The defaults, then the JSON file, then the environment variables.

        Raises DataSourceConfigError when the file named by FIELD_SHIFT_DATA_SOURCES is missing,
        is not valid JSON, names an unknown source, or when a scale is not a number.
        """
        env = os.environ if environment is None else environment
        sources = {source.key: source for source in DATA_SOURCES}
        for key, entry in _read_file(env).items():
            if key not in sources:
                raise DataSourceConfigError(
                    f"Source de données inconnue : {key!r}. Sources possibles : "
                    f"{', '.join(sources)}"
                )
            sources[key] = _with_file_entry(sources[key], entry)
        for key, source in sources.items():
            sources[key] = _with_environment(source, env)
        return cls(sources)

    @property
    def power_daily_url(self) -> str:
        """Address of the NASA POWER daily point service (the weather of the farm)."""
        configured = self.sources[POWER_DAILY].url
        default = next(source.url for source in DATA_SOURCES if source.key == POWER_DAILY)
        return configured or default

    @property
    def point_sources(self) -> tuple[DataEndpoint, ...]:
        """The configured sources that fill a site variable at a point."""
        return tuple(
            source
            for key, source in self.sources.items()
            if key != POWER_DAILY and source.is_configured
        )

    def without_network(self) -> DataSourceConfig:
        """The same configuration with every address removed (demo mode: nothing is fetched)."""
        return DataSourceConfig({key: replace(s, url=None) for key, s in self.sources.items()})


def _read_file(env: Mapping[str, str]) -> dict[str, Any]:
    """The content of the JSON configuration file ({} when there is none)."""
    named = env.get(CONFIG_FILE_ENV, "").strip()
    path = Path(named or DEFAULT_CONFIG_FILE)
    if not path.is_file():
        if named:
            raise DataSourceConfigError(f"{CONFIG_FILE_ENV} : fichier introuvable : {path}")
        return {}
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise DataSourceConfigError(f"{path} n’a pas pu être lu : {error}") from error
    if not isinstance(content, dict):
        raise DataSourceConfigError(f"{path} doit contenir un objet JSON {{clé: source}}")
    return content


def _scale(value: Any, where: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise DataSourceConfigError(f"{where} : scale doit être un nombre, pas {value!r}") from None


def _with_file_entry(source: DataEndpoint, entry: Any) -> DataEndpoint:
    """A source with the fields of its entry in the file: an address alone ("key": "https://…")
    or an object {url, jsonPath, scale, headers}."""
    if entry is None or isinstance(entry, str):
        return replace(source, url=entry or None)
    if not isinstance(entry, dict):
        raise DataSourceConfigError(f"{source.key} : une adresse ou un objet {{url, jsonPath…}}")
    changes: dict[str, Any] = {}
    if "url" in entry:
        changes["url"] = entry["url"] or None
    if "jsonPath" in entry:
        changes["json_path"] = str(entry["jsonPath"])
    if "scale" in entry:
        changes["scale"] = _scale(entry["scale"], source.key)
    if "headers" in entry:
        changes["headers"] = {str(k): str(v) for k, v in dict(entry["headers"]).items()}
    return replace(source, **changes)


def _with_environment(source: DataEndpoint, env: Mapping[str, str]) -> DataEndpoint:
    """A source with the fields its environment variables give."""
    suffix = source.key.upper()
    changes: dict[str, Any] = {}
    if URL_ENV_PREFIX + suffix in env:
        changes["url"] = env[URL_ENV_PREFIX + suffix].strip() or None
    if JSON_PATH_ENV_PREFIX + suffix in env:
        changes["json_path"] = env[JSON_PATH_ENV_PREFIX + suffix].strip()
    if SCALE_ENV_PREFIX + suffix in env:
        changes["scale"] = _scale(env[SCALE_ENV_PREFIX + suffix], SCALE_ENV_PREFIX + suffix)
    return replace(source, **changes) if changes else source
