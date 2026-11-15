"""What the twin fields grow (steps 5 and 6): the crop maps of the twin cells.

In a twin cell (a NASA POWER cell of the grid), a window of 16 km × 16 km at its centre is sampled
on a grid of 64 × 64 points (one every 250 m), and the crop of each point is read on the crop map
of each of the last 8 years:

    in Canada         Annual Crop Inventory of AAFC (30 m), 2017–2024
    in the U.S.       USDA NASS Cropland Data Layer (30 m) on Microsoft Planetary Computer, the
                      8 last years it serves (2014–2021)

A point that is a known crop every year is a field: its crops are its sequence (step 6). A cell
with fewer than MIN_FIELDS fields is not cultivated: it is no twin. The soil of the cell (step 5)
is SoilGrids at the centre of its window; its fields are kept when that soil is comparable to the
soil of the section (`SoilFilter`, tolerances widened under 200 fields).

Every map is read once per cell and year, and kept on disk; the cells checked together are read in
parallel.

Step 7, the value of a previous crop, needs the greenness of the twin fields (NASA HLS): it is not
computed here. It stays unknown (None) and the plan lists those gaps; no value is written in its
place.
"""

from __future__ import annotations

import json
import math
import threading
import time
from collections import defaultdict
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from typing import Final
from urllib.parse import quote

import httpx

from field_shift.algorithm.config.climate import TWIN_PERIOD
from field_shift.algorithm.twins.climate_twin_finder import GridCell, Twin
from field_shift.algorithm.twins.soil_comparison import Soil, SoilFilter
from field_shift.algorithm.twins.twin_evidence import TwinEvidence
from field_shift.algorithm.twins.twin_evidence_builder import TwinField, build_twin_evidence
from field_shift.algorithm.yield_model.sources.crop_history import (
    is_border_straddling_bbox,
    is_location_in_canada,
)
from field_shift.algorithm.yield_model.sources.raster_parser import (
    parse_npy_grid,
    parse_uncompressed_tiff_u8,
)
from field_shift.data_access.data_source_config import DataEndpoint
from field_shift.data_access.disk_cache import DataCache
from field_shift.data_access.soilgrids import NoSoilError, SoilGridsClient, SoilGridsError

WINDOW_HALF_KM: Final = 8.0
GRID_SIZE: Final = 64
SEQUENCE_YEARS: Final = 8
KM_PER_DEGREE_LAT: Final = 111.32
#: Area each sampled point stands for (16 km × 16 km / 4096 points).
POINT_AREA_HA: Final = (2 * WINDOW_HALF_KM) ** 2 * 100 / GRID_SIZE**2
#: Fewest fields (points cultivated all 8 years) for a cell to count as cultivated.
MIN_FIELDS: Final = 100
#: Cells read at the same time, and years of one cell read at the same time (at most
#: MAX_PARALLEL_CELLS × MAX_PARALLEL_REQUESTS requests at once).
MAX_PARALLEL_CELLS: Final = 4
MAX_PARALLEL_REQUESTS: Final = 8
TIMEOUT_S: Final = 90.0
CONNECT_TIMEOUT_S: Final = 15.0
#: The AAFC image service refuses many connections at once from one address (connection and
#: TLS handshake timeouts above ~4, measured on 2026-11-15) but answers one in 0.1 s: at most 2
#: of its requests run at the same time. Planetary Computer takes more.
AAFC_MAX_CONNECTIONS: Final = 2
PLANETARY_MAX_CONNECTIONS: Final = 6
ATTEMPTS: Final = 4
RETRY_WAIT_S: Final = 1.5
CACHE_NAMESPACE: Final = "crop-maps"
AAFC: Final = "AAFC"
CDL: Final = "USDA_CDL"

