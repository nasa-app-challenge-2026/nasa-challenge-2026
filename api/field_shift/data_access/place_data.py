"""Steps 3 to 7 of a place, from the real data services (the `PlaceDataProvider` of the server).

    climate models   NASA NEX-GDDP-CMIP6, ensemble of the models, 3 scenarios (power_projection.py)
    twin grid        NASA POWER, observed climates 2011–2024 of the cells around the farm
                     (power_grid.py)
    twin crops       AAFC Annual Crop Inventory and USDA Cropland Data Layer, soils of SoilGrids
                     (twin_crops.py)
    precrop values   the regional yield model of the team, MODIS NDVI and crop maps of the region
                     of the farm (yield_precrops.py)

Nothing is read before it is needed: the grid when the place is first planned (then kept on disk),
the projections when a cycle ends more than 10 years ahead, the crop maps of a cell when it is a
candidate twin.
"""

from __future__ import annotations

from typing import Final

import httpx

from field_shift.algorithm.sources.data_source import DataSource
from field_shift.algorithm.sources.place_sources import (
    CLIMATE_MODELS_KEY,
    TWIN_CROPS_KEY,
    TWINS_KEY,
    PlaceSources,
)
from field_shift.algorithm.weather.daily_weather import DailyWeather
from field_shift.data_access.data_source_config import (
    AAFC_CROPS,
    POWER_REGIONAL,
    SOILGRIDS,
    USDA_CDL,
    DataSourceConfig,
)
from field_shift.data_access.disk_cache import DataCache
from field_shift.data_access.power_grid import PowerGridClient
from field_shift.data_access.power_projection import (
    MODELS_LABEL,
    PowerProjectionClient,
    projected_scenarios,
)
from field_shift.data_access.soilgrids import SoilGridsClient
from field_shift.data_access.twin_crops import TwinCropMaps
from field_shift.data_access.yield_precrops import (
    PairMatrixReader,
    read_precrop_values,
    regional_pair_matrix,
    with_regional_precrops,
)

#: The soil of a twin cell only sharpens step 5: SoilGrids is tried once, 45 s at most.
TWIN_SOIL_TIMEOUT_S: Final = 45.0

PLACE_SOURCES: Final = (
    DataSource(
        CLIMATE_MODELS_KEY,
        True,
        "NASA NEX-GDDP-CMIP6, ensemble des modèles (service de projections de NASA POWER) : "
        "scénarios SSP1-2.6, SSP2-4.5 et SSP3-7.0",
    ),
    DataSource(
        TWINS_KEY,
        True,
        "Climats observés 2011–2024 des cases NASA POWER (0,5°) sur 10° × 10° autour de la ferme",
    ),
    DataSource(
        TWIN_CROPS_KEY,
        True,
        "Cultures des champs jumeaux : Inventaire annuel des cultures (AAC) au Canada, USDA "
        "Cropland Data Layer aux États-Unis ; sol des jumeaux : SoilGrids 2.0",
    ),
)


class RemotePlaceData:
    """The real steps 3 to 7 of any place."""

    def __init__(
        self,
        config: DataSourceConfig,
        cache: DataCache | None = None,
        pair_matrix: PairMatrixReader = regional_pair_matrix,
    ) -> None:
        self._pair_matrix = pair_matrix
        cache = cache or DataCache.default()
        self._projection = PowerProjectionClient(url=config.power_projection_url, cache=cache)
        self._grid = PowerGridClient(url=config[POWER_REGIONAL].url, cache=cache)
        twin_soils = SoilGridsClient(
            config[SOILGRIDS],
            http=httpx.Client(timeout=TWIN_SOIL_TIMEOUT_S),
            cache=cache,
            attempts=1,
        )
        self._crops = TwinCropMaps(config[AAFC_CROPS], config[USDA_CDL], twin_soils, cache=cache)

    def place_sources(self, lat: float, lon: float, farm_weather: DailyWeather) -> PlaceSources:
        precrops = read_precrop_values(lat, lon, self._pair_matrix)
        return PlaceSources(
            models=projected_scenarios(self._projection, lat, lon),
            models_label=MODELS_LABEL,
            grid=self._grid.cells(lat, lon),
            cultivation=self._crops.cultivated,
            evidence_for=with_regional_precrops(self._crops.evidence_for, precrops),
            sources=(*PLACE_SOURCES, precrops.source),
        )
