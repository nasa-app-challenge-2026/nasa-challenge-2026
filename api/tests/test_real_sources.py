"""The readers of the real data sources of the plan, on faked services (no network):

the disk cache (a request is made once, even after a restart; a failure is never kept),
NASA POWER (one request per place for the plan and the water model),
NEX-GDDP-CMIP6 (the projections of NASA POWER) and how its changes reach the target climate,
the NASA POWER grid of the twins, the crop maps of the twins (AAFC, USDA CDL),
the measures of a section (slope, heavy rain, bare soil, soil),
and the twin search that asks the crop maps only for the candidate cells.
"""

from __future__ import annotations

import io
import json
import struct
import threading
from datetime import date

import httpx
import numpy as np
import pytest

from field_shift.algorithm.climate.indicator_table import IndicatorTable
from field_shift.algorithm.climate.target_climate_projector import (
    ModelSimulation,
    TargetClimateProjector,
)
from field_shift.algorithm.config.climate import FARM_WEATHER_YEARS, YearRange
from field_shift.algorithm.sources.field_data import SectionPlace
from field_shift.algorithm.twins.climate_twin_finder import ClimateTwinFinder, GridCell, Twin
from field_shift.algorithm.twins.soil_comparison import Soil
from field_shift.algorithm.weather.daily_weather import DailyWeather
from field_shift.data_access.data_source_config import (
    AAFC_CROPS,
    SOILGRIDS,
    USDA_CDL,
    DataSourceConfig,
)
from field_shift.data_access.disk_cache import DataCache
from field_shift.data_access.field_measures import (
    RemoteFieldData,
    bare_soil_days,
    heavy_rain_days,
    square_around,
)
from field_shift.data_access.nasa_power import DOWNLOAD_YEARS, NasaPowerClient
from field_shift.data_access.power_grid import PowerGridClient, grid_box
from field_shift.data_access.power_projection import (
    REFERENCE_YEARS,
    SERVED_YEARS,
    PowerProjectionClient,
    ProjectedScenario,
    ProjectionUnavailableError,
)
from field_shift.data_access.soilgrids import NoSoilError, SoilGridsClient
from field_shift.data_access.twin_crops import (
    AAFC_CROPS as AAFC_TABLE,
)
from field_shift.data_access.twin_crops import (
    CDL_CROPS,
    GRID_SIZE,
    MIN_FIELDS,
    TwinCropMaps,
    sequences_of,
)
from tests.helpers.demo_farm_weather import demo_farm_weather
from tests.helpers.soilgrids_stub import WCS_HOST, wcs_answer

CONFIG = DataSourceConfig.load({})


def calendar(first: int, last: int) -> list[str]:
    days = np.arange(
        np.datetime64(f"{first}-01-01"), np.datetime64(f"{last + 1}-01-01"), dtype="datetime64[D]"
    )
    return [str(day).replace("-", "") for day in days]


def client_of(handle) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handle))


# --- The disk cache -------------------------------------------------------------------------------


