"""MODIS NDVI at a point: every composite of a year in one request (Microsoft Planetary Computer).

MOD13Q1 (Terra) and MYD13Q1 (Aqua) are composites of 16 days at 250 m, 8 days apart: 46 a year
together. The Planetary Computer gives the value of every item of a search at a point in one
request (a "mosaic" search, then its point): 2 requests per point and year. The same series from
the ORNL DAAC service takes one request per two months and per band, 40 to 60 s each (measured on
2026-11-15).

Kept on disk per point and year.
"""

from __future__ import annotations

import datetime as dt
import time
from typing import Any, Final

import httpx

from field_shift.data_access.data_source_config import DataEndpoint
from field_shift.data_access.disk_cache import DataCache

COLLECTION: Final = "modis-13Q1-061"
#: Annual evapotranspiration, gap-filled (500 m): ET and potential ET, kg/m² × 10.
ET_COLLECTION: Final = "modis-16A3GF-061"
ET_SCALE: Final = 0.1
ET_VALID_RAW: Final = range(0, 32701)
ASSET: Final = "250m_16_days_NDVI"
SCALE: Final = 0.0001
VALID_RAW: Final = range(-2000, 10001)
#: Points closer than 0.002° (about 200 m, under the 250 m pixel) share an answer.
CACHE_PRECISION: Final = 500
TIMEOUT_S: Final = 90.0
ATTEMPTS: Final = 3
RETRY_WAIT_S: Final = 2.0
CACHE_NAMESPACE: Final = "modis-ndvi-point"


class NdviUnavailableError(RuntimeError):
    """The NDVI of a point could not be read."""


def composite_date(item_id: str) -> dt.date:
    """The first day of a composite, from its id ("…MOD13Q1.A2025353.h12v04…" → 2025-12-19)."""
    for part in item_id.split("."):
        if len(part) == 8 and part[0] == "A" and part[1:].isdigit():
            year, day = int(part[1:5]), int(part[5:])
            return dt.date(year, 1, 1) + dt.timedelta(days=day - 1)
    raise ValueError(f"identifiant MODIS sans date : {item_id}")


class ModisNdviClient:
    """The NDVI composites of a point and year."""

    def __init__(
        self,
        endpoint: DataEndpoint,
        http: httpx.Client | None = None,
        cache: DataCache | None = None,
    ) -> None:
        self._endpoint = endpoint
        self._http = http or httpx.Client(timeout=TIMEOUT_S)
        self._cache = cache or DataCache.default()

    @property
    def dataset(self) -> str:
        return self._endpoint.dataset

    def year_series(self, lat: float, lon: float, year: int) -> list[tuple[str, float]]:
        """(first day of the composite, NDVI) of every valid composite of `year`, by date.
        Raises NdviUnavailableError."""
        key = f"{round(lat * CACHE_PRECISION)}:{round(lon * CACHE_PRECISION)}:{year}:{COLLECTION}"
        series = self._cache.get_or_fetch(
            CACHE_NAMESPACE, key, lambda: self._download(lat, lon, year)
        )
        return [(day, value) for day, value in series]

    def annual_et_ratio(self, lat: float, lon: float, year: int) -> tuple[float, int]:
        """(ΣET / ΣPET of the year, the year read) at the point, from MOD16A3GF: the latest year
        served up to `year`. Raises NdviUnavailableError."""
        key = (
            f"{round(lat * CACHE_PRECISION)}:{round(lon * CACHE_PRECISION)}:{year}:{ET_COLLECTION}"
        )
        ratio, read_year = self._cache.get_or_fetch(
            CACHE_NAMESPACE, key, lambda: self._download_et_ratio(lat, lon, year)
        )
        return float(ratio), int(read_year)

    def _download_et_ratio(self, lat: float, lon: float, year: int) -> list[float]:
        stac = self._endpoint.url.replace("/data/v1", "/stac/v1")
        search = {
            "collections": [ET_COLLECTION],
            "intersects": {"type": "Point", "coordinates": [lon, lat]},
            "limit": 20,
        }
        found = self._call("POST", "", url=f"{stac}/search", json=search)
        items = sorted(
            (
                (composite_date(str(item["id"])).year, str(item["id"]))
                for item in found.get("features", [])
                if str(item.get("id", "")).startswith("MOD16A3GF")  # Terra, as MOD16A2
            ),
            reverse=True,
        )
        items = [(item_year, item) for item_year, item in items if item_year <= year]
        if not items:
            raise NdviUnavailableError(f"{ET_COLLECTION} : aucune année servie au point")
        item_year, item = items[0]
        values = []
        for asset in ("ET_500m", "PET_500m"):
            answer = self._call(
                "GET",
                f"/item/point/{lon},{lat}",
                params={"collection": ET_COLLECTION, "item": item, "assets": asset},
            )
            raw = (answer.get("values") or [None])[0]
            if raw is None or int(raw) not in ET_VALID_RAW:
                raise NdviUnavailableError(f"{ET_COLLECTION} : pas de valeur valide au point")
            values.append(int(raw) * ET_SCALE)
        actual, potential = values
        if potential <= 0:
            raise NdviUnavailableError(f"{ET_COLLECTION} : ET potentielle nulle au point")
        return [actual / potential, item_year]

    def _call(self, method: str, path: str, url: str | None = None, **kwargs) -> Any:
        last_error: Exception | None = None
        for attempt in range(ATTEMPTS):
            try:
                response = self._http.request(
                    method,
                    url or f"{self._endpoint.url}{path}",
                    headers=self._endpoint.headers,
                    **kwargs,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as error:
                last_error = error
                if error.response.status_code in (400, 404, 422):
                    break
            except (httpx.HTTPError, ValueError) as error:
                last_error = error
            if attempt + 1 < ATTEMPTS:
                time.sleep(RETRY_WAIT_S * (attempt + 1))
        raise NdviUnavailableError(f"{self.dataset} n’a pas répondu ({last_error})")

    def _download(self, lat: float, lon: float, year: int) -> list[tuple[str, float]]:
        point = {"type": "Point", "coordinates": [lon, lat]}
        search = {
            "collections": [COLLECTION],
            "filter-lang": "cql2-json",
            "filter": {
                "op": "and",
                "args": [
                    {"op": "s_intersects", "args": [{"property": "geometry"}, point]},
                    {
                        "op": "t_intersects",
                        "args": [
                            {"property": "datetime"},
                            {"interval": [f"{year}-01-01T00:00:00Z", f"{year}-12-31T23:59:59Z"]},
                        ],
                    },
                ],
            },
        }
        registered = self._call("POST", "/mosaic/register", json=search)
        try:
            search_id = registered["searchid"]
        except (KeyError, TypeError) as error:
            raise NdviUnavailableError(f"{self.dataset} : recherche refusée") from error
        answer = self._call(
            "GET",
            f"/mosaic/{search_id}/point/{lon},{lat}",
            params={"assets": ASSET, "collection": COLLECTION},
        )
        series: dict[str, float] = {}
        try:
            for item, values, _ in answer["values"]:
                raw = values[0]
                if raw is None or int(raw) not in VALID_RAW:
                    continue  # no valid value (cloud, fill)
                day = composite_date(str(item))
                if day.year == year:
                    series[day.isoformat()] = int(raw) * SCALE
        except (KeyError, TypeError, ValueError) as error:
            raise NdviUnavailableError(
                f"{self.dataset} : réponse inattendue ({error!r})"
            ) from error
        if not series:
            raise NdviUnavailableError(f"{self.dataset} : aucun NDVI valide en {year} au point")
        return sorted(series.items())
