"""SoilGrids 2.0 (ISRIC) at a point, read on its Web Coverage Service, kept on disk.

    topsoil_soil(…)     the soil of step 5 (twin fields and sections): clay, sand, organic
                        carbon and pH, mean over 0–30 cm
    mean_over(…)        any property over any layers: 0–15 cm for the soil protection (ranking),
                        0–200 cm for the water model

The REST API of SoilGrids (`properties/query`) answered in 1 s to more than 90 s on 2026-11-15,
often not at all; its WCS (the same maps) answered every coverage in 0.2 to 0.5 s. One coverage per
property and layer is read (a 1 × 1 pixel window around the point), in parallel: 12 small
requests for the topsoil.

The maps are in "mapped units" (g/kg of clay, dg/kg of carbon, pH × 10): `D_FACTOR` converts them
to %, g/kg and pH. A point without soil (water, built-up area, rock) has the value 0 in every map:
`NoSoilError`, never a default soil.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Final

import httpx

from field_shift.algorithm.twins.soil_comparison import Soil
from field_shift.data_access.data_source_config import DataEndpoint
from field_shift.data_access.disk_cache import DataCache
from field_shift.data_access.geotiff import GeoTiffError, read_geotiff

PROPERTIES: Final = ("sand", "clay", "soc", "phh2o")
#: Layers of the topsoil and their thickness (cm).
DEPTHS: Final = (("0-5cm", 5.0), ("5-15cm", 10.0), ("15-30cm", 15.0))
#: Every layer of SoilGrids and its thickness (cm).
ALL_DEPTHS: Final = (*DEPTHS, ("30-60cm", 30.0), ("60-100cm", 40.0), ("100-200cm", 100.0))
#: Mapped units → %, g/kg and pH: the same factor for the four properties.
D_FACTOR: Final = 10.0
#: Half the side of the window read around the point (about 170 m: one 250 m pixel).
HALF_WINDOW_DEG: Final = 0.0015
#: Points closer than 0.001° (about 100 m, under the 250 m of SoilGrids) share an answer.
CACHE_PRECISION: Final = 1000
TIMEOUT_S: Final = 60.0
ATTEMPTS: Final = 3
RETRY_WAIT_S: Final = 2.0
MAX_PARALLEL_REQUESTS: Final = 6
EPSG_4326: Final = "http://www.opengis.net/def/crs/EPSG/0/4326"
CACHE_NAMESPACE: Final = "soilgrids-wcs"


class SoilGridsError(RuntimeError):
    """SoilGrids could not be read (the message says why, in French)."""


class NoSoilError(SoilGridsError):
    """SoilGrids has no soil at the point: water, built-up area or rock."""


class SoilGridsClient:
    """Reads SoilGrids at a point, once per point, property and layer."""

    def __init__(
        self,
        endpoint: DataEndpoint,
        http: httpx.Client | None = None,
        cache: DataCache | None = None,
        attempts: int = ATTEMPTS,
    ) -> None:
        """`attempts` = how many times a request is tried (fewer where the soil is optional)."""
        self._endpoint = endpoint
        self._http = http or httpx.Client(timeout=TIMEOUT_S)
        self._cache = cache or DataCache.default()
        self._attempts = attempts

    @property
    def dataset(self) -> str:
        return self._endpoint.dataset

    def layers(
        self,
        lat: float,
        lon: float,
        depths: Sequence[tuple[str, float]] = DEPTHS,
        properties: Sequence[str] = PROPERTIES,
    ) -> dict[str, dict[str, float | None]]:
        """{property: {layer: value in %, g/kg or pH; None where SoilGrids has none}}."""
        labels = tuple(label for label, _ in depths)
        key = f"{round(lat * CACHE_PRECISION)}:{round(lon * CACHE_PRECISION)}"
        jobs = [(name, label) for name in properties for label in labels]

        def read(job: tuple[str, str]) -> float | None:
            name, label = job
            return self._cache.get_or_fetch(
                CACHE_NAMESPACE, f"{key}:{name}:{label}", lambda: [self._coverage(lat, lon, *job)]
            )[0]

        with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_REQUESTS, len(jobs))) as pool:
            values = list(pool.map(read, jobs))
        out: dict[str, dict[str, float | None]] = {name: {} for name in properties}
        for (name, label), value in zip(jobs, values, strict=True):
            out[name][label] = value
        return out

    def mean_over(
        self,
        lat: float,
        lon: float,
        depths: Sequence[tuple[str, float]] = DEPTHS,
        properties: Sequence[str] = PROPERTIES,
    ) -> dict[str, float]:
        """Every property averaged over `depths` (weighted by their thickness). Raises
        NoSoilError when a value is missing."""
        layers = self.layers(lat, lon, depths, properties)
        total = sum(thickness for _, thickness in depths)
        means = {}
        for name in properties:
            values = [layers[name][label] for label, _ in depths]
            if any(value is None for value in values):
                raise NoSoilError(
                    f"{self.dataset} : pas de sol au point ({lat:.5f}, {lon:.5f}) : eau, zone "
                    "bâtie ou roche"
                )
            means[name] = (
                sum(value * thickness for value, (_, thickness) in zip(values, depths, strict=True))
                / total
            )
        return means

    def topsoil_soil(self, lat: float, lon: float) -> Soil:
        """The soil of step 5: clay, sand, organic carbon and pH over 0–30 cm."""
        means = self.mean_over(lat, lon, DEPTHS)
        return Soil(
            clay_pct=means["clay"],
            sand_pct=means["sand"],
            organic_carbon=means["soc"],
            ph=means["phh2o"],
        )

    def _coverage(self, lat: float, lon: float, name: str, label: str) -> float | None:
        """The value of one map at the point (None: no soil there)."""
        params = [
            ("map", f"/map/{name}.map"),
            ("SERVICE", "WCS"),
            ("VERSION", "2.0.1"),
            ("REQUEST", "GetCoverage"),
            ("COVERAGEID", f"{name}_{label}_mean"),
            ("FORMAT", "image/tiff"),
            ("SUBSET", f"long({lon - HALF_WINDOW_DEG:.6f},{lon + HALF_WINDOW_DEG:.6f})"),
            ("SUBSET", f"lat({lat - HALF_WINDOW_DEG:.6f},{lat + HALF_WINDOW_DEG:.6f})"),
            ("SUBSETTINGCRS", EPSG_4326),
            ("OUTPUTCRS", EPSG_4326),
        ]
        last_error: Exception | None = None
        for attempt in range(self._attempts):
            try:
                response = self._http.get(
                    self._endpoint.url, params=params, headers=self._endpoint.headers
                )
                response.raise_for_status()
                raw = read_geotiff(response.content).at(lon, lat)
                return None if raw is None or raw <= 0 else raw / D_FACTOR
            except httpx.HTTPStatusError as error:
                last_error = error
                if error.response.status_code in (400, 404, 422):
                    break
            except (httpx.HTTPError, GeoTiffError) as error:
                last_error = error
            if attempt + 1 < self._attempts:
                time.sleep(RETRY_WAIT_S * (attempt + 1))
        raise SoilGridsError(f"{self.dataset} n’a pas répondu ({name} {label} : {last_error})")