class TestDiskCache:
    def test_a_value_is_fetched_once_and_read_back_after_a_restart(self, tmp_path):
        calls = []
        first = DataCache(tmp_path)
        assert first.get_or_fetch("ns", "k", lambda: calls.append(1) or {"a": [1, 2]}) == {
            "a": [1, 2]
        }
        assert first.get_or_fetch("ns", "k", lambda: calls.append(1) or {}) == {"a": [1, 2]}
        restarted = DataCache(tmp_path)  # a new server: only the disk
        assert restarted.get_or_fetch("ns", "k", lambda: calls.append(1) or {}) == {"a": [1, 2]}
        assert len(calls) == 1

    def test_a_failure_is_not_kept(self, tmp_path):
        cache = DataCache(tmp_path)

        def broken():
            raise RuntimeError("service en panne")

        with pytest.raises(RuntimeError):
            cache.get_or_fetch("ns", "k", broken)
        assert cache.get_or_fetch("ns", "k", lambda: 3) == 3

    def test_the_same_key_asked_at_the_same_time_is_fetched_once(self):
        cache = DataCache.in_memory()
        calls, gate = [], threading.Event()

        def slow():
            calls.append(1)
            gate.wait(1)
            return "ok"

        threads = [
            threading.Thread(target=lambda: cache.get_or_fetch("ns", "k", slow)) for _ in range(4)
        ]
        for thread in threads:
            thread.start()
        gate.set()
        for thread in threads:
            thread.join()
        assert calls == [1]

    def test_a_broken_file_is_read_again_from_the_service(self, tmp_path):
        cache = DataCache(tmp_path)
        cache.put("ns", "k", 1)
        next((tmp_path / "ns").glob("*.json")).write_text("{coupé", encoding="utf-8")
        assert DataCache(tmp_path).get_or_fetch("ns", "k", lambda: 2) == 2


# --- NASA POWER: one request per place ------------------------------------------------------------


def power_answer(first: int, last: int) -> dict:
    days = calendar(first, last)
    rows = {"T2M_MAX": 25.0, "T2M_MIN": 5.0, "PRECTOTCORR": 2.0, "RH2M": 70.0, "WS2M": 2.0,
            "ALLSKY_SFC_SW_DWN": 15.0, "GWETROOT": 0.6}  # fmt: skip
    return {
        "properties": {"parameter": {k: dict.fromkeys(days, v) for k, v in rows.items()}},
        "geometry": {"coordinates": [-72.9, 45.6, 40.0]},
        "header": {"fill_value": -999},
        "parameters": {"ALLSKY_SFC_SW_DWN": {"units": "MJ/m^2/day"}},
    }


class TestNasaPower:
    def test_one_request_gives_the_plan_and_the_water_model_and_is_kept_on_disk(self, tmp_path):
        requests: list[httpx.Request] = []
        answer = json.dumps(power_answer(DOWNLOAD_YEARS.first, DOWNLOAD_YEARS.last))

        def handle(request):
            requests.append(request)
            return httpx.Response(200, content=answer)

        client = NasaPowerClient(client_of(handle), cache=DataCache(tmp_path))
        weather = client.fetch_daily(45.6, -72.9)
        series = client.point_series(45.6, -72.9)
        assert weather.first_year == FARM_WEATHER_YEARS.first
        assert weather.last_year == FARM_WEATHER_YEARS.last
        assert "RH2M" in series["properties"]["parameter"]  # what water_use reads too
        params = requests[0].url.params
        assert params["start"] == f"{DOWNLOAD_YEARS.first}0101"
        assert set(params["parameters"].split(",")) >= {"T2M_MAX", "RH2M", "GWETROOT"}
        restarted = NasaPowerClient(client_of(handle), cache=DataCache(tmp_path))
        restarted.fetch_daily(45.6, -72.9)
        assert len(requests) == 1


# --- NEX-GDDP-CMIP6 through the NASA POWER projections --------------------------------------------


def projection_answer(scenario: str, warming_c: float) -> dict:
    """A projection that warms by `warming_c` per year after 2015, with constant rain."""
    days = calendar(SERVED_YEARS.first, SERVED_YEARS.last)
    tmax = {d: 20.0 + warming_c * (int(d[:4]) - 2015) for d in days}
    tmin = {d: 5.0 + warming_c * (int(d[:4]) - 2015) for d in days}
    rain = dict.fromkeys(days, 3.0)
    return {
        "properties": {
            "parameter": {
                "T2M_MAX": {scenario: tmax},
                "T2M_MIN": {scenario: tmin},
                "PRECTOTCORR": {scenario: rain},
            }
        }
    }


