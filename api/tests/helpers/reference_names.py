"""The golden fixtures (exported from field_shift.py) speak with the reference's French names;
these helpers translate them to the ids of this project."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from field_shift.reference.crops import CROP_NAMES, CROP_SHEETS
from field_shift.reference.return_delays import SOIL_DISEASES

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def plain(text: str) -> str:
    """The reference writes apostrophes with ' ; this project with ’."""
    return text.replace("’", "'")


_NAME_TO_ID = {
    **{plain(sheet.name): sheet.id for sheet in CROP_SHEETS},
    **{plain(name): crop_id for crop_id, name in CROP_NAMES.items()},
    "Soya 2e culture": "soya-2e",
}
_SHEET_TO_CROP = {sheet.id: sheet.crop_id for sheet in CROP_SHEETS}
_DISEASE_TO_ID = {plain(d.name): disease_id for disease_id, d in SOIL_DISEASES.items()}


def id_of(name: str) -> str:
    """Sheet id (or crop id) of a name of the reference."""
    return _NAME_TO_ID[plain(name)]


def crop_id_of(name: str) -> str:
    """Crop id of a name of the reference ("Luzerne ×2" → "luzerne")."""
    identifier = id_of(name)
    return _SHEET_TO_CROP.get(identifier, identifier)


def disease_id_of(name: str) -> str:
    return _DISEASE_TO_ID[plain(name)]


#: field_shift.py v5.1 calls the soil criterion `erosion` (here `protection_sol`), and its pests
#: criterion, the return delays, `ravageurs` (here `delais_retour`: `ravageurs` is the pests model).
_CRITERION_TO_ID = {"erosion": "protection_sol", "ravageurs": "delais_retour"}


def criterion_id_of(name: str) -> str:
    """Id of a criterion of the reference ("erosion" → "protection_sol")."""
    return _CRITERION_TO_ID.get(name, name)


def by_criterion_id(values: dict[str, Any]) -> dict[str, Any]:
    """A mapping of the reference by criterion, with the ids of this project."""
    return {criterion_id_of(name): value for name, value in values.items()}


def infinite(value: Any) -> Any:
    """ "Infinity" (JSON-safe) → inf."""
    return {"Infinity": float("inf"), "-Infinity": float("-inf")}.get(value, value)
