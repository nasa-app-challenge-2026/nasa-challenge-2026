"""The value of each previous crop from the regional yield model of the team
(`data_access/yield_precrops.py`), without the network: pair statistics written as the model wrote
them on the demo farm on 15 November 2026."""

from __future__ import annotations

import pytest

from field_shift.algorithm.chain.chain_scorer import yield_criterion
from field_shift.algorithm.twins.twin_evidence import TwinEvidence
from field_shift.data_access.yield_precrops import (
    MIN_SAMPLES,
    PRECROP_KEY,
    precrop_values,
    read_precrop_values,
    with_regional_precrops,
)


def stat(mean: float, samples: int, interval: tuple[float, float]) -> dict:
    return {
        "meanEffectPct": mean,
        "stdErrorPct": 1.17,
        "intervalPct": list(interval),
        "sampleCount": samples,
        "effectiveYearsCount": min(samples, 6),
        "confidence": "elevee" if samples >= 15 else "faible",
    }


#: Pairs seen in thousands of fields of the region, and one in four fields only.
PAIR_MATRIX = {
    "pairs": {
        "mais>soya": stat(0.28, 4239, (-0.9, 1.4)),
        "soya>ble": stat(1.77, 776, (0.2, 3.3)),
        "ble>mais": stat(-1.92, 708, (-3.4, -0.4)),
        "mais>ble": stat(-4.59, 174, (-7.1, -2.1)),
        "ble>ble": stat(-2.77, 46, (-6.0, 0.5)),
        "orge>ble": stat(1.9, 4, (-16.1, 19.9)),
    }
}


def test_the_pairs_of_the_model_become_successions_of_the_plan():
    values = precrop_values(PAIR_MATRIX)
    assert values[("mais", "soya")] == 0.28
    assert values[("soya", "ble-automne")] == 1.77  # the model's "ble" is winter wheat here
    assert values[("soya-2e", "ble-automne")] == 1.77  # a double-crop soybean is a soybean


def test_a_pair_seen_in_too_few_fields_stays_unknown():
    assert MIN_SAMPLES > 4
    assert ("orge", "ble-automne") not in precrop_values(PAIR_MATRIX)


def test_the_regional_values_fill_only_what_the_twins_leave_unknown():
    twins = TwinEvidence(
        crops=["mais", "soya", "ble-automne"],
        successions=[
            ("mais", "soya", None),
            ("soya", "ble-automne", 4.0),
            ("ble-automne", "soya", None),
        ],
    )
    filled = twins.with_precrop_values(precrop_values(PAIR_MATRIX))
    assert filled.precrop_value("mais", "soya") == 0.28  # unknown in the twins: the region
    assert filled.precrop_value("soya", "ble-automne") == 4.0  # known in the twins: kept
    assert filled.precrop_value("ble-automne", "soya") is None  # unknown everywhere
    assert filled.is_observed("ble-automne", "soya") and not filled.is_observed("mais", "orge")
    assert filled.crops == twins.crops


def twins_of(*successions):
    def evidence_for(first_year, last_year, twins, soil):
        return TwinEvidence(crops=["mais", "soya", "foin"], successions=successions)

    return evidence_for


def test_the_evidence_of_every_cycle_gets_the_regional_values():
    regional = read_precrop_values(45.6, -72.9, lambda lat, lon: PAIR_MATRIX)
    evidence_for = twins_of(("mais", "soya", None), ("soya", "foin", None))
    evidence = with_regional_precrops(evidence_for, regional)(2027, 2030, [], None)
    assert evidence.precrop_value("mais", "soya") == 0.28
    # The yield criterion is no longer neutral (0.5) when the value is known.
    assert yield_criterion([0.28]) == pytest.approx(0.5 + 0.28 / 32)
    # A crop the maps do not know stays unknown, and counts as the yield model counts a pair it
    # never saw: unfavourable, so that it does not win for being unknown.
    assert evidence.precrop_value("soya", "foin") is None
    assert evidence.unmeasured_value == regional.unmeasured_value <= -1.5
    # A crop after itself takes its regional value (0 % when the region did not measure it).
    assert evidence.same_crop_value("ble-automne") == -2.77
    assert evidence.same_crop_value("soya") is None


def test_the_plan_says_where_the_values_come_from():
    regional = read_precrop_values(45.6, -72.9, lambda lat, lon: PAIR_MATRIX)
    assert regional.source.key == PRECROP_KEY and regional.source.real
    label = regional.source.label
    assert "MODIS" in label and f"{len(regional.values)} successions mesurées" in label
    assert "jamais mesurée compte" in label


def test_a_model_that_cannot_read_its_data_gives_no_value_and_says_so():
    def no_data(lat, lon):
        raise TimeoutError("Délai HTTP dépassé.")

    regional = read_precrop_values(45.6, -72.9, no_data)
    assert regional.values == {} and regional.unmeasured_value == 0  # neutral, as in v5.1
    source = regional.source
    assert not source.real and "indisponible" in source.label and "neutre" in source.label
    evidence = with_regional_precrops(twins_of(("mais", "soya", None)), regional)(
        2027, 2030, [], None
    )
    assert evidence.precrop_value("mais", "soya") is None and evidence.unmeasured_value == 0
