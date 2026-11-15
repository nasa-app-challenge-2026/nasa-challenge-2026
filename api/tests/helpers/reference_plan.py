"""Rebuilds the inputs of a plan fixture (field_shift.py v5.1) for the Python planner. The
water is the one of the reference (see `reference_water.py`), not the one of the server.
"""

from __future__ import annotations

from dataclasses import dataclass

from field_shift.algorithm.climate.cycle_climate import ClimateMethod, CycleClimate
from field_shift.algorithm.delays.field_history import PastCrop
from field_shift.algorithm.diagnostic.parcel_diagnostic import FieldMeasures, ParcelDiagnostic
from field_shift.algorithm.planning.cycle_plan import CycleData
from field_shift.algorithm.planning.farmer_profile import FarmerProfile
from field_shift.algorithm.planning.parcel import Parcel
from field_shift.algorithm.planning.time_settings import TimeSettings
from field_shift.algorithm.twins.twin_evidence import TwinEvidence
from field_shift.reference.crops import SHEETS
from field_shift.reference.planning import ReserveMode
from tests.helpers.reference_names import crop_id_of, disease_id_of, id_of
from tests.helpers.reference_water import ReferenceCycleWater

EQUIPMENT = {"fourragère": "fourragere"}


def climate_of(raw: dict) -> CycleClimate:
    return CycleClimate(
        degree_days_per_day=tuple(raw["dj_jour"]),
        last_spring_frost=raw["gel_printemps"],
        first_fall_frost=raw["gel_automne"],
        january_minimum_c=raw["tmin_janvier"],
        harvest_advance_months=raw["decalage_fin"],
        method=ClimateMethod.TREND
        if raw["source"].startswith("tendance")
        else ClimateMethod.MODELS,
        source=raw["source"],
        summer_rain_change_pct=raw["delta_pluie_ete_pct"],
    )


class FixtureCycleData:
    """The climate and twin evidence the reference used for each cycle window of a scenario."""

    def __init__(self, windows: dict, measures: dict) -> None:
        self._windows = windows
        self._measures = measures
        self._cache: dict[str, CycleData] = {}

    def cycle_data(self, first_year: int, last_year: int) -> CycleData:
        key = f"{first_year}-{last_year}"
        if key not in self._cache:
            window = self._windows[key]
            climate = climate_of(window["climate"])
            self._cache[key] = CycleData(
                climate=climate,
                water=ReferenceCycleWater(self._measures, climate.summer_rain_change_pct),
                evidence=TwinEvidence(
                    crops=[crop_id_of(c) for c in window["cultures"]],
                    successions=[
                        (crop_id_of(a), crop_id_of(b), v) for a, b, v in window["precedents"]
                    ],
                    sigma_mean=window["sigma_moyen"],
                ),
            )
        return self._cache[key]


def _past_of(parcel: dict) -> tuple[PastCrop, ...]:
    """The reference reads the past crops from the most recent backwards."""
    if parcel["recolte_en_place"] is None:
        return ()
    free_year = 2000 + int(parcel["recolte_en_place"] // 12)
    sheet = SHEETS[id_of(parcel["culture_en_place"])] if parcel["culture_en_place"] else None
    past = list(parcel["historique"])
    if sheet and past and not sheet.is_perennial and crop_id_of(past[-1]) == sheet.crop_id:
        past = past[:-1]
    return tuple(
        PastCrop(free_year - 1 - i, crop_id_of(name)) for i, name in enumerate(reversed(past))
    )


@dataclass
class PlanInputs:
    time: TimeSettings
    farmer: FarmerProfile
    data: FixtureCycleData
    today: float
    parcels: list[Parcel]


def inputs_of(fixture: dict) -> PlanInputs:
    m = fixture["mesures"]
    measures = FieldMeasures(
        slope_pct=m["pente_pct"],
        heavy_rain_days=m["jours_pluie_intense"],
        bare_soil_days=m["jours_sol_nu"],
    )
    scenario = fixture["scenario"]
    diagnostic = ParcelDiagnostic(measures, irrigated=scenario.get("irrigation", False))
    return PlanInputs(
        time=TimeSettings(scenario["C"], scenario["f"], scenario["H"]),
        farmer=FarmerProfile(
            ranking=tuple(fixture["fermier"]["classement"]),
            livestock=fixture["fermier"]["betail"],
            missing_equipment=frozenset(
                EQUIPMENT.get(e, e) for e in fixture["fermier"]["equipement_manquant"]
            ),
            seeds=frozenset(crop_id_of(s) for s in fixture["reserve"]),
            reserve_mode=ReserveMode(scenario.get("mode", "preferer")),
        ),
        data=FixtureCycleData(fixture["windows"], m),
        today=fixture["debut"],
        parcels=[
            Parcel(
                id=p["nom"],
                diagnostic=diagnostic,
                in_place=id_of(p["culture_en_place"]) if p["culture_en_place"] else None,
                in_place_harvest=p["recolte_en_place"],
                past=_past_of(p),
                current_rotation=tuple(id_of(n) for n in p["rotation_commencee"] or ()),
                rotation_position=p["position_actuelle"],
                diseases=tuple(disease_id_of(d) for d in p.get("maladies") or ()),
            )
            for p in fixture["parcelles"]
        ],
    )
