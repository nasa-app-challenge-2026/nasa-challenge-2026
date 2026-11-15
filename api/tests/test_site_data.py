"""The data of a section: its outline, its slope, the models (Ksat, K, R), the statistics of the
forcing, the readers of each data service and their configuration. No network: the services are
faked with httpx.MockTransport."""

from __future__ import annotations

import json
from datetime import date

import httpx
import pytest

from field_shift.algorithm.soil_protection.forcing import (
    SeriesError,
    evapotranspiration_ratio,
    last_growing_season,
    season_label,
    storm_intensity,
    two_month_windows,
)
from field_shift.algorithm.soil_protection.pedotransfer import saxton_rawls_ksat
from field_shift.algorithm.soil_protection.site_conditions import (
    MissingSiteDataError,
    SiteReading,
    site_from_readings,
)
from field_shift.algorithm.soil_protection.site_estimates import with_estimates
from field_shift.algorithm.terrain.section_shape import SectionShape, ShapeError
from field_shift.algorithm.terrain.slope import fitted_plane, terrain_of, terrain_sample
from field_shift.data_access.data_source_config import (
    DATA_SOURCES,
    DataSourceConfig,
    DataSourceConfigError,
)
from field_shift.data_access.site_data import RemoteSiteData, SiteDataUnavailableError
from tests.helpers.site_stub import TEST_VALUES, square

TODAY = date(2026, 11, 14)


def shape_of(polygon: dict) -> SectionShape:
    return SectionShape.from_coordinates(polygon["coordinates"][0])


class TestSectionShape:
    def test_area_and_centre_of_a_square(self):
        shape = shape_of(square(45.5, -73.0, 200))
        assert shape.area_ha == pytest.approx(4, rel=1e-3)
        lon, lat = shape.centroid
        assert (lat, lon) == pytest.approx((45.5, -73.0), abs=1e-7)

    def test_the_centre_of_an_l_shape_is_its_centre_of_mass(self):
        # An L of three unit squares (0,0)-(2,1) + (0,1)-(1,2), in thousandths of a degree.
        ring = [[0, 0], [2, 0], [2, 1], [1, 1], [1, 2], [0, 2], [0, 0]]
        shape = SectionShape.from_coordinates([[x / 1000, y / 1000] for x, y in ring])
        lon, lat = shape.centroid
        assert (lon * 1000, lat * 1000) == pytest.approx((5 / 6, 5 / 6), abs=1e-3)

    def test_inside_and_outside(self):
        shape = shape_of(square(side_m=100))
        assert shape.contains(0, 0) and not shape.contains(80, 0)

    @pytest.mark.parametrize(
        "ring, message",
        [
            ([[0, 0], [1, 0], [0, 0]], "au moins 4"),
            ([[0, 0], [1, 0], [1, 1], [0, 1]], "fermé"),
            ([[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]], "se croise"),
            ([[0, 0], [1, 0], [2, 0], [0, 0]], "surface"),
            ([[0, 0], [200, 0], [0, 1], [0, 0]], "coordonnées valides"),
            ([[179, 0], [-179, 0], [-179, 1], [179, 0]], "antiméridien"),
        ],
    )
    def test_an_unusable_outline_is_refused(self, ring, message):
        with pytest.raises(ShapeError, match=message):
            SectionShape.from_coordinates(ring)


class TestSlope:
    def test_a_plane_gives_its_slope_and_the_water_runs_down(self):
        points = [(x, y) for x in (0, 50, 100) for y in (0, 50, 100)]
        elevations = [100 - 0.05 * x for x, _ in points]  # 5 % down towards the east
        slope, downslope = fitted_plane(points, elevations)
        assert slope == pytest.approx(5)
        assert downslope == pytest.approx((1, 0))

    def test_flat_ground(self):
        points = [(0, 0), (10, 0), (0, 10), (10, 10)]
        assert fitted_plane(points, [34, 34, 34, 34])[0] == 0

    def test_a_large_section_is_sampled_inside_a_small_one_around(self):
        large = terrain_sample(shape_of(square(side_m=1000)))
        small = terrain_sample(shape_of(square(side_m=40)))
        assert large.inside and len(large.local) == 81
        assert not small.inside and len(small.local) == 81  # the 270 m window around it

    def test_the_slope_length_is_the_length_of_the_section_along_the_slope(self):
        shape = shape_of(square(side_m=400))
        sample = terrain_sample(shape)
        elevations = [50 + 0.03 * y for _, y in sample.local]  # 3 % down towards the south
        terrain = terrain_of(shape, sample, elevations)
        assert terrain.slope_pct == pytest.approx(3)
        assert terrain.slope_length_m == pytest.approx(400, rel=1e-3)


