"""Writes the reference plans of the contract: backend/contract/examples/*.plan.json.

For every `*.input.json` of the folder, the plan the server returns with the FICTITIOUS weather
of field_shift.py (so that the files never depend on the network, and are the same on every
machine). This weather only exists here and in the tests: the server always reads NASA POWER.

    python -m field_shift.tools.make_examples [examples_folder]
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

from field_shift.algorithm.sources.data_source import DataSource
from field_shift.algorithm.sources.demo_farm_weather import demo_farm_weather
from field_shift.contract.farm_input import FarmInput
from field_shift.contract.farm_plan import FarmPlan
from field_shift.data_access.weather_providers import WEATHER_KEY, FarmWeather
from field_shift.services.plan_service import PlanService

#: Written in the plans so that regenerating them does not change them.
FIXED_GENERATION_TIME = datetime(2026, 11, 13, tzinfo=UTC)
DEFAULT_EXAMPLES = Path(__file__).resolve().parents[3] / "backend" / "contract" / "examples"
INPUT_SUFFIX = ".input.json"
PLAN_SUFFIX = ".plan.json"
JSON_INDENT = 2


EXAMPLE_WEATHER_SOURCE = DataSource(
    WEATHER_KEY, real=False, label="Météo fictive de field_shift.py (plans d’exemple du contrat)"
)


class ExampleWeatherProvider:
    """The fixed fictitious weather of field_shift.py, whatever the place."""

    def farm_weather(self, lat: float, lon: float) -> FarmWeather:
        return FarmWeather(demo_farm_weather(), EXAMPLE_WEATHER_SOURCE)


def example_plans(examples: Path = DEFAULT_EXAMPLES) -> dict[str, FarmPlan]:
    """The plan of each example input, by example name."""
    service = PlanService(ExampleWeatherProvider())
    plans = {}
    for path in sorted(examples.glob(f"*{INPUT_SUFFIX}")):
        farm_input = FarmInput.model_validate_json(path.read_text(encoding="utf-8"))
        plans[path.name.removesuffix(INPUT_SUFFIX)] = service.plan_farm(
            farm_input, generated_at=FIXED_GENERATION_TIME
        )
    return plans


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    examples = Path(args[0]) if args else DEFAULT_EXAMPLES
    for name, plan in example_plans(examples).items():
        target = examples / f"{name}{PLAN_SUFFIX}"
        text = plan.model_dump_json(by_alias=True, indent=JSON_INDENT)
        target.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {target}")


if __name__ == "__main__":
    main()