#: USDA Cropland Data Layer class → the crop(s) of the year, in the order they are harvested.
#: A class missing here (forest, water, towns, crops the plan does not know) makes the point no
#: field. Double crops give two crops in the year.
CDL_CROPS: Final[dict[int, tuple[str, ...]]] = {
    1: ("mais",),
    5: ("soya",),
    21: ("orge",),
    24: ("ble-automne",),
    26: ("ble-automne", "soya-2e"),
    27: ("seigle",),
    28: ("avoine",),
    31: ("canola",),
    36: ("luzerne",),
    37: ("foin",),
    39: ("sarrasin",),
    41: ("betterave",),
    42: ("haricot-sec",),
    43: ("pomme-de-terre",),
    49: ("oignon",),
    53: ("pois",),
    54: ("tomate",),
    61: ("jachere",),
    206: ("carotte",),
    222: ("courge",),
    225: ("ble-automne", "mais"),
    226: ("avoine", "mais"),
    227: ("laitue",),
    237: ("orge", "mais"),
    240: ("soya", "avoine"),
    243: ("chou",),
    246: ("radis",),
    247: ("navet",),
    254: ("orge", "soya-2e"),
}
#: AAFC Annual Crop Inventory class → the crop of the year (same rule).
AAFC_CROPS: Final[dict[int, tuple[str, ...]]] = {
    122: ("foin",),  # pasture and forages: hay crops (the plan has no pasture)
    131: ("jachere",),
    133: ("orge",),
    136: ("avoine",),
    137: ("seigle",),
    145: ("ble-automne",),
    147: ("mais",),
    153: ("canola",),
    158: ("soya",),
    162: ("pois",),
    167: ("haricot-sec",),
    176: ("tomate",),
    177: ("pomme-de-terre",),
    178: ("betterave",),
    195: ("sarrasin",),
}


class CropMapsUnavailableError(RuntimeError):
    """A crop map could not be read for a twin cell."""


@dataclass(frozen=True)
class CellField(TwinField):
    """A field of a twin cell, with the soil of its cell (None: SoilGrids has none there)."""

    soil: Soil | None = None


@dataclass(frozen=True)
class CellCrops:
    """What the crop maps say of a cell: its fields (sequence → number of points)."""

    provider: str
    years: tuple[int, ...]
    sequences: dict[tuple[str, ...], int]

    @property
    def field_count(self) -> int:
        return sum(self.sequences.values())


def window_of(lat: float, lon: float) -> dict[str, float]:
    """The window sampled in a cell, centred on its centre."""
    dlat = WINDOW_HALF_KM / KM_PER_DEGREE_LAT
    dlon = WINDOW_HALF_KM / (KM_PER_DEGREE_LAT * max(math.cos(math.radians(lat)), 0.1))
    return {"minLon": lon - dlon, "minLat": lat - dlat, "maxLon": lon + dlon, "maxLat": lat + dlat}


def sequences_of(
    codes_by_year: Sequence[Sequence[int]], table: dict[int, tuple[str, ...]]
) -> dict[tuple[str, ...], int]:
    """The crop sequence of every point that is a known crop every year, counted."""
    counts: dict[tuple[str, ...], int] = defaultdict(int)
    for point in zip(*codes_by_year, strict=True):
        crops: list[str] = []
        for code in point:
            year_crops = table.get(int(code))
            if year_crops is None:
                break
            crops.extend(year_crops)
        else:
            counts[tuple(crops)] += 1
    return dict(counts)


