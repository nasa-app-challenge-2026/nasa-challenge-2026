"""The projected climate of the farm: NASA NEX-GDDP-CMIP6, from the NASA POWER projection service.

NEX-GDDP-CMIP6 (Thrasher et al. 2022) is the CMIP6 models downscaled to 0.25° and bias-corrected
by NASA. The NASA POWER projection service serves it at a point, day by day: the ENSEMBLE of the
models (their mean), for three scenarios, from 2015 to 2100. It does not serve the models one by
one, nor their historical runs (checked on 2026-11-15: "Model … is not available in the daily
NEX-GDDP source"; "outside the available live data range" before 2015).

So the three scenarios are the three futures of step 3 (case 2), searched for twins one by one in
place of three models; and the change of each one is measured from its own first 20 years
(2015–2034, `REFERENCE_YEARS`), the observed weather being brought to that period by the trend of
NASA POWER first (see `TargetClimateProjector`). The delta method only uses monthly means of the
model: the smoothing of the daily values by the ensemble mean does not matter.

The NEX-GDDP-CMIP6 files themselves (one global grid per day and variable) take about 15 s per
year and variable to read at a point: the POWER service answers the 86 years in 2 s.

One request per scenario and place (about 1.6 MB), kept on disk.
"""

from __future__ import annotations

from typing import Any, Final

import httpx
import numpy as np

from field_shift.algorithm.climate.target_climate_projector import ModelSimulation
from field_shift.algorithm.config.climate import YearRange
from field_shift.algorithm.weather.daily_weather import DailyWeather
from field_shift.data_access.disk_cache import DataCache

API_URL: Final = "https://power.larc.nasa.gov/api/projection/daily/point"
#: (identifier of the service, name for the farmer)
SCENARIOS: Final = (("ssp126", "SSP1-2.6"), ("ssp245", "SSP2-4.5"), ("ssp370", "SSP3-7.0"))
MODEL: Final = "ensemble"
PARAMETERS: Final = ("T2M_MAX", "T2M_MIN", "PRECTOTCORR")
#: The years the service serves.
SERVED_YEARS: Final = YearRange(2015, 2100)
#: The change of a scenario is measured from its first 20 years.
REFERENCE_YEARS: Final = YearRange(2015, 2034)
FILL_VALUE: Final = -999
TIMEOUT_S: Final = 120.0
#: The NEX-GDDP-CMIP6 grid is 0.25°: points of the same cell share the same series.
CELLS_PER_DEGREE: Final = 4
CACHE_NAMESPACE: Final = "nex-gddp-cmip6"
MODELS_LABEL: Final = (
    "NEX-GDDP-CMIP6, ensemble des modèles (NASA POWER) : deltas mensuels, moyenne des "
    "scénarios SSP1-2.6, SSP2-4.5 et SSP3-7.0"
)


class ProjectionUnavailableError(RuntimeError):
    """The NASA POWER projection service could not give the projected climate."""


def _series(values: dict[str, Any], dates: list[str]) -> list[float]:
    """The values of every day of the calendar; a missing day takes the value of the day before."""
    out, previous = [], None
    for day in dates:
        value = values.get(day)
        if not isinstance(value, int | float) or value <= FILL_VALUE:
            if previous is None:
                raise ProjectionUnavailableError(f"NEX-GDDP-CMIP6 : pas de valeur le {day}")
            value = previous
        out.append(float(value))
        previous = float(value)
    return out