class TestProjections:
    def client(self, warming_c=0.05):
        requests = []

        def handle(request):
            requests.append(request)
            scenario = request.url.params["scenario"]
            return httpx.Response(200, content=json.dumps(projection_answer(scenario, warming_c)))

        return PowerProjectionClient(client_of(handle), cache=DataCache.in_memory()), requests

    def test_a_scenario_is_read_once_and_measured_from_its_first_twenty_years(self):
        client, requests = self.client()
        model = ProjectedScenario(client, 45.6, -72.9, "ssp245", "SSP2-4.5")
        simulation = model.simulate(2040, 2059)
        model.simulate(2030, 2049)
        assert len(requests) == 1
        assert requests[0].url.params["model"] == "ensemble"
        assert simulation.reference == REFERENCE_YEARS
        assert simulation.historical.first_year == REFERENCE_YEARS.first
        assert simulation.future.first_year == 2040 and simulation.future.last_year == 2059
        assert model.name == "NEX-GDDP-CMIP6 SSP2-4.5"

    def test_a_window_outside_the_served_years_is_refused(self):
        client, _ = self.client()
        model = ProjectedScenario(client, 45.6, -72.9, "ssp245", "SSP2-4.5")
        with pytest.raises(ProjectionUnavailableError):
            model.simulate(2095, 2114)

    def test_an_error_of_the_service_names_it(self):
        def handle(request):
            return httpx.Response(422, json={"detail": "x"})

        client = PowerProjectionClient(client_of(handle), cache=DataCache.in_memory())
        with pytest.raises(ProjectionUnavailableError, match="422"):
            client.daily(45.6, -72.9, "ssp245")

    def test_the_change_of_the_model_is_added_to_the_observed_weather_of_its_period(self):
        """A model 2 °C warmer in its window than in 2015–2034 makes the target 2 °C warmer than
        the recent NASA POWER years moved to 2015–2034 by their trend."""
        observed = demo_farm_weather()

        class Model:
            name = "test"

            def simulate(self, first_year, last_year):
                ref = DailyWeather.from_series(
                    2015, 2034, *(np.full(len(range(7305)), v) for v in (10.0, 0.0, 2.0))
                )
                future = DailyWeather.from_series(
                    first_year,
                    last_year,
                    *(
                        np.full(
                            len(DailyWeather.calendar_columns(first_year, last_year)["year"]), v
                        )
                        for v in (12.0, 2.0, 2.0)
                    ),
                )
                return ModelSimulation(ref, future, reference=YearRange(2015, 2034))

        projector = TargetClimateProjector(observed, 2026, models=[Model()])
        projected = projector.project(2047, 2050)
        target = projected.weathers[0][1]
        moved, _ = projector._trend.extend_to(2024.5)
        assert target.tmax.mean() == pytest.approx(moved.tmax.mean() + 2.0, abs=1e-9)
        assert target.rain.sum() == pytest.approx(moved.rain.sum())  # same rain: ratio 1


# --- The NASA POWER grid of the twins -------------------------------------------------------------


class TestPowerGrid:
    def test_the_box_is_ten_degrees_centred_on_the_half_degree_of_the_farm(self):
        assert grid_box(45.6077, -72.94) == (40.5, 50.5, -78.0, -68.0)
        assert grid_box(88.0, 0.0)[1] == 89.5

    def test_every_cell_gets_its_indicators_from_one_request_per_variable_and_year(self):
        requests = []

        def handle(request):
            requests.append(request)
            name = request.url.params["parameters"]
            year = int(request.url.params["start"][:4])
            value = {"T2M_MAX": 26.0, "T2M_MIN": 12.0, "PRECTOTCORR": 3.0}[name]
            features = [
                {
                    "geometry": {"coordinates": [lon, lat, 0]},
                    "properties": {
                        "parameter": {name: dict.fromkeys(calendar(year, year), value + lat - 45)}
                    },
                }
                for lat in (45.0, 45.5)
                for lon in (-73.125, -72.5)
            ]
            return httpx.Response(200, json={"features": features})

        period = YearRange(2023, 2024)
        grid = PowerGridClient(client_of(handle), cache=DataCache.in_memory(), period=period)
        cells = grid.cells(45.6, -72.9)
        assert len(requests) == 3 * 2  # 3 variables × 2 years
        assert len(cells) == 4 and all(cell.cultivated is None for cell in cells)
        warm, cold = (next(c for c in cells if c.lat == lat) for lat in (45.5, 45.0))
        assert warm.indicators.years.tolist() == [2023, 2024]
        assert warm.indicators.rows[0][0] > cold.indicators.rows[0][0]  # more degree-days
        grid.cells(45.6, -72.9)
        assert len(requests) == 6  # kept


