"""The priority `ravageurs` of the plan is the team's pests model (`algorithm/pests`): the pressure
of the soil diseases, nematodes and insects the crops of a chain meet, with the history and the
declared diseases of the field. The scenarios are those of the reference plans, scored on the four
priorities instead of the nine criteria of field_shift.py v5.1.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from field_shift.algorithm.chain.chain_step import to_occupations
from field_shift.algorithm.planning.parcel_planner import ParcelPlanner
from field_shift.reference.criteria import CRITERIA_IDS
from tests.helpers.reference_names import fixture
from tests.helpers.reference_plan import inputs_of

PESTS_FIRST = ("ravageurs", "rendement", "eau", "protection_sol")


def plans_on_the_four_priorities(scenario: str, ranking=PESTS_FIRST):
    inputs = inputs_of(fixture(f"plan-{scenario}.json"))
    farmer = replace(inputs.farmer, ranking=ranking, criteria=CRITERIA_IDS)
    planner = ParcelPlanner(inputs.time, farmer, inputs.data, inputs.today)
    return [planner.plan(parcel) for parcel in inputs.parcels]


@pytest.mark.parametrize("scenario", ["demo-4-12-12", "variant-betail-maladie-irrigation"])
def test_the_pests_priority_is_the_score_of_the_pests_model(scenario):
    for plan in plans_on_the_four_priorities(scenario):
        for cycle in plan.cycles:
            chosen = cycle.chosen
            assert list(chosen.criteria) == list(CRITERIA_IDS)
            occupations = to_occupations(chosen.chain, cycle.context.catalog)
            model = cycle.context.pests.evaluate(occupations, closed=True)
            assert chosen.criteria["ravageurs"] == model.score
            assert chosen.pests.score == model.score
            assert 0 < chosen.pests.confidence <= 1


def test_the_plan_tells_the_farmer_which_crops_are_exposed_and_which_are_unknown():
    cycles = [c for plan in plans_on_the_four_priorities("demo-4-12-12") for c in plan.cycles]
    sentences = [s for c in cycles for s in c.chosen.pests.sentences]
    assert sentences and all("sans hôte" in s for s in sentences)
    for cycle in cycles:
        without_data = set(cycle.chosen.pests.crops_without_data)
        assert without_data <= {"foin", "jachere"}  # the crops the catalogue knows nothing about


def test_a_partial_chain_is_scored_on_its_pests_too():
    plan = plans_on_the_four_priorities("demo-4-12-12")[0]
    cycle = plan.cycles[0]
    chain = cycle.chosen.chain
    first_sold = next(i for i, step in enumerate(chain) if step.is_sold)
    occupations = to_occupations(chain[: first_sold + 1], cycle.context.catalog)
    partial = cycle.context.pests.evaluate(occupations, closed=False, explain=False)
    assert partial is not None and 0 <= partial.score <= 1