class TestModels:
    @pytest.mark.parametrize(
        "sand, clay, low, high",
        [(88, 5, 80, 130), (40, 20, 10, 25), (25, 50, 0.5, 5)],  # sand, loam, clay
    )
    def test_ksat_of_saxton_and_rawls_has_the_order_of_their_table(self, sand, clay, low, high):
        assert low < saxton_rawls_ksat(sand, clay, 2.5).ksat_mm_h < high

    def test_the_organic_matter_is_bounded_to_the_range_of_the_equations(self):
        rich = saxton_rawls_ksat(33, 33, 12)
        assert rich.organic_matter_bounded
        assert rich.ksat_mm_h == saxton_rawls_ksat(33, 33, 8).ksat_mm_h

    def test_the_estimates_say_what_they_were_computed_from(self):
        readings = [SiteReading(k, v, "test") for k, v in TEST_VALUES.items()]
        estimated = {r.key: r for r in with_estimates(readings)[len(readings) :]}
        assert set(estimated) == {"ksat_mm_h", "k_factor", "r_factor"}
        assert "1000 mm, test" in estimated["r_factor"].method
        assert site_from_readings(with_estimates(readings)).r_factor == pytest.approx(3473.8, 0.01)

    def test_a_missing_input_of_a_model_is_an_error(self):
        readings = [SiteReading(k, v, "test") for k, v in TEST_VALUES.items() if k != "clay_pct"]
        with pytest.raises(MissingSiteDataError, match="Argile"):
            with_estimates(readings)

    def test_a_missing_variable_is_an_error_not_a_default(self):
        with pytest.raises(MissingSiteDataError, match="Pente"):
            site_from_readings([SiteReading("sand_pct", 40, "test")])


class TestForcing:
    def test_the_last_season_over_a_month_ago(self):
        assert last_growing_season(45.5, TODAY)[0] == (2026, 5)
        assert last_growing_season(45.5, date(2026, 10, 15))[0] == (2025, 5)
        south = last_growing_season(-30, TODAY)
        assert south[0] == (2025, 11) and south[-1] == (2026, 3)
        assert season_label(last_growing_season(45.5, TODAY)) == "mai–sept. 2026"

    def test_windows_of_two_months(self):
        windows = two_month_windows(last_growing_season(45.5, TODAY))
        assert windows == [
            (date(2026, 5, 1), date(2026, 6, 30)),
            (date(2026, 7, 1), date(2026, 8, 31)),
            (date(2026, 9, 1), date(2026, 9, 30)),
        ]

    def test_the_storm_is_the_mean_of_the_annual_maxima(self):
        series = {}
        for year, peak in zip(range(2016, 2022), (10, 20, 30, 40, 50, 60), strict=True):
            for hour in range(8760):
                series[f"{year}{hour:06d}"] = peak if hour == 100 else 0.1
        assert storm_intensity(series).intensity_mm_h == 35

    def test_too_few_complete_years_is_an_error(self):
        series = {f"2020{hour:06d}": 1.0 for hour in range(8760)}
        with pytest.raises(SeriesError, match="1 année"):
            storm_intensity(series)

    def test_the_ratio_of_evapotranspiration(self):
        assert evapotranspiration_ratio({"a": 2, "b": 3}, {"a": 4, "b": 6, "c": 9}) == 0.5
        with pytest.raises(SeriesError):
            evapotranspiration_ratio({}, {"a": 1})


# --- The readers, on fake services ----------------------------------------------------------------

SOILGRIDS_ANSWER = {
    "properties": {
        "layers": [
            {
                "name": name,
                "unit_measure": {"d_factor": 10, "target_units": unit},
                "depths": [
                    {"label": "0-5cm", "values": {"mean": top}},
                    {"label": "5-15cm", "values": {"mean": below}},
                ],
            }
            for name, unit, top, below in (
                ("sand", "%", 340, 310),
                ("clay", "%", 330, 360),
                ("soc", "g/kg", 600, 450),
            )
        ]
    }
}


def climatology_answer() -> dict:
    wetness = dict.fromkeys(
        ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 0.8
    )
    wetness.update(MAY=0.6, JUN=0.6, JUL=0.6, AUG=0.6, SEP=0.6, ANN=0.7)
    return {"properties": {"parameter": {"PRECTOTCORR": {"ANN": 3.0}, "GWETTOP": wetness}}}