# --- The crop maps of the twins -------------------------------------------------------------------


def u8_tiff(pixels: list[int], size: int) -> bytes:
    """An uncompressed grey 8-bit TIFF, one strip (what AAFC answers)."""
    tags = [(256, 3, 1, size), (257, 3, 1, size), (258, 3, 1, 8), (259, 3, 1, 1),
            (262, 3, 1, 1), (273, 4, 1, 0), (277, 3, 1, 1), (278, 3, 1, size),
            (279, 4, 1, size * size)]  # fmt: skip
    data_offset = 8 + 2 + 12 * len(tags) + 4
    header = bytearray(b"II") + struct.pack("<HI", 42, 8) + struct.pack("<H", len(tags))
    for tag, kind, count, value in tags:
        value = data_offset if tag == 273 else value
        header += struct.pack("<HHI", tag, kind, count)
        header += struct.pack("<HH", value, 0) if kind == 3 else struct.pack("<I", value)
    header += struct.pack("<I", 0)
    return bytes(header) + bytes(pixels)


def npy(bands: list[list[int]], size: int) -> bytes:
    out = io.BytesIO()
    np.save(out, np.array(bands, dtype=np.uint8).reshape(len(bands), size, size))
    return out.getvalue()


class FakeCropServices:
    """AAFC: maize and soybean in turn on 3/4 of the window; CDL: the same in the U.S. with a
    double crop of winter wheat and soybean; SoilGrids: a loam."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.http = client_of(self.handle)

    def handle(self, request):
        self.requests.append(request)
        n = GRID_SIZE * GRID_SIZE
        if "exportImage" in request.url.path:
            year = int(request.url.path.split("/")[-3])
            crop = 147 if year % 2 else 158
            return httpx.Response(200, content=u8_tiff([crop] * (3 * n // 4) + [34] * (n // 4), 64))
        if request.url.path.endswith("/stac/v1/search"):
            features = [
                {"id": f"cropland_{y}_1_2_90000", "assets": {"cropland": {}}}
                for y in range(2008, 2022)
            ]
            return httpx.Response(200, json={"features": features})
        if "/item/crop/" in request.url.path:
            item = request.url.params["item"]
            year = int(item.split("_")[1])
            crop = 26 if year % 2 else 1
            return httpx.Response(200, content=npy([[crop] * n, [255] * n], GRID_SIZE))
        if request.url.host == WCS_HOST:  # a loam
            maps = {"sand": 400, "clay": 200, "soc": 200, "phh2o": 65}
            return wcs_answer(lambda name, label: maps[name])(request)
        return httpx.Response(404)


def crop_maps(services: FakeCropServices) -> TwinCropMaps:
    cache = DataCache.in_memory()
    soils = SoilGridsClient(CONFIG[SOILGRIDS], services.http, cache)
    return TwinCropMaps(CONFIG[AAFC_CROPS], CONFIG[USDA_CDL], soils, services.http, cache)


def cell(lat: float, lon: float) -> GridCell:
    table = IndicatorTable(np.array([2011]), np.zeros((1, 5)))
    return GridCell(f"{lat}:{lon}", lat, lon, None, table)


class TestCropMaps:
    def test_a_point_is_a_field_when_it_is_a_known_crop_every_year(self):
        codes = [[147, 147, 34], [158, 26 * 0 + 158, 147]]
        assert sequences_of(codes, AAFC_TABLE) == {("mais", "soya"): 2}  # the town point is out
        assert sequences_of([[26], [1]], CDL_CROPS) == {("ble-automne", "soya-2e", "mais"): 1}

    def test_a_canadian_cell_is_read_on_the_aafc_inventory(self):
        services = FakeCropServices()
        maps = crop_maps(services)
        crops = maps.cell_crops(cell(46.5, -72.0))
        assert crops.provider == "AAFC" and crops.years == tuple(range(2017, 2025))
        assert crops.field_count == 3 * GRID_SIZE * GRID_SIZE // 4
        assert maps.cultivated([cell(46.5, -72.0)]) == [True]

    def test_an_american_cell_is_read_on_the_cdl_with_its_double_crops(self):
        services = FakeCropServices()
        crops = crop_maps(services).cell_crops(cell(42.0, -93.5))
        assert crops.provider == "USDA_CDL" and crops.years == tuple(range(2014, 2022))
        (sequence,) = crops.sequences
        assert "soya-2e" in sequence and "ble-automne" in sequence

    def test_the_evidence_keeps_the_twin_fields_of_a_comparable_soil(self):
        services = FakeCropServices()
        maps = crop_maps(services)
        twins = [Twin(cell(46.5, -72.0), 0.8)]
        same = maps.evidence_for(2027, 2030, twins, Soil(20, 40, 20, 6.5))
        assert same.crops == {"mais", "soya"}
        assert same.is_observed("mais", "soya") and same.is_observed("soya", "mais")
        assert same.precrop_value("soya", "mais") is None  # step 7: unknown, never invented
        other = maps.evidence_for(2027, 2030, twins, Soil(60, 10, 60, 8.0))
        assert other.crops == {"mais", "soya"}  # no comparable soil: the twins as they are

    def test_twins_all_beyond_sigma_two_still_say_what_grows(self):
        services = FakeCropServices()
        twins = [Twin(cell(46.5, -72.0), 2.6)]
        evidence = crop_maps(services).evidence_for(2047, 2050, twins, None)
        assert evidence.crops == {"mais", "soya"}
        assert evidence.sigma_mean == pytest.approx(2.6)

    def test_a_cell_without_enough_fields_is_not_cultivated(self):
        assert MIN_FIELDS > 0
        services = FakeCropServices()

        def town(request):
            if "exportImage" in request.url.path:
                return httpx.Response(200, content=u8_tiff([34] * GRID_SIZE**2, GRID_SIZE))
            return services.handle(request)

        services.http = client_of(town)
        assert crop_maps(services).cultivated([cell(46.5, -72.0)]) == [False]


# --- The twin search asks the crop maps only for its candidates -----------------------------------


class TestLazyCultivation:
    def test_only_the_closest_cells_are_checked_and_the_others_never(self):
        years = np.arange(2011, 2025)
        target = np.tile([1000.0, 250.0, 150.0, 5.0, -12.0], (len(years), 1))
        rng = np.random.default_rng(3)
        cells = []
        for i in range(40):
            rows = target + i * 10 + rng.normal(0, 5, target.shape)
            cells.append(GridCell(f"c{i}", 45.0, -73.0, None, IndicatorTable(years, rows)))
        asked: list[list[str]] = []

        def cultivation(batch):
            asked.append([c.id for c in batch])
            return [int(c.id[1:]) % 3 != 0 for c in batch]  # every third cell is a town

        finder = ClimateTwinFinder(cells, twins_per_target=5, cultivation=cultivation)
        twins = finder.closest_cells(target)
        assert len(twins) == 5 and all(int(t.cell.id[1:]) % 3 for t in twins)
        checked = {cell_id for batch in asked for cell_id in batch}
        assert len(checked) < 20  # the far cells are never read
        finder.closest_cells(target)
        assert len(asked) == len({tuple(b) for b in asked})  # nothing asked twice

    def test_an_unknown_cell_needs_a_check(self):
        table = IndicatorTable(np.array([2011]), np.zeros((1, 5)))
        with pytest.raises(ValueError):
            ClimateTwinFinder([GridCell("c", 0, 0, None, table)])


# --- The measures of a section --------------------------------------------------------------------


class FakeSectionServices:
    def __init__(self, soil_value=400):
        self.requests: list[httpx.Request] = []
        self.soil_value = soil_value
        self.http = client_of(self.handle)

    def handle(self, request):
        self.requests.append(request)
        if request.url.host == "api.open-meteo.com":
            lats = [float(v) for v in request.url.params["latitude"].split(",")]
            return httpx.Response(
                200, json={"elevation": [100 - 0.03 * (lat - 45.6) * 111_195 for lat in lats]}
            )
        if request.url.path.endswith("/mosaic/register"):
            return httpx.Response(200, json={"searchid": "s"})
        if "/mosaic/s/point/" in request.url.path:
            values = [
                [f"x/MOD13Q1.A2025{day:03d}.h12v04.061", [8000 if 130 < day < 280 else 500], []]
                for day in range(1, 366, 8)
            ]
            return httpx.Response(200, json={"values": values})
        if request.url.host == WCS_HOST:
            maps = {"sand": self.soil_value, "clay": 200, "soc": 180, "phh2o": 62}
            return wcs_answer(lambda name, label: maps[name])(request)
        return httpx.Response(404)


def field_source(services: FakeSectionServices) -> RemoteFieldData:
    return RemoteFieldData(
        CONFIG, services.http, DataCache.in_memory(), today=lambda: date(2026, 11, 15)
    )


class TestSectionMeasures:
    def test_heavy_rain_days_and_bare_soil_days(self):
        weather = demo_farm_weather()
        assert heavy_rain_days(weather) == pytest.approx(
            np.count_nonzero(weather.between(2005, 2024).rain >= 25) / 20
        )
        series = [(f"2025-{m:02d}-01", 0.1 if m < 5 else 0.7) for m in range(1, 13)]
        assert bare_soil_days(series) == pytest.approx(365 * 4 / 12)
        with pytest.raises(ValueError):
            bare_soil_days(series[:3])

    def test_every_measure_of_a_drawn_section_comes_from_its_service(self):
        services = FakeSectionServices()
        shape = square_around(45.6, -72.9, 300)
        section = SectionPlace("A", 45.6, -72.9, shape.ring)
        data = field_source(services).field_data(section, None, demo_farm_weather())
        assert data.measures.slope_pct == pytest.approx(3.0, abs=0.05)
        soil = data.soil
        assert (soil.clay_pct, soil.sand_pct, soil.organic_carbon, soil.ph) == pytest.approx(
            (20, 40, 18, 6.2)
        )
        assert "SoilGrids" in data.soil_source and "contour" in data.measures_source
        assert 150 < data.measures.bare_soil_days < 260

    def test_a_soil_test_replaces_soilgrids_and_no_soil_asks_for_one(self):
        services = FakeSectionServices(soil_value=None)
        source = field_source(services)
        section = SectionPlace("B", 45.6, -72.9)
        test = Soil(30, 30, 25, 6.8)
        assert source.field_data(section, test, demo_farm_weather()).soil == test
        from field_shift.algorithm.sources.field_data import FieldDataUnavailableError

        with pytest.raises(FieldDataUnavailableError, match="analyse de sol"):
            source.field_data(section, None, demo_farm_weather())

    def test_no_soil_is_an_error_of_soilgrids(self):
        services = FakeSectionServices(soil_value=None)
        soils = SoilGridsClient(CONFIG[SOILGRIDS], services.http, DataCache.in_memory())
        with pytest.raises(NoSoilError):
            soils.topsoil_soil(45.6, -72.9)
