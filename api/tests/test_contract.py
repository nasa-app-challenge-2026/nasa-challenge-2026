"""The server and the contract files (schema + examples) agree with each other."""

from __future__ import annotations

import json
from copy import deepcopy

import pytest
from jsonschema import Draft7Validator

from field_shift.algorithm.planning.priorities import weights_from_ranking
from field_shift.contract.farm_input import FarmInput
from field_shift.reference.criteria import CRITERIA_IDS
from field_shift.reference.crops import CROP_NAMES, SHEETS
from field_shift.reference.planning import (
    FREQUENCIES,
    MAX_CYCLE_YEARS,
    MIN_CYCLE_YEARS,
    ReserveMode,
)
from field_shift.reference.return_delays import SOIL_DISEASES
from field_shift.tools.make_examples import example_plans
from tests.conftest import EXAMPLES_DIR


def validator(schema: dict, definition: str) -> Draft7Validator:
    """A validator of one definition of the schema."""
    return Draft7Validator(
        {"$ref": f"#/definitions/{definition}", "definitions": schema["definitions"]}
    )


def errors(schema: dict, definition: str, data) -> list[str]:
    return [
        f"{'/'.join(map(str, e.path))}: {e.message}"
        for e in validator(schema, definition).iter_errors(data)
    ]


class TestIdsAreTheSameEverywhere:
    """The ids of the contract live in the schema, in this server and in the front end
    (tests/contract.test.js checks the front end against the same schema)."""

    def test_sheets(self, schema):
        assert set(schema["definitions"]["SheetId"]["enum"]) == set(SHEETS)

    def test_crops(self, schema):
        assert set(schema["definitions"]["CropId"]["enum"]) == set(CROP_NAMES)

    def test_criteria(self, schema):
        assert schema["definitions"]["CriterionId"]["enum"] == list(CRITERIA_IDS)

    def test_diseases(self, schema):
        assert set(schema["definitions"]["DiseaseId"]["enum"]) == set(SOIL_DISEASES)

    def test_time_settings(self, schema):
        time = schema["definitions"]["FarmInput"]["properties"]["farm"]["properties"]["time"][
            "properties"
        ]
        assert time["cycleYears"]["minimum"] == MIN_CYCLE_YEARS
        assert time["cycleYears"]["maximum"] == MAX_CYCLE_YEARS
        assert time["frequencyMonths"]["enum"] == [f.months for f in FREQUENCIES]

    def test_reserve_modes(self, schema):
        seeds = schema["definitions"]["FarmInput"]["properties"]["farm"]["properties"]["seeds"]
        assert set(seeds["properties"]["mode"]["enum"]) == {m.value for m in ReserveMode}


class TestExamples:
    def test_there_are_examples(self, example_inputs):
        assert {"ferme-demo", "deux-cultures-par-an", "cycle-5-ans"} <= set(example_inputs)

    def test_inputs_are_valid_for_the_schema_and_the_server(self, schema, example_inputs):
        for name, data in example_inputs.items():
            assert errors(schema, "FarmInput", data) == [], name
            FarmInput.model_validate(data)

    def test_plans_are_valid_for_the_schema(self, schema):
        for path in EXAMPLES_DIR.glob("*.plan.json"):
            assert errors(schema, "FarmPlan", json.loads(path.read_text(encoding="utf-8"))) == [], (
                path.name
            )

    def test_plans_are_what_the_server_returns_now(self):
        """A plan not regenerated after a change of the algorithm would mislead the front end:
        run `python -m field_shift.tools.make_examples`."""
        for name, plan in example_plans().items():
            written = json.loads((EXAMPLES_DIR / f"{name}.plan.json").read_text(encoding="utf-8"))
            assert plan.model_dump(mode="json", by_alias=True) == written, name


class TestSchemaRefusesWhatTheServerRefuses:
    def test_an_unknown_crop(self, schema, example_inputs):
        bad = deepcopy(example_inputs["ferme-demo"])
        bad["sections"][0]["currentRotation"] = ["riz"]
        assert errors(schema, "FarmInput", bad)

    def test_a_cycle_that_is_too_long(self, schema, example_inputs):
        bad = deepcopy(example_inputs["ferme-demo"])
        bad["farm"]["time"]["cycleYears"] = 7
        assert errors(schema, "FarmInput", bad)


def test_the_weights_of_the_plan_are_those_of_the_ranking(plan_client, example_inputs):
    plan = plan_client.post("/plan", json=example_inputs["ferme-demo"]).json()
    ranking = example_inputs["ferme-demo"]["farm"]["priorities"]
    assert plan["settings"]["priorities"] == ranking
    assert plan["weights"] == pytest.approx(weights_from_ranking(ranking), abs=1e-3)