def hourly_answer() -> dict:
    series = {}
    for year in range(2016, 2026):
        for hour in range(8760):
            series[f"{year}{hour:06d}"] = 12.0 if hour == 5 else 0.0
    return {"properties": {"parameter": {"PRECTOTCORR": series}}}


def modis_answer(request: httpx.Request) -> dict:
    band = request.url.params["band"]
    raw = {"250m_16_days_NDVI": 7000, "ET_500m": 300, "PET_500m": 600}[band]
    return {
        "subset": [
            {"calendar_date": f"{request.url.params['startDate']}-{i}", "data": [raw]}
            for i in range(3)
        ]
        + [{"calendar_date": "fill", "data": [-3000 if band.startswith("250m") else 32767]}]
    }


class FakeServices:
    """The six services, answering from memory; `down` names hosts that answer 503."""

    def __init__(self, down: tuple[str, ...] = ()) -> None:
        self.down = down
        self.requests: list[httpx.Request] = []
        self.http = httpx.Client(transport=httpx.MockTransport(self.handle))

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        host, path = request.url.host, request.url.path
        if host in self.down:
            return httpx.Response(503)
        if host == "rest.isric.org":
            return httpx.Response(200, json=SOILGRIDS_ANSWER)
        if host == "api.open-meteo.com":
            lats = [float(v) for v in request.url.params["latitude"].split(",")]
            # 2 % down towards the north: elevation falls 2 m per 100 m of latitude.
            return httpx.Response(
                200, json={"elevation": [100 - 0.02 * (lat - 45.5) * 111_195 for lat in lats]}
            )
        if path.endswith("/climatology/point"):
            return httpx.Response(200, json=climatology_answer())
        if path.endswith("/hourly/point"):
            return httpx.Response(200, content=json.dumps(hourly_answer()))
        if host == "modis.ornl.gov":
            return httpx.Response(200, json=modis_answer(request))
        return httpx.Response(404)


ALL_KEYS = [
    "slope_pct",
    "slope_length_m",
    "sand_pct",
    "clay_pct",
    "organic_matter_pct",
    "ndvi",
    "root_activity",
    "annual_rain_mm",
    "storm_intensity_mm_h",
    "soil_saturation",
]


def provider(services: FakeServices) -> RemoteSiteData:
    return RemoteSiteData(DataSourceConfig.load({}), services.http, today=lambda: TODAY)


