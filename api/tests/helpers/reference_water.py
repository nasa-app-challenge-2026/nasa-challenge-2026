"""The water of field_shift.py v5.1, for the tests against the reference plans ONLY.

The reference plans (tests/fixtures/plan-*.json) were exported from field_shift.py v5.1, where
water was a fixed value per crop and a risk made of four satellite measures. The server no longer
works that way: its water comes from `water_use` (see `data_access/field_shift_eau.py`). To keep
comparing everything else with the reference (chain search, return delays, the eight other
criteria, keep or change, robustness), these tests give the planner a water model that answers
what the reference answered. Nothing here is used by the server.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace

from field_shift.algorithm.chain.chain_step import ChainStep
from field_shift.algorithm.numerics.ratios import clamp01
from field_shift.algorithm.planning.cycle_plan import CycleData, CycleDataSource
from field_shift.algorithm.water.water_model import WaterPressure, WaterScore

#: The `eau=` value of each crop sheet of field_shift.py v5.1.
REFERENCE_SHEET_WATER = {
    "mais": 0.4,
    "soya": 0.5,
    "soya-2e": 0.5,
    "ble-automne": 0.7,
    "orge": 0.6,
    "canola": 0.4,
    "sarrasin": 0.6,
    "luzerne-2": 0.6,
    "luzerne-3": 0.6,
    "foin-2": 0.7,
    "foin-3": 0.7,
    "seigle-couvert": 0.6,
    "jachere": 1.0,
}
MIN_DURATION_MONTHS = 1e-6


def reference_water_risk(measures: Mapping[str, float], summer_rain_change_pct: float) -> float:
    """`risque_eau` of `diagnostic_parcelle()` before the irrigation: ESI 40 %, SMAP 30 %, summer
    rain drop 20 %, GRACE 10 % (`measures` are the "mesures" of a fixture)."""
    return (
        0.4 * clamp01((0.8 - measures["esi_ete"]) / 0.4)
        + 0.3 * clamp01(measures["smap_secheresse"])
        + 0.2 * clamp01(-summer_rain_change_pct / 20)
        + 0.1 * clamp01(-measures["grace_tendance_cm_an"] / 2)
    )


class ReferenceCycleWater:
    """The water of one cycle as field_shift.py v5.1 computed it."""

    def __init__(self, measures: Mapping[str, float], summer_rain_change_pct: float) -> None:
        risk = reference_water_risk(measures, summer_rain_change_pct)
        self.pressure = WaterPressure(pressure=risk, worst=risk)

    def score(
        self,
        steps: Sequence[ChainStep],
        start: float,
        end: float,
        *,
        irrigated: bool,
        partial: bool,
    ) -> WaterScore:
        """`crit["eau"]` of `evaluer()`: the sheet values weighted by the time each crop holds
        the field (`steps` come in harvest order)."""
        weighted, total, previous = 0.0, 0.0, start
        for step in steps:
            span = max(step.harvest - previous, 0.0)
            weighted += REFERENCE_SHEET_WATER[step.sheet_id] * span
            total += span
            previous = step.harvest
        note = weighted / (total or MIN_DURATION_MONTHS)
        return WaterScore(note=note, worst=note)


class WithReferenceWater:
    """A source of cycle data whose water is the one of the reference."""

    def __init__(self, data: CycleDataSource, measures: Mapping[str, float]) -> None:
        self._data = data
        self._measures = measures

    def cycle_data(self, first_year: int, last_year: int) -> CycleData:
        data = self._data.cycle_data(first_year, last_year)
        water = ReferenceCycleWater(self._measures, data.climate.summer_rain_change_pct)
        return replace(data, water=water)