class TwinCropMaps:
    """The crop maps and soils of the twin cells, and the evidence they give."""

    def __init__(
        self,
        aafc: DataEndpoint,
        cdl: DataEndpoint,
        soilgrids: SoilGridsClient,
        http: httpx.Client | None = None,
        cache: DataCache | None = None,
    ) -> None:
        self._aafc = aafc
        self._cdl = cdl
        self._soilgrids = soilgrids
        self._http = http or httpx.Client(
            timeout=httpx.Timeout(TIMEOUT_S, connect=CONNECT_TIMEOUT_S), follow_redirects=True
        )
        self._slots = {
            aafc.dataset: threading.BoundedSemaphore(AAFC_MAX_CONNECTIONS),
            cdl.dataset: threading.BoundedSemaphore(PLANETARY_MAX_CONNECTIONS),
        }
        self._cache = cache or DataCache.default()

    # --- The check of step 4: which candidate cells are cultivated --------------------------------

    def cultivated(self, cells: Sequence[GridCell]) -> list[bool]:
        """For each cell, are there enough fields in its window? (read in parallel)"""
        with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_CELLS, max(1, len(cells)))) as pool:
            crops = list(pool.map(self.cell_crops, cells))
        return [c.field_count >= MIN_FIELDS for c in crops]

    # --- Steps 5 and 6 ---------------------------------------------------------------------------

    def evidence_for(
        self, first_year: int, last_year: int, twins: Sequence[Twin], soil: Soil | None
    ) -> TwinEvidence:
        """What the twin fields of a comparable soil grow, for the field of `soil`."""
        with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_CELLS, max(1, len(twins)))) as pool:
            crops = list(pool.map(lambda twin: self.cell_crops(twin.cell), twins))
            soils = list(pool.map(lambda twin: self.cell_soil(twin.cell), twins))
        fields = [
            CellField(sequence, count * POINT_AREA_HA, twin.sigma, cell_soil)
            for twin, cell_crops, cell_soil in zip(twins, crops, soils, strict=True)
            for sequence, count in cell_crops.sequences.items()
        ]
        kept = fields
        if soil is not None:
            known = [f for f in fields if f.soil is not None]
            unknown = [f for f in fields if f.soil is None]
            kept = SoilFilter(soil).keep_comparable(known).fields + unknown
            if not kept:  # no twin field of a comparable soil: the twins as they are
                kept = fields
        evidence = build_twin_evidence(kept, (), twins)
        if not evidence.crops and kept:
            # Every twin is beyond σ = 2: no field counts. The closest ones still say what grows
            # in the nearest climate, and the mean σ (above 2) tells the plan it is less reliable.
            sigmas = [f.sigma for f in kept]
            evidence = build_twin_evidence([replace(f, sigma=0.0) for f in kept], (), twins)
            evidence.sigma_mean = sum(sigmas) / len(sigmas)
        return evidence

    def cell_soil(self, cell: GridCell) -> Soil | None:
        """SoilGrids at the centre of the window of the cell (None: no soil there, or SoilGrids
        did not answer — its fields are then kept without a soil check)."""
        try:
            return self._soilgrids.topsoil_soil(cell.lat, cell.lon)
        except (NoSoilError, SoilGridsError):
            return None

    # --- Crop maps -------------------------------------------------------------------------------

    def cell_crops(self, cell: GridCell) -> CellCrops:
        """The fields of the window of a cell (read once, kept on disk)."""
        window = window_of(cell.lat, cell.lon)
        canada = is_location_in_canada(cell.lat, cell.lon)
        providers = (AAFC, CDL) if canada else (CDL, AAFC)
        if not is_border_straddling_bbox(window):
            providers = providers[:1]
        best: CellCrops | None = None
        for provider in providers:
            crops = self._provider_crops(provider, cell, window)
            if best is None or crops.field_count > best.field_count:
                best = crops
        assert best is not None
        return best

    def _provider_crops(self, provider: str, cell: GridCell, window: dict) -> CellCrops:
        key = (
            f"{provider}:{cell.lat:.3f}:{cell.lon:.3f}:{WINDOW_HALF_KM}:{GRID_SIZE}:"
            f"{SEQUENCE_YEARS}"
        )
        stored = self._cache.get_or_fetch(
            CACHE_NAMESPACE, key, lambda: self._read_maps(provider, cell, window)
        )
        table = AAFC_CROPS if provider == AAFC else CDL_CROPS
        return CellCrops(provider, tuple(stored["years"]), sequences_of(stored["codes"], table))

    def _read_maps(self, provider: str, cell: GridCell, window: dict) -> dict:
        if provider == AAFC:
            years = list(range(TWIN_PERIOD.last - SEQUENCE_YEARS + 1, TWIN_PERIOD.last + 1))
            items = {year: str(year) for year in years}
            read = self._aafc_tile
        else:
            items = self._cdl_items(cell)
            years = sorted(year for year in items if year <= TWIN_PERIOD.last)[-SEQUENCE_YEARS:]
            if len(years) < SEQUENCE_YEARS:
                return {"years": [], "codes": []}  # no CDL here (outside the U.S.)
            read = self._cdl_tile
        with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_REQUESTS, len(years))) as pool:
            codes = list(pool.map(lambda year: read(items[year], window), years))
        return {"years": years, "codes": codes}

    def _get(self, url: str, dataset: str, **kwargs) -> httpx.Response:
        """One request to a crop map service: few at a time per service, tried again after a
        connection failure or an error of the server."""
        method = kwargs.pop("method", "GET")
        last_error: Exception | None = None
        for attempt in range(ATTEMPTS):
            try:
                with self._slots[dataset]:
                    response = self._http.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as error:
                last_error = error
                if error.response.status_code < 500:
                    raise CropMapsUnavailableError(
                        f"{dataset} a répondu {error.response.status_code}"
                    ) from error
            except httpx.HTTPError as error:
                last_error = error
            if attempt + 1 < ATTEMPTS:
                time.sleep(RETRY_WAIT_S * (attempt + 1))
        raise CropMapsUnavailableError(f"{dataset} n’a pas répondu ({last_error})")

    def _aafc_tile(self, year: str, window: dict) -> list[int]:
        bbox = ",".join(f"{window[k]:.6f}" for k in ("minLon", "minLat", "maxLon", "maxLat"))
        params = {
            "bbox": bbox,
            "bboxSR": "4326",
            "imageSR": "4326",
            "size": f"{GRID_SIZE},{GRID_SIZE}",
            "interpolation": "RSP_NearestNeighbor",
            "pixelType": "U8",
            "format": "tiff",
            "compression": "NONE",
            "f": "image",
        }
        url = f"{self._aafc.url}/{year}/ImageServer/exportImage"
        response = self._get(url, self._aafc.dataset, params=params, headers=self._aafc.headers)
        try:
            parsed = parse_uncompressed_tiff_u8(
                response.content, expected_width=GRID_SIZE, expected_height=GRID_SIZE
            )
        except ValueError as error:
            raise CropMapsUnavailableError(f"{self._aafc.dataset} {year} : {error}") from error
        return [int(code) for code in parsed["pixels"]]

    def _cdl_items(self, cell: GridCell) -> dict[int, str]:
        """The CDL item of each year at the centre of the cell."""
        body = {
            "collections": ["usda-cdl"],
            "intersects": {"type": "Point", "coordinates": [cell.lon, cell.lat]},
            "limit": 100,
        }
        response = self._get(
            f"{self._cdl.url}/stac/v1/search",
            self._cdl.dataset,
            method="POST",
            content=json.dumps(body),
            headers={"Content-Type": "application/json", **self._cdl.headers},
        )
        items = {}
        for feature in response.json().get("features", []):
            identifier = str(feature.get("id", ""))
            if identifier.startswith("cropland_") and "cropland" in feature.get("assets", {}):
                year = int(identifier.split("_")[1])
                items[year] = identifier
        return items

    def _cdl_tile(self, item: str, window: dict) -> list[int]:
        bbox = ",".join(f"{window[k]:.6f}" for k in ("minLon", "minLat", "maxLon", "maxLat"))
        url = (
            f"{self._cdl.url}/data/v1/item/crop/{bbox}.npy?collection=usda-cdl"
            f"&item={quote(item, safe='')}&assets=cropland&width={GRID_SIZE}"
            f"&height={GRID_SIZE}&coord_crs=epsg:4326&resampling=nearest"
        )
        response = self._get(url, self._cdl.dataset, headers=self._cdl.headers)
        try:
            parsed = parse_npy_grid(
                response.content, expected_width=GRID_SIZE, expected_height=GRID_SIZE
            )
        except ValueError as error:
            raise CropMapsUnavailableError(f"{self._cdl.dataset} {item} : {error}") from error
        data, mask = parsed["bands"][0], parsed["bands"][-1]
        # outside the tile (masked): no crop
        return [int(code) if int(valid) else 0 for code, valid in zip(data, mask, strict=True)]
