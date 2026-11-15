"""The only place where Field Shift meets `water_use`, the water module (api/water_use).

`water_use` simulates the water of the soil day by day (FAO-56, FAO-33, NRCS) on a real weather,
a real soil and a real slope, and gives a rotation a water score between 0 and 1. Everything the
pipeline knows about water comes from here:

    note_eau        the water score of a chain          criterion `eau` of step 9b
    pression_eau    the water pressure of the farm      water risk of step 8

and, built on these two, `WaterUseModel`: the `WaterModel` the planner is given (one per place,
then one `CycleWater` per cycle, with one weather per climate model).

Nothing of `water_use` is changed here, and no formula is added: this file converts (a chain of
the planner into a rotation of `water_use`, a `DailyWeather` into a `Meteo`) and gathers the data
(soil, slope, groundwater, soil moisture, evaporative stress). The sources of the pressure are
optional: one that does not answer is left out and named, it never stops a plan. The soil is
needed by the score: without it the plan fails (`WaterDataUnavailableError`, answered 502), as
everywhere in the server (no fictitious value to fall back on).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import fmean
from typing import Any, Final

import numpy as np

from field_shift.algorithm.chain.chain_step import ChainStep
from field_shift.algorithm.config.climate import FARM_WEATHER_YEARS, RECENT_WINDOW
from field_shift.algorithm.config.timing import TIME_EPSILON
from field_shift.algorithm.sources.data_source import DataSource
from field_shift.algorithm.timeline import month_time
from field_shift.algorithm.water.water_model import (
    NamedWeather,
    WaterPressure,
    WaterScore,
)
from field_shift.algorithm.weather.daily_weather import DailyWeather
from field_shift.data_access.soilgrids import (
    ALL_DEPTHS,
    D_FACTOR,
    SoilGridsClient,
    SoilGridsError,
)
from field_shift.data_access.weather_providers import FarmWeather
from water_use import earthdata
from water_use.cultures import CULTURES
from water_use.et0 import et0_meteo
from water_use.humidite import secheresse_merra2
from water_use.meteo import Meteo, lire_reponse_power, telecharger_power
from water_use.nappes import nappes_usgs
from water_use.notes import (
    POIDS_PRESSION,
    evaluer_rotation,
    pression_sur_l_eau,
    secheresse_depuis_percentile,
)
from water_use.reseau import ErreurDonnees
from water_use.rotation import Rotation, rotation_depuis_dict
from water_use.sol import Sol, lire_reponse_soilgrids, sol_manuel, sol_ssurgo, trouver_sol
from water_use.terrain import terrain_srtm

#: Sheet of the plan → crop code of `water_use` (`python -m water_use cultures`).
#: A crop that is not here is refused with a clear error (`water_use_code`): there is no default.
WATER_USE_CODES: Final[dict[str, str]] = {
    # the sheets of the plan (reference/crops.py, CROP_SHEETS)
    "mais": "mais",
    "soya": "soya",
    "soya-2e": "soya",
    "ble-automne": "ble_hiver",
    "orge": "orge",
    "canola": "canola",
    "sarrasin": "sarrasin",
    "luzerne-2": "luzerne",
    "luzerne-3": "luzerne",
    "foin-2": "prairie",
    "foin-3": "prairie",
    "seigle-couvert": "seigle_couvert",
}
#: What leaves the soil bare: nothing is sown, so the rotation of `water_use` has no entry for it.
BARE_SOIL_IDS: Final = frozenset({"jachere"})
#: The pipeline does not know how the soil is tilled: every chain is scored as tilled the usual
#: way (the least residue left on the soil). A choice of the team, to make an input one day.
TILLAGE: Final = "conventionnel"

#: The readable numbers of a score that the pipeline shows.
FIGURES: Final = (
    "demande_mm_an",
    "manque_mm_an",
    "irrigation_mm_an",
    "pluie_gardee_pct",
    "eau_au_semis_mm",
)
SUB_SCORES: Final = ("A", "B", "C", "D")

#: Key of the water model among the data sources of a plan.
WATER_KEY: Final = "water"
MONTHS_PER_YEAR: Final = 12
#: 29 February is not a date of every year: `water_use` reads "MM-JJ" in any year.
LEAP_DAY: Final = (2, 29)
#: The weather starts one year before the years that are scored: the soil fills up first.
SPIN_UP_YEARS: Final = 1
#: SMAP and ECOSTRESS are tasks NASA runs on its servers (minutes to hours). The server does not
#: wait: the task is sent, MERRA-2 is used meanwhile, and a later plan reads the result.
EARTHDATA_WAIT_S: Final = 0.0
#: Points closer than 0.01° share the same soil, slope and sources.
PLACE_PRECISION: Final = 100

if not set(WATER_USE_CODES.values()) <= set(CULTURES):
    raise RuntimeError("WATER_USE_CODES names a crop that water_use does not know")


class WaterDataUnavailableError(RuntimeError):
    """A data base the water score cannot do without (the soil) did not answer."""


def _silent(*_: object) -> None:
    """`water_use` prints its progress on the command line; the server says nothing."""


# --------------------------------------------------------------------------------------------------
# A chain of the planner → a rotation of water_use
# --------------------------------------------------------------------------------------------------
def water_use_code(crop_or_sheet_id: str) -> str:
    """The `water_use` code of a sheet or a crop of the pipeline. Raises ValueError (in French,
    shown to the user) when the crop has none: it is never replaced by another one."""
    try:
        return WATER_USE_CODES[crop_or_sheet_id]
    except KeyError:
        known = ", ".join(sorted(WATER_USE_CODES))
        raise ValueError(
            f"culture « {crop_or_sheet_id} » : pas de fiche eau dans water_use, la note eau ne "
            f"peut pas être calculée. Cultures connues : {known}. Ajoutez la culture à "
            "water_use/cultures.py puis à WATER_USE_CODES (field_shift_eau.py)."
        ) from None


def _month_day(day: date) -> str:
    if (day.month, day.day) == LEAP_DAY:
        day -= timedelta(days=1)
    return f"{day.month:02d}-{day.day:02d}"


@dataclass
class _Stand:
    """One crop of a chain, from its sowing day to its last day."""

    sheet_id: str
    code: str
    first_day: date
    last_day: date

    @property
    def is_cover(self) -> bool:
        return not CULTURES[self.code].vente


def _shifted(day: date, years: int) -> date:
    """The same day `years` later (29 February becomes the 28th)."""
    try:
        return day.replace(year=day.year + years)
    except ValueError:
        return day.replace(year=day.year + years, day=day.day - 1)


def _without_overlaps(stands: list[_Stand], cycle_years: int) -> list[_Stand]:
    """The stands, each one ended the day before the next is sown (the rotation repeats: the
    last one is followed by the first, `cycle_years` later).

    The planner counts in months: a cover destroyed "at 4.3" and a maize sown "at 4.3" share a
    day, and `water_use` refuses two crops on the same day. A cover left with no day at all is
    dropped; a sold crop in that case is an error of the chain."""
    stands = sorted(stands, key=lambda stand: stand.first_day)
    kept: list[_Stand] = []
    for i, stand in enumerate(stands):
        following = stands[(i + 1) % len(stands)]
        next_sowing = following.first_day
        if i + 1 == len(stands):
            next_sowing = _shifted(next_sowing, cycle_years)
        stand.last_day = min(stand.last_day, next_sowing - timedelta(days=1))
        if stand.last_day > stand.first_day:
            kept.append(stand)
        elif not stand.is_cover:
            raise ValueError(
                f"chaîne impossible à noter pour l’eau : {stand.sheet_id} semé le "
                f"{stand.first_day} n’a aucun jour avant la culture suivante"
            )
    return kept


def rotation_of_chain(
    steps: Sequence[ChainStep], start: float, end: float, name: str = "chaîne"
) -> dict[str, Any]:
    """A chain (its crops and its covers, between the absolute months `start` and `end`) in the
    rotation format of `water_use`:

        {"nom", "duree_ans", "travail_sol", "cultures": [{"culture", "annee", "semis": "MM-JJ",
         "fin": "MM-JJ", "duree_annees"}]}

    The rotation lasts the whole years from `start` to `end`, and repeats. A position left
    without crop (fallow) has no entry: the soil is bare. Raises ValueError for a crop without a
    `water_use` code, and for a chain with nothing sown (there is no water to simulate).
    """
    cycle_years = max(1, math.ceil((end - start) / MONTHS_PER_YEAR - TIME_EPSILON))
    stands = [
        _Stand(
            step.sheet_id,
            water_use_code(step.sheet_id),
            month_time.to_date(step.sowing),
            month_time.to_date(step.harvest),
        )
        for step in steps
        if step.sowing is not None and step.sheet_id not in BARE_SOIL_IDS
    ]
    if not stands:
        raise ValueError("chaîne sans aucune culture semée : pas de note eau")
    stands = _without_overlaps(stands, cycle_years)
    first_year = month_time.year_of(start)
    crops = []
    for stand in stands:
        sowing, last = _month_day(stand.first_day), _month_day(stand.last_day)
        entry: dict[str, Any] = {
            "culture": stand.code,
            "annee": (stand.first_day.year - first_year) % cycle_years + 1,
            "semis": sowing,
            "fin": last,
        }
        # `water_use` ends a crop in its sowing year, or the next one when "fin" comes before
        # "semis" (winter crops). Anything longer (perennials) says how many years it lasts.
        years = stand.last_day.year - stand.first_day.year + 1
        if last <= sowing:
            years -= 1
        if years > 1:
            entry["duree_annees"] = years
        crops.append(entry)
    return {"nom": name, "duree_ans": cycle_years, "travail_sol": TILLAGE, "cultures": crops}


# --------------------------------------------------------------------------------------------------
# The weather of a cycle → a Meteo of water_use
# --------------------------------------------------------------------------------------------------
def meteo_of_weather(
    weather: DailyWeather,
    lat: float,
    lon: float,
    observed: Meteo | None = None,
    source: str = "",
) -> Meteo:
    """A weather of the pipeline (°C, mm/day) as a `Meteo`.

    The pipeline only carries temperatures and rain. Humidity (%), wind at 2 m (m/s) and solar
    radiation (MJ/m²/day) are those NASA POWER measured on the same days (`observed`), when it
    has them: the weather of a cycle is made of real past years, warmed or made wetter. Without
    them they are NaN, and `water_use` computes the reference evapotranspiration with Hargreaves
    instead of Penman-Monteith.
    """
    dates = np.arange(
        np.datetime64(f"{weather.first_year}-01-01"),
        np.datetime64(f"{weather.last_year + 1}-01-01"),
        dtype="datetime64[D]",
    )
    if len(dates) != len(weather):
        raise ValueError("la météo du cycle doit couvrir des années complètes, jour après jour")
    unknown = np.full(len(dates), np.nan)
    humidity, wind, radiation, altitude = unknown, unknown, unknown, 0.0
    if observed is not None:
        altitude = observed.altitude
        rows = np.searchsorted(observed.dates, dates)
        inside = rows < len(observed.dates)
        inside[inside] = observed.dates[rows[inside]] == dates[inside]
        if inside.all():
            humidity, wind, radiation = observed.rh[rows], observed.u2[rows], observed.rs[rows]
    return Meteo(
        dates,
        np.asarray(weather.tmax, dtype=float),
        np.asarray(weather.tmin, dtype=float),
        humidity,
        wind,
        radiation,
        np.asarray(weather.rain, dtype=float),
        lat,
        lon,
        altitude,
        source=source,
    )


def with_spin_up_year(meteo: Meteo) -> Meteo:
    """The weather with its first year played once more before it, on the dates of the year
    before (29 February takes the 28th): the soil fills up on the climate of the cycle, and every
    year of the cycle is scored. `meteo` starts on 1 January."""
    first = int(meteo.annees[0])
    start = date(first, 1, 1)
    spin_up = [
        date(first - 1, 1, 1) + timedelta(days=i)
        for i in range((start - date(first - 1, 1, 1)).days)
    ]
    rows = np.array([(_shifted(day, SPIN_UP_YEARS) - start).days for day in spin_up])

    def extended(values: np.ndarray | None) -> np.ndarray | None:
        return None if values is None else np.concatenate((values[rows], values))

    return Meteo(
        np.concatenate((np.array(spin_up, dtype="datetime64[D]"), meteo.dates)),
        extended(meteo.tmax),
        extended(meteo.tmin),
        extended(meteo.rh),
        extended(meteo.u2),
        extended(meteo.rs),
        extended(meteo.pluie),
        meteo.lat,
        meteo.lon,
        meteo.altitude,
        source=meteo.source,
        jours_bouches=meteo.jours_bouches,
        humidite_racines=extended(meteo.humidite_racines),
    )


def summer_rain_trend(
    lat: float, lon: float, observed: Meteo | None, farm_weather: DailyWeather | None
) -> float | None:
    """The summer rain component of the pressure (`pluie_ete`, 0 to 1) on the recent weather of
    the farm (RECENT_WINDOW), from NASA POWER as measured, else from the weather of the plan.

    It is a trend measured today, like the groundwater and the soil moisture: every cycle uses it.
    Measured on the weather of a cycle, it would compare the two halves of 1985–2014 for the
    cycles beyond 10 years (their weather is 1985–2014 changed by the climate models, the same
    change every year), and the pressure would drop between the near and the far cycles without
    the climate getting wetter.
    """
    if observed is not None:
        recent = observed.sous_periode(RECENT_WINDOW.first, RECENT_WINDOW.last)
    elif farm_weather is not None:
        recent = meteo_of_weather(farm_weather.between(*RECENT_WINDOW), lat, lon)
    else:
        return None
    if len(recent.dates) == 0:
        return None
    et0, _ = et0_meteo(recent)
    return pression_eau(recent, et0, *RECENT_WINDOW)["composantes"].get("pluie_ete")


def with_component(result: Mapping[str, Any], name: str, value: float) -> dict[str, Any]:
    """A result of `pression_eau` with one component replaced, and the pressure weighted again
    as `water_use.notes.pression_sur_l_eau` weighs it (POIDS_PRESSION over the components there
    are)."""
    components = {**result["composantes"], name: value}
    total = sum(POIDS_PRESSION[k] for k in components)
    pressure = sum(POIDS_PRESSION[k] * v for k, v in components.items()) / total
    return {
        **result,
        "pression": round(pressure, 3),
        "composantes": components,
        "manquantes": [k for k in POIDS_PRESSION if k not in components],
    }


# --------------------------------------------------------------------------------------------------
# Soil and slope of a place
# --------------------------------------------------------------------------------------------------
_soils: dict[tuple[int, int], Sol] = {}
#: Reads the soil of a place (lat, lon) → Sol; raises ErreurDonnees.
SoilReader = Callable[[float, float], Sol]
#: The box where water_use asks SSURGO first (the United States, wide).
SSURGO_BOX: Final = ((18.0, 72.0), (-180.0, -65.0))


def _water_use_soil(lat: float, lon: float) -> Sol:
    """SSURGO, then SoilGrids, as water_use reads them (its REST requests)."""
    return trouver_sol(lat, lon, journal=_silent)


def _soilgrids_answer(client: SoilGridsClient, lat: float, lon: float) -> dict[str, Any]:
    """SoilGrids read on its WCS, written as its REST API answers (what water_use reads)."""
    layers = client.layers(lat, lon, ALL_DEPTHS, ("sand", "clay", "soc"))
    return {
        "properties": {
            "layers": [
                {
                    "name": name,
                    "unit_measure": {"d_factor": D_FACTOR},
                    "depths": [
                        {
                            "label": label,
                            "values": {"mean": None if value is None else value * D_FACTOR},
                        }
                        for label, value in by_depth.items()
                    ],
                }
                for name, by_depth in layers.items()
            ]
        }
    }


def soilgrids_soil_reader(client: SoilGridsClient) -> SoilReader:
    """The soil of a place with SoilGrids read on its WCS (the REST API water_use asks did not
    answer for minutes on 2026-11-15): SSURGO first in the United States, as water_use does, then
    SoilGrids. The formulas of water_use are the same (`lire_reponse_soilgrids`)."""

    def read(lat: float, lon: float) -> Sol:
        (lat_min, lat_max), (lon_min, lon_max) = SSURGO_BOX
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            try:
                soil = sol_ssurgo(lat, lon)
            except ErreurDonnees:
                soil = None
            if soil is not None:
                if not soil.groupe_hydro:  # SSURGO has no group here: the texture's
                    soil.groupe_hydro = read_soilgrids(lat, lon).groupe_hydro
                    soil.details["groupe_hydro"] = "SoilGrids (texture 0-30 cm), absent de SSURGO"
                return soil
        return read_soilgrids(lat, lon)

    def read_soilgrids(lat: float, lon: float) -> Sol:
        try:
            return lire_reponse_soilgrids(_soilgrids_answer(client, lat, lon))
        except SoilGridsError as error:
            raise ErreurDonnees(str(error)) from error

    return read


def soil_of_place(lat: float, lon: float, read: SoilReader | None = None) -> Sol:
    """The soil of the place (SSURGO in the United States, SoilGrids elsewhere) with its slope
    (SRTM). The slope is optional: without it, the runoff tables are used as they are. Read once
    per place. Raises WaterDataUnavailableError when no soil base answers."""
    key = (round(lat * PLACE_PRECISION), round(lon * PLACE_PRECISION))
    if key not in _soils:
        try:
            soil = (read or _water_use_soil)(lat, lon)
        except ErreurDonnees as error:
            raise WaterDataUnavailableError(
                f"le sol du champ n’a pas pu être lu pour la note eau : {error}"
            ) from error
        try:
            soil.pente = terrain_srtm(lat, lon).pente
        except ErreurDonnees:
            soil.pente = None
        _soils[key] = soil
    return _soils[key]


# --------------------------------------------------------------------------------------------------
# The two functions of the pipeline
# --------------------------------------------------------------------------------------------------
def note_eau(
    chaine: Mapping[str, Any] | Rotation,
    meteo_cycle: Meteo,
    lat: float,
    lon: float,
    irrigue: bool,
    debut: int,
    fin: int,
    *,
    sol: Sol | None = None,
    et0: np.ndarray | None = None,
) -> dict[str, Any]:
    """The water score of a chain on the weather of a cycle.

    chaine        the chain in the rotation format of `water_use` (see `rotation_of_chain`)
    meteo_cycle   daily weather, whole years, starting ONE YEAR before `debut` (the soil fills up)
    debut, fin    first and last year that are scored
    sol, et0      given when they are already known (else: the soil and slope of the place are
                  read, and the reference evapotranspiration is computed from the weather)

    Returns the score (`note`, 0 to 1), its four parts `A` `B` `C` `D`, the `alertes` and the
    readable numbers `demande_mm_an`, `manque_mm_an`, `irrigation_mm_an`, `pluie_gardee_pct`,
    `eau_au_semis_mm`.
    """
    rotation = chaine if isinstance(chaine, Rotation) else rotation_depuis_dict(dict(chaine))
    if int(meteo_cycle.annees[0]) > debut - SPIN_UP_YEARS:
        raise ValueError(
            f"la météo doit commencer un an avant {debut} pour remplir le sol "
            f"(elle commence en {int(meteo_cycle.annees[0])})"
        )
    if sol is None:
        sol = soil_of_place(lat, lon)
    if et0 is None:
        et0, _ = et0_meteo(meteo_cycle)
    evaluation = evaluer_rotation(rotation, meteo_cycle, sol, debut, fin, irrigue, et0)
    return {
        "note": evaluation.note,
        "A": evaluation.A,
        "B": evaluation.B,
        "C": evaluation.C,
        "D": evaluation.D,
        "alertes": list(evaluation.alertes),
        **{name: evaluation.chiffres[name] for name in FIGURES},
    }


def pression_eau(
    meteo: Meteo,
    et0: np.ndarray,
    debut: int,
    fin: int,
    nappes_percentile: float | None = None,
    esi: float | None = None,
    secheresse_sol: float | None = None,
) -> dict[str, Any]:
    """The water pressure of the farm on a weather (0 = water is not scarce, 1 = very dry).

    nappes_percentile  recent groundwater level, percentile 0–100 (50 = normal)
    esi                standardized anomaly of the evaporative stress index (negative = stress)
    secheresse_sol     root-zone drought, 0 to 1 (from a SMAP percentile:
                       `water_use.notes.secheresse_depuis_percentile`)

    A value that is None is left out: the other components share its weight (see
    `pressure_inputs` for the bases each one comes from). Returns `pression`, its `composantes`,
    the `manquantes` ones, the aridity index and its class.
    """
    return pression_sur_l_eau(
        meteo,
        et0,
        debut,
        fin,
        nappes_percentile=nappes_percentile,
        esi=esi,
        secheresse_sol=secheresse_sol,
    )


def _attempt(read: Callable[[], Any]) -> tuple[Any, str]:
    """What a data base gives, or None and why: a base that fails never stops the pipeline."""
    try:
        return read(), ""
    except ErreurDonnees as error:
        return None, str(error)


def pressure_inputs(
    lat: float,
    lon: float,
    observed: Meteo | None,
    first_year: int,
    last_year: int,
    earthdata_wait_s: float = EARTHDATA_WAIT_S,
) -> tuple[dict[str, float | None], dict[str, str]]:
    """What the bases know today about the water of the place: (the `nappes_percentile`, `esi`
    and `secheresse_sol` of `pression_eau`, where each one comes from or why it is missing).

    Same order and same fallbacks as the command line of `water_use` (`_sources_extra`):
    groundwater from the USGS wells (United States only); root-zone drought from SMAP with a
    NASA Earthdata account, else from MERRA-2; evaporative stress from ECOSTRESS with the account.
    """
    inputs: dict[str, float | None] = {
        "nappes_percentile": None,
        "esi": None,
        "secheresse_sol": None,
    }
    sources: dict[str, str] = {}

    wells, why = _attempt(lambda: nappes_usgs(lat, lon, first_year, last_year))
    if wells is not None:
        inputs["nappes_percentile"] = wells["percentile"]
        sources["nappes"] = f"{wells['source']} : percentile {wells['percentile']}"
    else:
        sources["nappes"] = f"non mesuré : {why or 'aucun puits USGS suivi près du champ'}"

    account, why = _attempt(earthdata.identifiants)
    if account is None:
        sources["esi"] = "non mesuré : compte NASA Earthdata absent"
    else:
        smap, why = _attempt(
            lambda: earthdata.smap_percentile(
                lat, lon, last_year, earthdata_wait_s, journal=_silent
            )
        )
        if smap is not None:
            inputs["secheresse_sol"] = round(secheresse_depuis_percentile(smap["percentile"]), 3)
            sources["sol_sec"] = f"{smap['source']} : percentile {smap['percentile']}"
        stress, why = _attempt(
            lambda: earthdata.ecostress_esi(
                lat, lon, first_year, last_year, earthdata_wait_s, journal=_silent
            )
        )
        if stress is not None:
            inputs["esi"] = stress["anomalie"]
            sources["esi"] = f"{stress['source']} : anomalie {stress['anomalie']:+.2f}"
        else:
            sources["esi"] = f"non mesuré : {why}"

    if inputs["secheresse_sol"] is None:
        model = None if observed is None else secheresse_merra2(observed, first_year, last_year)
        if model is not None:
            inputs["secheresse_sol"] = model["secheresse"]
            sources["sol_sec"] = f"{model['source']} : percentile {model['percentile']}"
        else:
            sources["sol_sec"] = "non mesuré : ni SMAP ni humidité MERRA-2 pour ce champ"
    return inputs, sources


# --------------------------------------------------------------------------------------------------
# The water model of the planner
# --------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class _CycleWeather:
    """One weather of a cycle, ready for `water_use`."""

    name: str
    meteo: Meteo
    et0: np.ndarray
    first_year: int
    last_year: int


def _mean_of(values: Sequence[Mapping[str, float]], names: Sequence[str]) -> dict[str, float]:
    return {name: fmean(value[name] for value in values) for name in names}


class WaterUseCycle:
    """`water_use` on the weather of one cycle (the `CycleWater` of the planner).

    A chain gets one score per weather (one per climate model beyond the short term): the mean is
    the criterion, the worst is kept beside it. Every year of a weather is scored; its first year,
    played once before it, fills the soil. Only complete chains are scored: a score is a
    simulation of every day of about twenty years, too long for the thousands of partial chains
    the search builds. The scores are kept: the same chain is asked several times.

    The pressure is computed on each weather, with the summer rain trend of today
    (`summer_rain_trend`) when the model knows it.
    """

    def __init__(
        self,
        model: WaterUseModel,
        weathers: Sequence[NamedWeather],
    ) -> None:
        if not weathers:
            raise ValueError("la note eau a besoin de la météo du cycle")
        self._model = model
        self._weathers = []
        for name, weather in weathers:
            meteo = with_spin_up_year(
                meteo_of_weather(weather, model.lat, model.lon, model.observed, name)
            )
            et0, _ = et0_meteo(meteo)
            self._weathers.append(
                _CycleWeather(name, meteo, et0, weather.first_year, weather.last_year)
            )
        self._scores: dict[tuple, WaterScore] = {}
        self.pressure = self._pressure()

    def _pressure(self) -> WaterPressure:
        results = [
            pression_eau(w.meteo, w.et0, w.first_year, w.last_year, **self._model.pressure_inputs)
            for w in self._weathers
        ]
        trend = self._model.summer_rain_trend
        if trend is not None:
            results = [with_component(result, "pluie_ete", trend) for result in results]
        components = sorted({name for result in results for name in result["composantes"]})
        return WaterPressure(
            pressure=fmean(result["pression"] for result in results),
            worst=max(result["pression"] for result in results),
            components={
                name: fmean(result["composantes"].get(name, 0.0) for result in results)
                for name in components
            },
            missing=tuple(results[0]["manquantes"]),
            sources=dict(self._model.sources),
            aridity_index=fmean(result["indice_aridite"] for result in results),
            aridity_class=max(results, key=lambda result: result["pression"])["classe"],
        )

    def score(
        self,
        steps: Sequence[ChainStep],
        start: float,
        end: float,
        *,
        irrigated: bool,
        partial: bool,
    ) -> WaterScore | None:
        if partial:
            return None
        rotation = rotation_of_chain(steps, start, end)
        key = (
            rotation["duree_ans"],
            irrigated,
            tuple(tuple(sorted(crop.items())) for crop in rotation["cultures"]),
        )
        if key not in self._scores:
            self._scores[key] = self._score(rotation, irrigated)
        return self._scores[key]

    def _score(self, rotation: dict[str, Any], irrigated: bool) -> WaterScore:
        parsed = rotation_depuis_dict(rotation)
        results = [
            note_eau(
                parsed,
                w.meteo,
                self._model.lat,
                self._model.lon,
                irrigated,
                w.first_year,
                w.last_year,
                sol=self._model.soil,
                et0=w.et0,
            )
            for w in self._weathers
        ]
        alerts = dict.fromkeys(alert for result in results for alert in result["alertes"])
        return WaterScore(
            note=fmean(result["note"] for result in results),
            worst=min(result["note"] for result in results),
            sub_scores=_mean_of(results, SUB_SCORES),
            figures=_mean_of(results, FIGURES),
            alerts=tuple(alerts),
            by_model=tuple(
                (w.name, r["note"]) for w, r in zip(self._weathers, results, strict=True)
            ),
        )


class WaterUseModel:
    """`water_use` for one place (the `WaterModel` of the planner).

    soil             soil and slope of the place
    observed         what NASA POWER measured there, with humidity, wind, radiation and the
                     MERRA-2 soil moisture (None: temperatures and rain only, Hargreaves)
    pressure_inputs  groundwater, evaporative stress and soil drought of today
                     (`pressure_inputs()`), the same for every cycle
    sources          where each of them comes from
    real             False when the soil is not the one of the place (examples, tests)
    farm_weather     the NASA POWER weather of the plan (temperatures and rain): with `observed`,
                     where the summer rain trend of today is read (`summer_rain_trend`)
    """

    def __init__(
        self,
        lat: float,
        lon: float,
        soil: Sol,
        observed: Meteo | None = None,
        pressure_inputs: Mapping[str, float | None] | None = None,
        sources: Mapping[str, str] | None = None,
        real: bool = True,
        farm_weather: DailyWeather | None = None,
    ) -> None:
        self.lat = lat
        self.lon = lon
        self.soil = soil
        self.observed = observed
        self.summer_rain_trend = summer_rain_trend(lat, lon, observed, farm_weather)
        self.pressure_inputs = dict(pressure_inputs or {})
        self.sources = {"sol": soil.source, **(sources or {})}
        self.source = DataSource(
            WATER_KEY, real, f"water_use, bilan d’eau du sol jour par jour — sol : {soil.source}"
        )

    @classmethod
    def with_soil_texture(
        cls,
        lat: float,
        lon: float,
        sand_pct: float,
        clay_pct: float,
        organic_matter_pct: float,
        farm_weather: DailyWeather | None = None,
    ) -> WaterUseModel:
        """The model on a soil given by its texture instead of the soil of the place, and on no
        data base at all: for the example plans and the tests, which never use the network. It
        is marked as not real."""
        soil = sol_manuel(sand_pct, clay_pct, organic_matter_pct)
        soil.source = (
            f"sol FICTIF ({sand_pct:g} % sable, {clay_pct:g} % argile, "
            f"{organic_matter_pct:g} % matière organique)"
        )
        sources = {"et0": "Hargreaves, températures seules", "pente": "non lue : tables NRCS"}
        return cls(lat, lon, soil, sources=sources, real=False, farm_weather=farm_weather)

    @classmethod
    def from_data_bases(
        cls,
        lat: float,
        lon: float,
        power_series: Mapping[str, Any] | None = None,
        soil_reader: SoilReader | None = None,
        farm_weather: DailyWeather | None = None,
    ) -> WaterUseModel:
        """The model of a place, read from the real data bases.

        `power_series` is the NASA POWER daily answer the plan already read at the place (every
        variable, from one year before the scored years): given, NASA POWER is not asked again.
        `soil_reader` reads the soil (default: as water_use reads it).

        Raises WaterDataUnavailableError when the soil cannot be read. Everything else is
        optional and named in `sources` when it is missing.
        """
        soil = soil_of_place(lat, lon, soil_reader)
        sources = {
            "pente": "SRTM 30 m (NASA)" if soil.pente is not None else "non lue : tables NRCS",
        }
        first, last = FARM_WEATHER_YEARS.first - SPIN_UP_YEARS, FARM_WEATHER_YEARS.last
        if power_series is not None:
            observed, why = _attempt(lambda: lire_reponse_power(dict(power_series), lat, lon))
        else:
            observed, why = _attempt(lambda: telecharger_power(lat, lon, first, last))
        sources["et0"] = (
            "Penman-Monteith FAO-56 (humidité, vent et rayonnement de NASA POWER)"
            if observed is not None
            else f"Hargreaves, températures seules ({why})"
        )
        inputs, pressure_sources = pressure_inputs(
            lat, lon, observed, RECENT_WINDOW.first, RECENT_WINDOW.last
        )
        return cls(
            lat,
            lon,
            soil,
            observed,
            inputs,
            {**sources, **pressure_sources},
            farm_weather=farm_weather,
        )

    def for_cycle(self, weathers: Sequence[NamedWeather]) -> WaterUseCycle:
        return WaterUseCycle(self, weathers)


def water_models(
    soilgrids: SoilGridsClient,
) -> Callable[[float, float, FarmWeather], WaterUseModel]:
    """The water model of each place, on the NASA POWER answer the plan already read there and
    on the soil of SSURGO / SoilGrids (WCS)."""
    reader = soilgrids_soil_reader(soilgrids)

    def model(lat: float, lon: float, farm_weather: FarmWeather) -> WaterUseModel:
        return WaterUseModel.from_data_bases(
            lat, lon, farm_weather.power_series, reader, farm_weather.weather
        )

    return model
