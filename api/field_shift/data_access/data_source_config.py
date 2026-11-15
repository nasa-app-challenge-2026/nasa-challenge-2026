"""THE place where the addresses of the data services are configured.

Every service the server reads from has one entry in `DATA_SOURCES` below, with its default
address. All of them are public and need no key; an address (a mirror, a proxy) or HTTP headers (a
token) can be set WITHOUT TOUCHING THE CODE, in two ways:

1. A JSON file (copy `data_sources.example.json` to `data_sources.json` in `api/`):

       {
         "soilgrids": "https://maps.isric.org/mapserv",
         "modis": {"url": "https://modis.ornl.gov/rst/api/v1", "headers": {"Authorization": "…"}}
       }

   The file read is `data_sources.json` in the folder the server is started from, or the one
   named by the environment variable `FIELD_SHIFT_DATA_SOURCES`.

2. Environment variables, which win over the file: `FIELD_SHIFT_URL_<KEY>` (KEY is the key of
   the service in capitals), e.g. `FIELD_SHIFT_URL_SOILGRIDS=https://…`.

A service cannot be switched off: the model has no default value, every variable it needs comes
from the request or from these services. A service that fails makes the request fail (502), with
the name of the service.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Final

#: Environment variable naming the JSON file of the data sources.
CONFIG_FILE_ENV: Final = "FIELD_SHIFT_DATA_SOURCES"
#: File read when the variable is not set, if it exists in the working directory.
DEFAULT_CONFIG_FILE: Final = "data_sources.json"
URL_ENV_PREFIX: Final = "FIELD_SHIFT_URL_"

POWER_DAILY: Final = "power_daily"
POWER_CLIMATOLOGY: Final = "power_climatology"
POWER_HOURLY: Final = "power_hourly"
POWER_REGIONAL: Final = "power_regional"
POWER_PROJECTION: Final = "power_projection"
SOILGRIDS: Final = "soilgrids"
ELEVATION: Final = "elevation"
MODIS: Final = "modis"
MODIS_NDVI: Final = "modis_ndvi"
USDA_CDL: Final = "usda_cdl"
AAFC_CROPS: Final = "aafc_crops"


@dataclass(frozen=True)
class DataEndpoint:
    """One data service and where to reach it.

    key        name of the service in the configuration
    dataset    the dataset it serves (shown as the origin of the values)
    provides   what the server reads from it, in a few words
    reference  the publication that describes the dataset
    url        address of the service
    headers    HTTP headers sent with every request (a token, an API key)
    """

    key: str
    dataset: str
    provides: str
    reference: str
    url: str
    headers: Mapping[str, str] = field(default_factory=dict)


#: Every data service of the server with its default address.
DATA_SOURCES: Final[tuple[DataEndpoint, ...]] = (
    DataEndpoint(
        POWER_DAILY,
        dataset="NASA POWER (MERRA-2)",
        provides="Météo quotidienne de la ferme (plan des rotations, POST /plan)",
        reference="Stackhouse et al., NASA POWER, https://power.larc.nasa.gov/docs/",
        url="https://power.larc.nasa.gov/api/temporal/daily/point",
    ),
    DataEndpoint(
        POWER_CLIMATOLOGY,
        dataset="NASA POWER (MERRA-2)",
        provides="Pluie annuelle moyenne (PRECTOTCORR) et humidité du sol de surface (GWETTOP)",
        reference="Gelaro et al., J. Climate 30(14), 2017 (MERRA-2)",
        url="https://power.larc.nasa.gov/api/temporal/climatology/point",
    ),
    DataEndpoint(
        POWER_HOURLY,
        dataset="NASA POWER (MERRA-2)",
        provides="Pluie horaire (PRECTOTCORR) : intensité de l’averse de référence",
        reference="Gelaro et al., J. Climate 30(14), 2017 (MERRA-2)",
        url="https://power.larc.nasa.gov/api/temporal/hourly/point",
    ),
    DataEndpoint(
        POWER_REGIONAL,
        dataset="NASA POWER (MERRA-2)",
        provides=(
            "Climat observé 2011–2024 de chaque case de 0,5° autour de la ferme : recherche des "
            "jumeaux climatiques (POST /plan)"
        ),
        reference="Stackhouse et al., NASA POWER, https://power.larc.nasa.gov/docs/",
        url="https://power.larc.nasa.gov/api/temporal/daily/regional",
    ),
    DataEndpoint(
        POWER_PROJECTION,
        dataset="NASA NEX-GDDP-CMIP6 (ensemble des modèles, via NASA POWER)",
        provides=(
            "Climat projeté jour par jour (SSP1-2.6, SSP2-4.5, SSP3-7.0) : cycles à plus de "
            "10 ans (POST /plan)"
        ),
        reference="Thrasher et al., Scientific Data 9, 262, 2022 (NEX-GDDP-CMIP6)",
        url="https://power.larc.nasa.gov/api/projection/daily/point",
    ),
    DataEndpoint(
        SOILGRIDS,
        dataset="SoilGrids 2.0 (ISRIC)",
        provides=(
            "Sable, argile, carbone organique et pH du sol, couche par couche (service WCS) : "
            "sol des sections, des jumeaux, de la protection du sol et du bilan d’eau"
        ),
        reference="Poggio et al., SOIL 7, 217–240, 2021",
        url="https://maps.isric.org/mapserv",
    ),
    DataEndpoint(
        ELEVATION,
        dataset="Copernicus DEM GLO-90 (Open-Meteo)",
        provides="Altitudes sur la section : pente et longueur de pente",
        reference="ESA, Copernicus DEM, https://doi.org/10.5270/ESA-c5d3d65",
        url="https://api.open-meteo.com/v1/elevation",
    ),
    DataEndpoint(
        MODIS,
        dataset="MODIS (NASA, ORNL DAAC)",
        provides="NDVI (MOD13Q1) et ET / ET potentielle (MOD16A2) de la saison de croissance",
        reference=(
            "Didan, MOD13Q1 v061, 2021, doi:10.5067/MODIS/MOD13Q1.061 ; Running et al., "
            "MOD16A2 v061, 2021, doi:10.5067/MODIS/MOD16A2.061 ; Mu et al., RSE 115, 2011"
        ),
        url="https://modis.ornl.gov/rst/api/v1",
    ),
    DataEndpoint(
        MODIS_NDVI,
        dataset="MODIS MOD13Q1 / MYD13Q1 (NASA, Microsoft Planetary Computer)",
        provides=(
            "NDVI de tous les composites d’une année en un point : NDVI de la saison (POST "
            "/rotations/rank) et jours de sol nu de chaque section (POST /plan)"
        ),
        reference="Didan, MOD13Q1 v061, 2021, doi:10.5067/MODIS/MOD13Q1.061",
        url="https://planetarycomputer.microsoft.com/api/data/v1",
    ),
    DataEndpoint(
        USDA_CDL,
        dataset="USDA NASS Cropland Data Layer (Microsoft Planetary Computer)",
        provides="Culture de chaque pixel de 30 m, année par année : champs jumeaux aux États-Unis",
        reference="USDA NASS, Cropland Data Layer, https://www.nass.usda.gov/Research_and_Science/Cropland/",
        url="https://planetarycomputer.microsoft.com/api",
    ),
    DataEndpoint(
        AAFC_CROPS,
        dataset="Inventaire annuel des cultures (Agriculture et Agroalimentaire Canada)",
        provides="Culture de chaque pixel de 30 m, année par année : champs jumeaux au Canada",
        reference=(
            "AAC, Inventaire annuel des cultures, "
            "https://open.canada.ca/data/fr/dataset/ba2645d5-4458-414d-b196-6303ac06c1c9"
        ),
        url="https://agriculture.canada.ca/imagery-images/rest/services/annual_crop_inventory",
    ),
)

_DEFAULTS: Final = {source.key: source for source in DATA_SOURCES}


class DataSourceConfigError(ValueError):
    """The configuration of the data sources cannot be read (the message says what is wrong)."""


@dataclass(frozen=True)
class DataSourceConfig:
    """The data services as configured for this run of the server."""

    sources: Mapping[str, DataEndpoint] = field(default_factory=lambda: dict(_DEFAULTS))

    def __getitem__(self, key: str) -> DataEndpoint:
        return self.sources[key]

    @classmethod
    def load(cls, environment: Mapping[str, str] | None = None) -> DataSourceConfig:
        """The defaults, then the JSON file, then the environment variables.

        Raises DataSourceConfigError when the file named by FIELD_SHIFT_DATA_SOURCES is missing,
        is not valid JSON, names an unknown service, or empties an address.
        """
        env = os.environ if environment is None else environment
        sources = dict(_DEFAULTS)
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
        return self.sources[POWER_DAILY].url

    @property
    def power_projection_url(self) -> str:
        """Address of the NASA POWER projection service (NEX-GDDP-CMIP6)."""
        return self.sources[POWER_PROJECTION].url


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


def _address(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DataSourceConfigError(
            f"{where} : une adresse non vide est obligatoire (une source ne peut pas être coupée)"
        )
    return value.strip()


def _with_file_entry(source: DataEndpoint, entry: Any) -> DataEndpoint:
    """A source with the fields of its entry in the file: an address alone ("key": "https://…")
    or an object {url, headers}."""
    if isinstance(entry, str) or entry is None:
        return replace(source, url=_address(entry, source.key))
    if not isinstance(entry, dict):
        raise DataSourceConfigError(f"{source.key} : une adresse ou un objet {{url, headers}}")
    changes: dict[str, Any] = {}
    if "url" in entry:
        changes["url"] = _address(entry["url"], source.key)
    if "headers" in entry:
        changes["headers"] = {str(k): str(v) for k, v in dict(entry["headers"]).items()}
    return replace(source, **changes)


def _with_environment(source: DataEndpoint, env: Mapping[str, str]) -> DataEndpoint:
    """A source with the address its environment variable gives."""
    name = URL_ENV_PREFIX + source.key.upper()
    if name in env:
        return replace(source, url=_address(env[name], name))
    return source
