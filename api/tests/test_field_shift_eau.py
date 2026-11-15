"""The adapter between the pipeline and `water_use` (data_access/field_shift_eau.py), without the
network: synthetic weather and soil of `water_use.demo`, and simulated answers of the data bases
(the ones of tests/water_use/test_2b_chaine_complete.py).
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

import field_shift.algorithm.chain.chain_search as chain_search
import field_shift.data_access.field_shift_eau as eau
import water_use.sol as sol_module
from field_shift.algorithm.chain.chain_step import ChainStep
from field_shift.algorithm.timeline import month_time
from field_shift.algorithm.weather.daily_weather import DailyWeather
from field_shift.api.app import create_app
from field_shift.api.settings import Settings
from field_shift.contract.farm_input import FarmInput
from field_shift.data_access.field_shift_eau import (
    WATER_USE_CODES,
    WaterDataUnavailableError,
    WaterUseModel,
    meteo_of_weather,
    note_eau,
    pression_eau,
    rotation_of_chain,
    water_use_code,
    with_component,
    with_spin_up_year,
)
from field_shift.reference.crops import CROP_SHEETS
from field_shift.services.plan_service import PlanService
from tests.helpers.demo_field_data import DemoFieldDataSource
from tests.helpers.example_plans import (
    ExampleWeatherProvider,
    example_plan_service,
    example_water_model,
)
from tests.helpers.reference_place import ReferencePlaceData
from tests.water_use.test_2b_chaine_complete import api_simulees  # noqa: F401  (a fixture)
from water_use.demo import meteo_demo, sol_demo
from water_use.et0 import et0_meteo
from water_use.notes import evaluer_rotation
from water_use.reseau import ErreurDonnees
from water_use.rotation import lire_rotation

EXAMPLES = Path(__file__).resolve().parents[1] / "exemples"
FIRST_YEAR, LAST_YEAR = 2005, 2024
PLACE = (45.55, -72.98)
READABLE = ("demande_mm_an", "manque_mm_an", "irrigation_mm_an", "pluie_gardee_pct")


def example(name: str) -> dict:
    return json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))


def demo_weather(climate: str):
    """Synthetic weather starting one year before the scored years (the soil fills up)."""
    return meteo_demo(climate, FIRST_YEAR - 1, LAST_YEAR)


def note(rotation: dict, climate: str, irrigated: bool = False) -> dict:
    return note_eau(
        rotation, demo_weather(climate), *PLACE, irrigated, FIRST_YEAR, LAST_YEAR, sol=sol_demo()
    )


def step(sheet: str, year: int, sowing: float, harvest_year: int, harvest: float, position: int):
    return ChainStep(
        sheet,
        month_time.of(year, sowing),
        month_time.of(harvest_year, harvest),
        position,
        position,
    )


START = month_time.of(2026, 9.5)  # the field is free in mid-October 2026
MAIZE_MAIZE = [step("mais", 2027, 4.5, 2027, 9.6, 0), step("mais", 2028, 4.5, 2028, 9.6, 1)]
SOYBEAN_WHEAT = [
    step("soya", 2027, 4.75, 2027, 9.2, 0),
    step("ble-automne", 2027, 9.3, 2028, 6.65, 1),
]


def chain_note(chain, climate: str = "sec") -> float:
    return note(rotation_of_chain(chain, START, START + 24), climate)["note"]


class TestNoteEau:
    @pytest.mark.parametrize("climate", ["humide", "sec"])
    def test_the_score_and_its_parts_are_between_0_and_1(self, climate):
        for path in sorted(EXAMPLES.glob("*.json")):
            result = note(json.loads(path.read_text(encoding="utf-8")), climate)
            for key in ("note", "A", "B", "C", "D"):
                assert 0 <= result[key] <= 1, (path.name, key)
            assert all(np.isfinite(result[key]) and result[key] >= 0 for key in READABLE)
            assert isinstance(result["alertes"], list)

    def test_two_different_chains_get_two_different_scores(self):
        # No fixed value per crop any more: the dates and the order of the chain count.
        assert chain_note(MAIZE_MAIZE) != chain_note(SOYBEAN_WHEAT)
        later = [step("mais", 2027, 5.4, 2027, 10.2, 0), step("mais", 2028, 5.4, 2028, 10.2, 1)]
        assert chain_note(MAIZE_MAIZE) != chain_note(later)

    def test_sorghum_then_winter_wheat_beats_continuous_maize_in_a_dry_climate(self):
        assert (
            note(example("sorgho_ble_hiver"), "sec")["note"]
            > (note(example("mais_continu"), "sec")["note"])
        )

    def test_the_scores_are_exactly_those_of_water_use(self):
        # Same weather, same soil, same rotations: the adapter adds nothing to the algorithm.
        for climate in ("humide", "sec"):
            weather, soil = demo_weather(climate), sol_demo()
            et0, _ = et0_meteo(weather)
            for path in sorted(EXAMPLES.glob("*.json")):
                direct = evaluer_rotation(
                    lire_rotation(path), weather, soil, FIRST_YEAR, LAST_YEAR, False, et0
                )
                ours = note_eau(
                    json.loads(path.read_text(encoding="utf-8")),
                    weather,
                    *PLACE,
                    False,
                    FIRST_YEAR,
                    LAST_YEAR,
                    sol=soil,
                )
                assert ours["note"] == direct.note
                assert (ours["A"], ours["B"], ours["C"], ours["D"]) == (
                    direct.A,
                    direct.B,
                    direct.C,
                    direct.D,
                )

    def test_irrigation_is_counted_only_for_an_irrigated_farm(self):
        rotation = example("mais_continu")
        assert note(rotation, "sec")["irrigation_mm_an"] == 0
        irrigated = note(rotation, "sec", irrigated=True)
        assert irrigated["irrigation_mm_an"] > 100
        assert irrigated["manque_mm_an"] == pytest.approx(0, abs=1)

    def test_the_weather_must_start_one_year_before_the_scored_years(self):
        weather = meteo_demo("humide", FIRST_YEAR, LAST_YEAR)
        with pytest.raises(ValueError, match="un an avant"):
            note_eau(
                example("mais_soya"), weather, *PLACE, False, FIRST_YEAR, LAST_YEAR, sol=sol_demo()
            )

    def test_soil_and_slope_of_the_place_are_read_when_not_given(self, api_simulees, monkeypatch):  # noqa: F811
        monkeypatch.setattr(eau, "_soils", {})
        result = note_eau(
            example("mais_soya"), demo_weather("humide"), *PLACE, False, FIRST_YEAR, LAST_YEAR
        )
        assert 0 <= result["note"] <= 1
        assert eau.soil_of_place(*PLACE).pente == pytest.approx(0.02, abs=0.002)
        calls = len(api_simulees)
        eau.soil_of_place(*PLACE)
        assert len(api_simulees) == calls  # read once per place

    def test_a_slope_that_cannot_be_read_does_not_stop_the_score(self, api_simulees, monkeypatch):  # noqa: F811
        def no_srtm(*args, **kwargs):
            raise ErreurDonnees("SRTM en panne")

        monkeypatch.setattr(eau, "_soils", {})
        monkeypatch.setattr(eau, "terrain_srtm", no_srtm)
        assert eau.soil_of_place(*PLACE).pente is None

    def test_no_soil_at_all_is_an_error_that_names_the_soil(self, monkeypatch):
        def no_soil(*args, **kwargs):
            raise ErreurDonnees("SoilGrids en maintenance")

        monkeypatch.setattr(eau, "_soils", {})
        monkeypatch.setattr(eau, "trouver_sol", no_soil)
        with pytest.raises(WaterDataUnavailableError, match="sol"):
            eau.soil_of_place(*PLACE)


class TestPressionEau:
    def pressure(self, climate: str, **inputs) -> dict:
        weather = demo_weather(climate)
        et0, _ = et0_meteo(weather)
        return pression_eau(weather, et0, FIRST_YEAR, LAST_YEAR, **inputs)

    def test_the_pressure_is_higher_in_a_dry_climate(self):
        dry, wet = self.pressure("sec"), self.pressure("humide")
        assert 0 <= wet["pression"] < dry["pression"] <= 1
        assert dry["classe"] == "semi-aride"

    def test_missing_sources_are_named_and_the_others_share_their_weight(self):
        alone = self.pressure("sec")
        assert alone["manquantes"] == ["nappes", "stress_mesure"]
        full = self.pressure("sec", nappes_percentile=10, esi=-2, secheresse_sol=1)
        assert full["manquantes"] == []
        assert full["pression"] > alone["pression"]
        assert (
            self.pressure("sec", nappes_percentile=90, esi=1, secheresse_sol=0)["pression"]
            < (alone["pression"])
        )

    def test_replacing_a_component_weighs_the_pressure_as_water_use_does(self):
        weather = demo_weather("sec")
        et0, _ = et0_meteo(weather)
        result = pression_eau(weather, et0, FIRST_YEAR, LAST_YEAR, nappes_percentile=30)
        same = with_component(result, "pluie_ete", result["composantes"]["pluie_ete"])
        assert same["pression"] == pytest.approx(result["pression"], abs=1e-3)
        assert with_component(result, "pluie_ete", 1.0)["pression"] > result["pression"]
        added = with_component(pression_eau(weather, et0, FIRST_YEAR, LAST_YEAR), "nappes", 0.5)
        assert "nappes" not in added["manquantes"]

    def test_a_base_that_fails_is_left_out_and_named(self, monkeypatch):
        def broken(*args, **kwargs):
            raise ErreurDonnees("service en panne")

        monkeypatch.setattr(eau, "nappes_usgs", broken)
        monkeypatch.setattr(eau.earthdata, "identifiants", lambda: ("moi", "secret"))
        monkeypatch.setattr(eau.earthdata, "smap_percentile", broken)
        monkeypatch.setattr(eau.earthdata, "ecostress_esi", broken)
        inputs, sources = eau.pressure_inputs(*PLACE, None, FIRST_YEAR, LAST_YEAR)
        assert inputs == {"nappes_percentile": None, "esi": None, "secheresse_sol": None}
        assert all("non mesuré" in sources[key] for key in ("nappes", "esi", "sol_sec"))

    def test_smap_and_ecostress_are_used_with_an_earthdata_account(self, monkeypatch):
        monkeypatch.setattr(eau, "nappes_usgs", lambda *a, **k: None)
        monkeypatch.setattr(eau.earthdata, "identifiants", lambda: ("moi", "secret"))
        monkeypatch.setattr(
            eau.earthdata, "smap_percentile", lambda *a, **k: {"percentile": 10.0, "source": "SMAP"}
        )
        monkeypatch.setattr(
            eau.earthdata,
            "ecostress_esi",
            lambda *a, **k: {"anomalie": -1.5, "source": "ECOSTRESS"},
        )
        inputs, sources = eau.pressure_inputs(*PLACE, None, FIRST_YEAR, LAST_YEAR)
        assert inputs["secheresse_sol"] == 1.0  # 10th percentile: fully dry
        assert inputs["esi"] == -1.5
        assert sources["sol_sec"].startswith("SMAP")


class TestChainToRotation:
    def test_a_chain_becomes_a_rotation_of_water_use(self):
        chain = [
            *SOYBEAN_WHEAT,
            ChainStep("jachere", None, month_time.of(2028, 6.65), 2, 2),
            step("luzerne-2", 2029, 4.0, 2031, 8.75, 3),
        ]
        cover = ChainStep("seigle-couvert", month_time.of(2026, 9.85), month_time.of(2027, 4.3))
        rotation = rotation_of_chain([*chain, cover], START, START + 60, name="test")
        assert (rotation["nom"], rotation["duree_ans"]) == ("test", 5)
        assert rotation["travail_sol"] == "conventionnel"
        assert rotation["cultures"] == [
            {"culture": "seigle_couvert", "annee": 1, "semis": "10-26", "fin": "05-10"},
            {"culture": "soya", "annee": 2, "semis": "05-23", "fin": "10-07"},
            {"culture": "ble_hiver", "annee": 2, "semis": "10-10", "fin": "07-20"},
            {"culture": "luzerne", "annee": 4, "semis": "05-01", "fin": "09-23", "duree_annees": 3},
        ]
        assert 0 <= note(rotation, "humide")["note"] <= 1

    def test_a_crop_ends_the_day_before_the_next_one_is_sown(self):
        cover = ChainStep("seigle-couvert", month_time.of(2026, 9.85), month_time.of(2027, 4.5))
        maize = step("mais", 2027, 4.5, 2027, 9.6, 0)
        crops = rotation_of_chain([cover, maize], START, START + 12)["cultures"]
        assert [(c["culture"], c["semis"], c["fin"]) for c in crops] == [
            ("seigle_couvert", "10-26", "05-15"),
            ("mais", "05-16", "10-19"),
        ]

    def test_every_sheet_of_the_plan_has_a_water_use_code_or_is_bare_soil(self):
        for sheet in CROP_SHEETS:
            assert sheet.id in WATER_USE_CODES or sheet.id in eau.BARE_SOIL_IDS, sheet.id

    def test_a_crop_without_a_code_is_refused_clearly(self):
        with pytest.raises(ValueError, match=r"tomate.*pas de fiche eau"):
            water_use_code("tomate")
        with pytest.raises(ValueError, match="tomate"):
            rotation_of_chain([step("tomate", 2027, 4.5, 2027, 8.5, 0)], START, START + 12)

    def test_a_chain_with_nothing_sown_has_no_score(self):
        fallow = ChainStep("jachere", None, START, 0, 0)
        with pytest.raises(ValueError, match="aucune culture"):
            rotation_of_chain([fallow], START, START + 12)


class TestWeatherOfACycle:
    weather = DailyWeather.from_series(
        2004,
        2005,
        tmax=np.full(731, 20.0),
        tmin=np.full(731, 8.0),
        rain=np.full(731, 2.0),
    )

    def test_without_measures_only_temperatures_and_rain_are_known(self):
        meteo = meteo_of_weather(self.weather, *PLACE)
        assert meteo.dates.dtype == np.dtype("datetime64[D]")
        assert str(meteo.dates[0]) == "2004-01-01" and str(meteo.dates[-1]) == "2005-12-31"
        assert np.isnan(meteo.rh).all() and np.isnan(meteo.u2).all() and np.isnan(meteo.rs).all()
        et0, method = et0_meteo(meteo)
        assert "Hargreaves" in method and np.isfinite(et0).all()

    def test_humidity_wind_and_radiation_are_those_measured_on_the_same_days(self):
        observed = meteo_demo("humide", 2000, 2010)
        meteo = meteo_of_weather(self.weather, *PLACE, observed)
        same_days = (observed.annees >= 2004) & (observed.annees <= 2005)
        assert np.array_equal(meteo.rh, observed.rh[same_days])
        assert np.array_equal(meteo.rs, observed.rs[same_days])
        assert meteo.altitude == observed.altitude
        assert et0_meteo(meteo)[1] == "Penman-Monteith FAO-56"
        assert (meteo.tmax == 20.0).all()  # the temperatures stay those of the cycle

    def test_measures_that_do_not_cover_the_cycle_are_not_used(self):
        meteo = meteo_of_weather(self.weather, *PLACE, meteo_demo("humide", 2005, 2010))
        assert np.isnan(meteo.rh).all()

    def test_the_first_year_is_played_once_before_the_cycle_to_fill_the_soil(self):
        tmax = np.concatenate((np.arange(365, dtype=float), np.full(365, 99.0)))  # 2005, 2006
        weather = DailyWeather.from_series(2005, 2006, tmax, tmax - 10, np.ones(730))
        meteo = with_spin_up_year(meteo_of_weather(weather, *PLACE))
        assert str(meteo.dates[0]) == "2004-01-01" and len(meteo.dates) == 366 + 730
        spin_up = meteo.tmax[:366]
        assert spin_up[58] == spin_up[59] == 58.0  # 28 and 29 February 2004: 28 February 2005
        assert spin_up[60] == 59.0  # 1 March 2004: 1 March 2005
        assert np.array_equal(meteo.tmax[366:], tmax)


def recent(climate: str, name: str) -> tuple[str, DailyWeather]:
    """A weather of the pipeline (temperatures and rain) made of the synthetic one."""
    meteo = demo_weather(climate)
    weather = DailyWeather.from_series(
        FIRST_YEAR - 1, LAST_YEAR, meteo.tmax, meteo.tmin, meteo.pluie
    )
    return name, weather


class TestWaterUseModel:
    model = WaterUseModel(*PLACE, sol_demo())

    def score(self, cycle, chain=SOYBEAN_WHEAT, **options):
        options = {"irrigated": False, "partial": False} | options
        return cycle.score(chain, START, START + 24, **options)

    def test_several_climate_models_give_the_mean_and_the_worst(self):
        wet, dry = recent("humide", "modèle humide"), recent("sec", "modèle sec")
        both = self.score(self.model.for_cycle([wet, dry]))
        alone = [self.score(self.model.for_cycle([w])) for w in (wet, dry)]
        assert both.by_model == (("modèle humide", alone[0].note), ("modèle sec", alone[1].note))
        assert both.note == pytest.approx((alone[0].note + alone[1].note) / 2)
        assert both.worst == alone[1].note < both.note
        pressure = self.model.for_cycle([wet, dry]).pressure
        assert pressure.worst > pressure.pressure > self.model.for_cycle([wet]).pressure.pressure
        assert pressure.aridity_class == "semi-aride"

    def test_every_year_of_the_weather_of_a_cycle_is_scored(self):
        name, weather = recent("humide", "NASA POWER")
        direct = note_eau(
            rotation_of_chain(SOYBEAN_WHEAT, START, START + 24),
            with_spin_up_year(meteo_of_weather(weather, *PLACE)),
            *PLACE,
            False,
            weather.first_year,
            weather.last_year,
            sol=self.model.soil,
        )
        assert self.score(self.model.for_cycle([(name, weather)])).note == direct["note"]

    def test_the_summer_rain_trend_of_today_is_used_for_every_cycle(self):
        name, today = recent("humide", "NASA POWER")
        farm = WaterUseModel(*PLACE, sol_demo(), farm_weather=today)
        assert farm.summer_rain_trend is not None
        near = farm.for_cycle([(name, today)]).pressure
        far = farm.for_cycle([recent("sec", "modèle sec")]).pressure  # another climate
        assert near.components["pluie_ete"] == far.components["pluie_ete"] == farm.summer_rain_trend
        assert far.components["aridite"] > near.components["aridite"]  # its own aridity

    def test_a_partial_chain_has_no_water_score_yet(self):
        cycle = self.model.for_cycle([recent("humide", "NASA POWER")])
        assert self.score(cycle, partial=True) is None
        assert 0 <= self.score(cycle).note <= 1

    def test_a_chain_is_simulated_once(self, monkeypatch):
        cycle = self.model.for_cycle([recent("humide", "NASA POWER")])
        first = self.score(cycle)
        monkeypatch.setattr(eau, "note_eau", None)  # a second simulation would fail
        assert self.score(cycle) is first

    def test_the_model_of_a_place_reads_the_real_bases(self, api_simulees, monkeypatch):  # noqa: F811
        monkeypatch.setattr(eau, "_soils", {})
        model = WaterUseModel.from_data_bases(*PLACE)
        assert model.source.real and "SoilGrids" in model.source.label
        assert model.observed is not None and model.observed.humidite_racines is not None
        assert "Penman-Monteith" in model.sources["et0"]
        assert model.sources["pente"].startswith("SRTM")
        assert "MERRA-2" in model.sources["sol_sec"]  # no Earthdata account: MERRA-2
        assert "Earthdata" in model.sources["esi"]
        assert model.pressure_inputs["nappes_percentile"] is None  # no USGS well in Québec
        assert model.pressure_inputs["secheresse_sol"] is not None

    def test_without_nasa_power_measures_the_model_still_works(self, api_simulees, monkeypatch):  # noqa: F811
        def no_power(*args, **kwargs):
            raise ErreurDonnees("NASA POWER ne répond pas")

        monkeypatch.setattr(eau, "_soils", {})
        monkeypatch.setattr(eau, "telecharger_power", no_power)
        model = WaterUseModel.from_data_bases(*PLACE)
        assert model.observed is None and "Hargreaves" in model.sources["et0"]
        assert 0 <= self.score(model.for_cycle([recent("humide", "NASA POWER")])).note <= 1


class TestPlanWithWater:
    @pytest.fixture(scope="class")
    def farm(self, example_inputs) -> dict:
        return deepcopy(example_inputs["ferme-demo"])

    @pytest.fixture(scope="class")
    def plan(self, plan_service, farm) -> dict:
        return plan_service.plan_farm(FarmInput.model_validate(farm)).model_dump(
            mode="json", by_alias=True
        )

    def test_the_water_criterion_of_a_chain_is_its_water_score(self, plan):
        for section in plan["sections"]:
            for cycle in section["cycles"]:
                chain = cycle["chosen"]
                assert chain["criteria"]["eau"] == pytest.approx(chain["water"]["note"], abs=1e-3)
                assert 0 <= chain["water"]["worst"] <= chain["water"]["note"] <= 1
                assert set(chain["water"]["subScores"]) == {"A", "B", "C", "D"}
                assert chain["water"]["demandMmPerYear"] > 0

    def test_the_water_risk_is_the_water_pressure_and_weighs_on_the_water_criterion(self, plan):
        for section in plan["sections"]:
            for cycle in section["cycles"]:
                pressure = cycle["waterPressure"]["pressure"]
                assert cycle["risks"]["water"] == pytest.approx(pressure, abs=1e-3)
                assert cycle["weights"]["eau"] == pytest.approx(
                    plan["weights"]["eau"] * (1 + pressure), abs=2e-3
                )
            today = section["field"]["waterPressure"]
            assert section["field"]["risksToday"]["water"] == pytest.approx(today["pressure"])
            assert set(section["field"]["measures"]) == {
                "slopePct",
                "heavyRainDays",
                "bareSoilDays",
            }

    def test_the_long_term_has_one_score_per_climate_model(self, plan):
        cycles = [c for s in plan["sections"] for c in s["cycles"]]
        by_method = {c["climate"]["method"]: c for c in cycles}
        assert len(by_method["tendance"]["chosen"]["water"]["byModel"]) == 1
        models = by_method["modeles"]["chosen"]["water"]["byModel"]
        assert [m["model"] for m in models] == by_method["modeles"]["climate"]["models"]
        assert len(models) == 3

    def test_the_plan_says_where_its_water_comes_from(self, plan):
        assert plan["meta"]["sources"]["water"]["real"] is False  # the soil of the examples
        assert "water_use" in plan["meta"]["sources"]["water"]["label"]

    def test_irrigation_is_shown_beside_the_score_of_an_irrigated_section(self, plan, farm):
        assert all(
            cycle["chosen"]["water"]["irrigationMmPerYear"] is None
            for section in plan["sections"]
            for cycle in section["cycles"]
        )
        irrigated_farm = deepcopy(farm)
        irrigated_farm["sections"] = irrigated_farm["sections"][:1]
        irrigated_farm["sections"][0]["irrigated"] = True
        irrigated = example_plan_service().plan_farm(FarmInput.model_validate(irrigated_farm))
        for cycle, dry_cycle in zip(
            irrigated.sections[0].cycles, plan["sections"][0]["cycles"], strict=False
        ):
            assert cycle.chosen.water.irrigation_mm_per_year >= 0
            # The division by 2.5 of the risk of an irrigated field is kept as it was.
            assert cycle.risks.water == pytest.approx(
                0.4 * dry_cycle["waterPressure"]["pressure"], abs=1e-3
            )

    def test_the_search_finds_the_chains_a_full_scoring_would_find(self, plan, farm, monkeypatch):
        # Scoring the water of every complete chain is slow, so the search skips the chains
        # that cannot reach the best ones. Without the shortcut the plan must be the same.
        monkeypatch.setattr(chain_search, "best_possible_score", lambda scored, weights: 100.0)
        one_section = deepcopy(farm)
        one_section["sections"] = one_section["sections"][:1]
        full = example_plan_service().plan_farm(FarmInput.model_validate(one_section))
        assert full.sections[0].model_dump(mode="json", by_alias=True) == plan["sections"][0]

    def test_a_soil_that_cannot_be_read_is_a_502_that_names_it(self, farm):
        def no_soil(lat: float, lon: float, farm_weather=None):
            raise WaterDataUnavailableError("le sol du champ n’a pas pu être lu")

        service = PlanService(
            ExampleWeatherProvider(), no_soil, ReferencePlaceData(), DemoFieldDataSource()
        )
        response = TestClient(create_app(Settings(), service)).post("/plan", json=farm)
        assert response.status_code == 502
        assert "Sol" in response.json()["detail"][0]["source"]

    def test_the_example_model_never_reads_a_data_base(self, monkeypatch):
        def network(*args, **kwargs):
            raise AssertionError("the tests must not use the network")

        monkeypatch.setattr(sol_module, "get_json", network)
        monkeypatch.setattr(sol_module, "post_json", network)
        assert example_water_model(*PLACE).source.real is False
