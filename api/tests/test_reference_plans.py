"""Steps 9b and 10 against the reference implementation.

For every scenario exported from field_shift.py v5.1 (same climate, same twins), the planner must
choose the same chains, with the same scores, decisions, alternatives and robustness.
"""

from __future__ import annotations

import pytest

from field_shift.algorithm.chain.chain_step import sheet_ids
from field_shift.algorithm.planning.parcel_planner import ParcelPlanner
from field_shift.algorithm.report.chain_label import chain_label
from field_shift.algorithm.report.messages import rule_reason_text, shared_disease_text
from tests.helpers.reference_names import crop_id_of, fixture, id_of, plain
from tests.helpers.reference_plan import inputs_of

SCENARIOS = [
    "demo-4-12-12",
    "demo-4-6-8",
    "demo-3-12-9",
    "demo-5-12-10",
    "demo-2-12-6",
    "demo-3-4-3",
    "variant-uniquement",
    "variant-betail-maladie-irrigation",
    "variant-sans-fourragere-libre",
]
#: Deliberate differences with the reference (docs/ALGORITHME.md, "Écarts avec la référence"): a
#: field with no crop in place has its yield successions read in order (the reference pairs each
#: crop with itself).
KNOWN_DEVIATIONS = {"variant-sans-fourragere-libre/P3"}
TOLERANCE = 1e-9


def assert_chain(actual_chain, expected: list) -> None:
    assert sheet_ids(actual_chain) == [id_of(step[0]) for step in expected]
    for step, (_, sowing, harvest, first, last) in zip(actual_chain, expected, strict=True):
        if sowing is None:
            assert step.sowing is None
        else:
            assert step.sowing == pytest.approx(sowing, abs=TOLERANCE)
        assert step.harvest == pytest.approx(harvest, abs=TOLERANCE)
        assert (step.first_position, step.last_position) == (first, last)


def assert_cycle(actual, ref: dict) -> None:
    assert list(actual.years) == ref["annees"]
    assert list(actual.context.candidates) == [id_of(n) for n in ref["ctx"]["candidates"]]
    assert actual.weights == pytest.approx(ref["ctx"]["poids"], rel=TOLERANCE)
    assert actual.decision.value == ref["decision"]

    chosen = actual.chosen
    assert_chain(chosen.chain, ref["chaine"])
    assert chosen.score == pytest.approx(ref["note"], abs=TOLERANCE)
    for criterion, value in ref["criteres"].items():
        if value is None:
            assert chosen.criteria[criterion] is None
        else:
            assert chosen.criteria[criterion] == pytest.approx(value, abs=TOLERANCE), criterion
    assert chosen.gaps == [tuple(crop_id_of(n) for n in g.split(" → ")) for g in ref["lacunes"]]
    assert chosen.seeds_to_buy == [crop_id_of(n) for n in ref["achats"]]
    assert [(c.sheet_id, c.sowing, c.harvest) for c in chosen.covers] == [
        (id_of(n), pytest.approx(s, abs=TOLERANCE), pytest.approx(r, abs=TOLERANCE))
        for n, s, r in ref["intercalaires"]
    ]
    assert [plain(shared_disease_text(w)) for w in chosen.warnings] == [
        plain(v) for v in ref["vigilances"]
    ]
    assert plain(chain_label(chosen.chain, chosen.covers)) == plain(ref["texte"])
    assert actual.risks.erosion == pytest.approx(ref["diagnostic"]["risque_erosion"], abs=TOLERANCE)
    assert actual.risks.water == pytest.approx(ref["diagnostic"]["risque_eau"], abs=TOLERANCE)

    if ref["reference"]:
        assert_chain(actual.reference.chain, ref["reference"])
        assert actual.reference.score == pytest.approx(ref["note_reference"], abs=TOLERANCE)
    else:
        assert actual.reference is None
    assert [
        (plain(rule_reason_text(a.reason)), a.years_without, a.minimum)
        for a in actual.reference_alerts
    ] == [(plain(a["raison"]), a["annees_sans"], a["minimum"]) for a in ref["alertes_reference"]]
    assert list(actual.removed) == [id_of(n) for n in ref["impossibles"]]
    assert [sheet_ids(a.chain) for a in actual.alternatives] == [
        [id_of(n) for n in names] for names, _ in ref["alternatives"]
    ]
    for alternative, (_, score) in zip(actual.alternatives, ref["alternatives"], strict=True):
        assert alternative.score == pytest.approx(score, abs=TOLERANCE)

    if ref["robustesse"] is None:
        assert actual.robustness is None
    else:
        assert actual.robustness == pytest.approx(ref["robustesse"], abs=TOLERANCE)
    assert actual.becomes_infeasible_later is bool(ref["non_faisable_plus_tard"])


def cases():
    for name in SCENARIOS:
        reference = fixture(f"plan-{name}.json")
        for index, parcel in enumerate(reference["parcels"]):
            label = f"{name}/{parcel['nom']}"
            marks = (
                [pytest.mark.skip(reason="known deviation")] if label in KNOWN_DEVIATIONS else []
            )
            yield pytest.param(reference, index, id=label, marks=marks)


@pytest.mark.parametrize(("reference", "index"), list(cases()))
def test_the_plan_of_a_field_is_the_reference_one(reference, index):
    inputs = inputs_of(reference)
    planner = ParcelPlanner(inputs.time, inputs.farmer, inputs.data, inputs.today)
    plan = planner.plan(inputs.parcels[index])
    expected_cycles = reference["parcels"][index]["cycles"]
    assert len(plan.cycles) == len(expected_cycles)
    for cycle, expected in zip(plan.cycles, expected_cycles, strict=True):
        assert_cycle(cycle, expected)