class PowerProjectionClient:
    """Reads the NEX-GDDP-CMIP6 ensemble of a point, once per scenario and place."""

    def __init__(
        self,
        http: httpx.Client | None = None,
        url: str = API_URL,
        cache: DataCache | None = None,
    ) -> None:
        self._http = http or httpx.Client(timeout=TIMEOUT_S)
        self._url = url
        self._cache = cache or DataCache.default()

    def daily(self, lat: float, lon: float, scenario: str) -> DailyWeather:
        """Every day of SERVED_YEARS at the point (°C, mm/day). Raises
        ProjectionUnavailableError."""
        key = (
            f"{round(lat * CELLS_PER_DEGREE)}:{round(lon * CELLS_PER_DEGREE)}:{scenario}:"
            f"{MODEL}:{SERVED_YEARS.first}-{SERVED_YEARS.last}"
        )
        columns = self._cache.get_or_fetch(
            CACHE_NAMESPACE, key, lambda: self._download(lat, lon, scenario)
        )
        return DailyWeather.from_series(
            SERVED_YEARS.first,
            SERVED_YEARS.last,
            np.array(columns["T2M_MAX"]),
            np.array(columns["T2M_MIN"]),
            np.array(columns["PRECTOTCORR"]),
        )

    def _download(self, lat: float, lon: float, scenario: str) -> dict[str, list[float]]:
        params = {
            "parameters": ",".join(PARAMETERS),
            "community": "AG",
            "latitude": f"{lat:.4f}",
            "longitude": f"{lon:.4f}",
            "start": f"{SERVED_YEARS.first}0101",
            "end": f"{SERVED_YEARS.last}1231",
            "model": MODEL,
            "scenario": scenario,
            "time-standard": "UTC",
            "format": "JSON",
        }
        try:
            response = self._http.get(self._url, params=params)
            response.raise_for_status()
            parameter = response.json()["properties"]["parameter"]
            by_name = {name: parameter[name][scenario] for name in PARAMETERS}
        except httpx.HTTPStatusError as error:
            raise ProjectionUnavailableError(
                f"NASA POWER (projections NEX-GDDP-CMIP6) a répondu {error.response.status_code} "
                f"pour {scenario}"
            ) from error
        except httpx.HTTPError as error:
            raise ProjectionUnavailableError(
                f"NASA POWER (projections NEX-GDDP-CMIP6) n’a pas répondu ({error})"
            ) from error
        except (KeyError, TypeError, ValueError) as error:
            raise ProjectionUnavailableError(
                f"NASA POWER (projections NEX-GDDP-CMIP6) : réponse inattendue ({error!r})"
            ) from error
        days = np.arange(
            np.datetime64(f"{SERVED_YEARS.first}-01-01"),
            np.datetime64(f"{SERVED_YEARS.last + 1}-01-01"),
            dtype="datetime64[D]",
        )
        dates = [str(day).replace("-", "") for day in days]
        return {name: _series(values, dates) for name, values in by_name.items()}


class ProjectedScenario:
    """One scenario of the NEX-GDDP-CMIP6 ensemble at the farm, as a climate model of step 3."""

    def __init__(
        self, client: PowerProjectionClient, lat: float, lon: float, scenario: str, label: str
    ) -> None:
        self.name = f"NEX-GDDP-CMIP6 {label}"
        self._client = client
        self._lat = lat
        self._lon = lon
        self._scenario = scenario

    def simulate(self, first_year: int, last_year: int) -> ModelSimulation:
        """The scenario on its reference years (2015–2034) and on the window."""
        if first_year < SERVED_YEARS.first or last_year > SERVED_YEARS.last:
            raise ProjectionUnavailableError(
                f"NEX-GDDP-CMIP6 couvre {SERVED_YEARS.first}–{SERVED_YEARS.last} : la fenêtre "
                f"{first_year}–{last_year} en sort"
            )
        series = self._client.daily(self._lat, self._lon, self._scenario)
        return ModelSimulation(
            historical=series.between(REFERENCE_YEARS.first, REFERENCE_YEARS.last),
            future=series.between(first_year, last_year),
            reference=REFERENCE_YEARS,
        )


def projected_scenarios(
    client: PowerProjectionClient, lat: float, lon: float
) -> list[ProjectedScenario]:
    """The three scenarios at the farm (nothing is read before a cycle needs them)."""
    return [ProjectedScenario(client, lat, lon, scenario, label) for scenario, label in SCENARIOS]