class TestReaders:
    def test_every_variable_is_read_from_its_service(self):
        services = FakeServices()
        readings = {
            r.key: r for r in provider(services).site_readings(shape_of(square()), ALL_KEYS)
        }
        value = {key: reading.value for key, reading in readings.items()}
        assert value["sand_pct"] == pytest.approx((34 * 5 + 31 * 10) / 15)
        assert value["clay_pct"] == pytest.approx((33 * 5 + 36 * 10) / 15)
        assert value["organic_matter_pct"] == pytest.approx((60 * 5 + 45 * 10) / 15 / 10 * 1.724)
        assert value["slope_pct"] == pytest.approx(2, rel=1e-3)
        assert value["slope_length_m"] == pytest.approx(300, rel=1e-3)
        assert value["annual_rain_mm"] == pytest.approx(3 * 365.25)
        assert value["soil_saturation"] == pytest.approx(0.6)  # May to September
        assert value["storm_intensity_mm_h"] == 12
        assert value["ndvi"] == pytest.approx(0.7)  # the fill value is left out
        assert value["root_activity"] == pytest.approx(0.5)
        assert readings["sand_pct"].origin == "SoilGrids 2.0 (ISRIC)"
        assert readings["root_activity"].origin == "MODIS MOD16A2 (NASA, ORNL DAAC)"
        assert "Van Bemmelen" in readings["organic_matter_pct"].method
        assert "2016 à 2025" in readings["storm_intensity_mm_h"].method

    def test_the_requests_are_made_at_the_centre_of_the_section(self):
        services = FakeServices()
        provider(services).site_readings(shape_of(square(46.0, -72.0)), ["sand_pct", "ndvi"])
        soil = next(r for r in services.requests if r.url.host == "rest.isric.org")
        assert soil.url.params["lat"] == "46.000000" and soil.url.params["lon"] == "-72.000000"
        modis = [r for r in services.requests if r.url.host == "modis.ornl.gov"]
        assert [r.url.params["startDate"] for r in modis] == ["A2026121", "A2026182", "A2026244"]

    def test_only_the_services_of_the_needed_variables_are_called(self):
        services = FakeServices()
        provider(services).site_readings(shape_of(square()), ["sand_pct", "clay_pct"])
        assert {r.url.host for r in services.requests} == {"rest.isric.org"}

    def test_a_place_already_read_is_not_read_again(self):
        services = FakeServices()
        reader = provider(services)
        reader.site_readings(shape_of(square()), ["sand_pct"])
        reader.site_readings(shape_of(square(45.50001, -73.00001)), ["sand_pct"])  # ~1 m away
        assert len(services.requests) == 1

    def test_a_failed_service_fails_the_section_and_every_failure_is_named(self):
        services = FakeServices(down=("rest.isric.org", "modis.ornl.gov"))
        with pytest.raises(SiteDataUnavailableError) as raised:
            provider(services).site_readings(shape_of(square()), ALL_KEYS)
        datasets = sorted(failure.dataset for failure in raised.value.failures)
        assert datasets == ["MODIS (NASA, ORNL DAAC)"] * 2 + ["SoilGrids 2.0 (ISRIC)"]
        assert all("503" in failure.reason for failure in raised.value.failures)

    def test_a_failure_is_not_remembered(self):
        services = FakeServices(down=("rest.isric.org",))
        reader = provider(services)
        for _ in range(2):
            with pytest.raises(SiteDataUnavailableError):
                reader.site_readings(shape_of(square()), ["sand_pct"])
        assert len(services.requests) == 2

    def test_no_soil_at_the_point_is_an_error(self):
        answer = json.loads(json.dumps(SOILGRIDS_ANSWER))
        answer["properties"]["layers"][0]["depths"][0]["values"]["mean"] = None

        def handle(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=answer)

        http = httpx.Client(transport=httpx.MockTransport(handle))
        reader = RemoteSiteData(DataSourceConfig.load({}), http, today=lambda: TODAY)
        with pytest.raises(SiteDataUnavailableError, match="pas de donnée de sol"):
            reader.site_readings(shape_of(square()), ["sand_pct"])


class TestConfiguration:
    def test_every_service_has_a_default_address_and_a_reference(self):
        config = DataSourceConfig.load({})
        assert all(source.url.startswith("https://") for source in config.sources.values())
        assert all(source.reference for source in DATA_SOURCES)
        assert config.power_daily_url == "https://power.larc.nasa.gov/api/temporal/daily/point"

    def test_an_address_comes_from_a_file_and_the_environment_wins(self, tmp_path):
        file = tmp_path / "sources.json"
        file.write_text(
            json.dumps(
                {
                    "soilgrids": "https://file.test/soilgrids",
                    "modis": {"url": "https://file.test/modis", "headers": {"X-Key": "secret"}},
                }
            ),
            encoding="utf-8",
        )
        environment = {
            "FIELD_SHIFT_DATA_SOURCES": str(file),
            "FIELD_SHIFT_URL_SOILGRIDS": "https://env.test/soilgrids",
        }
        config = DataSourceConfig.load(environment)
        assert config["soilgrids"].url == "https://env.test/soilgrids"
        assert config["modis"].url == "https://file.test/modis"
        assert config["modis"].headers == {"X-Key": "secret"}

    @pytest.mark.parametrize(
        "content, message",
        [
            ('{"pente": "https://x.test"}', "inconnue"),
            ("pas du json", "n’a pas pu être lu"),
            ('{"soilgrids": ""}', "ne peut pas être coupée"),
            ("[]", "objet JSON"),
        ],
    )
    def test_a_wrong_file_is_refused_when_the_server_starts(self, tmp_path, content, message):
        file = tmp_path / "sources.json"
        file.write_text(content, encoding="utf-8")
        with pytest.raises(DataSourceConfigError, match=message):
            DataSourceConfig.load({"FIELD_SHIFT_DATA_SOURCES": str(file)})

    def test_a_service_cannot_be_switched_off(self):
        with pytest.raises(DataSourceConfigError, match="ne peut pas être coupée"):
            DataSourceConfig.load({"FIELD_SHIFT_URL_MODIS": ""})

    def test_a_missing_file_is_refused(self, tmp_path):
        with pytest.raises(DataSourceConfigError, match="introuvable"):
            DataSourceConfig.load({"FIELD_SHIFT_DATA_SOURCES": str(tmp_path / "absent.json")})
