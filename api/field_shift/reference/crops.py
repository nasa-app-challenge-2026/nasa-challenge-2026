"""Crops known to the algorithm, and the crop sheets of step 9b.

Two levels, as in the contract:
  - a *crop* is what grows in a field (the farmer's history, the seed reserve, the
    crops grown in the climate twins): `CROP_NAMES`;
  - a *sheet* is one way to grow a crop inside a rotation chain (alfalfa kept 2 or 3
    years, soybean sown after winter wheat...), with its calendar and its values for
    the scoring criteria: `CROP_SHEETS`.

VALUES ARE INDICATIVE (field_shift.py v5.1): an agronomist must check them.
The ORDER OF `CROP_SHEETS` MATTERS: the chain search tries the candidates in this
order and keeps the first one on ties.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class Role(StrEnum):
    """What a sheet is used for in a chain."""

    SOLD = "vente"
    COVER = "couvert"
    FALLOW = "jachere"


EQUIPMENT_FORAGE: Final = "fourragere"

FALLOW_SHEET_ID: Final = "jachere"

CROP_NAMES: Final[dict[str, str]] = {
    "mais": "Maïs",
    "soya": "Soya",
    "soya-2e": "Soya (2e culture)",
    "ble-automne": "Blé d’automne",
    "orge": "Orge",
    "canola": "Canola",
    "sarrasin": "Sarrasin",
    "luzerne": "Luzerne",
    "foin": "Foin",
    "seigle": "Seigle",
    "jachere": "Jachère",
    "avoine": "Avoine",
    "haricot-sec": "Haricot sec",
    "pois": "Pois",
    "chou": "Chou",
    "navet": "Navet",
    "radis": "Radis",
    "pomme-de-terre": "Pomme de terre",
    "tomate": "Tomate",
    "carotte": "Carotte",
    "celeri": "Céleri",
    "oignon": "Oignon",
    "laitue": "Laitue",
    "epinard": "Épinard",
    "betterave": "Betterave",
    "courge": "Courge",
}

#: Seeds a farmer can own (the crops that have a sheet), in the order the reserve shows them.
SEED_IDS: Final[tuple[str, ...]] = (
    "mais",
    "soya",
    "ble-automne",
    "orge",
    "canola",
    "sarrasin",
    "luzerne",
    "foin",
    "seigle",
)


@dataclass(frozen=True)
class CropSheet:
    """One way to grow a crop in a chain. Months are 0-based decimals (4.25 = early May).

    sowing_window       earliest and latest sowing month (None for fallow)
    degree_days         growing degree-days (base 10 °C) from sowing to maturity (summer crops)
    harvest_month       fixed harvest or destruction month (winter crops, perennials)
    production_years    perennials: years of production
    january_minimum_c   coldest mean January minimum the crop survives
    only_after          double crop: allowed only right after one of these sheets
    values              criteria values between 0 and 1 (fourrage, azote, matiere_org, marche); the
                        water criterion is not a sheet value: it is simulated for the whole
                        chain (`algorithm/water`)
    """

    id: str
    name: str
    crop_id: str
    values: dict[str, float]
    seed_id: str = ""
    role: Role = Role.SOLD
    sowing_window: tuple[float, float] | None = None
    degree_days: float | None = None
    harvest_month: float | None = None
    production_years: int = 0
    january_minimum_c: float | None = None
    only_after: tuple[str, ...] = ()
    frost_sensitive: bool = False
    equipment: str | None = None

    def __post_init__(self) -> None:
        # The seed defaults to the crop; soybean as a double crop is sown with soybean seed.
        if not self.seed_id:
            object.__setattr__(self, "seed_id", self.crop_id)

    @property
    def is_perennial(self) -> bool:
        return self.production_years > 0

    @property
    def years_occupied(self) -> int:
        """Years a planting of this sheet holds the field (an annual crop holds one)."""
        return max(self.production_years, 1)


def _values(fourrage: float, azote: float, matiere_org: float, marche: float) -> dict[str, float]:
    return {
        "fourrage": fourrage,
        "azote": azote,
        "matiere_org": matiere_org,
        "marche": marche,
    }


CROP_SHEETS: Final[tuple[CropSheet, ...]] = (
    CropSheet(
        id="mais",
        name="Maïs",
        crop_id="mais",
        sowing_window=(4.25, 5.5),
        degree_days=1150,
        frost_sensitive=True,
        values=_values(0.4, 0.1, 0.5, 0.9),
    ),
    CropSheet(
        id="soya",
        name="Soya",
        crop_id="soya",
        sowing_window=(4.5, 5.75),
        degree_days=1000,
        frost_sensitive=True,
        values=_values(0.1, 0.7, 0.2, 0.8),
    ),
    CropSheet(
        id="soya-2e",
        name="Soya (2e culture)",
        crop_id="soya-2e",
        seed_id="soya",
        sowing_window=(6.0, 7.0),
        degree_days=800,
        only_after=("ble-automne",),
        frost_sensitive=True,
        values=_values(0.1, 0.6, 0.2, 0.75),
    ),
    CropSheet(
        id="ble-automne",
        name="Blé d’automne",
        crop_id="ble-automne",
        sowing_window=(8.5, 9.75),
        harvest_month=6.65,
        january_minimum_c=-16,
        values=_values(0.3, 0.2, 0.6, 0.7),
    ),
    CropSheet(
        id="orge",
        name="Orge",
        crop_id="orge",
        sowing_window=(3.75, 4.75),
        degree_days=800,
        values=_values(0.4, 0.2, 0.5, 0.5),
    ),
    CropSheet(
        id="canola",
        name="Canola",
        crop_id="canola",
        sowing_window=(4.25, 5.25),
        degree_days=900,
        values=_values(0.0, 0.1, 0.3, 0.7),
    ),
    CropSheet(
        id="sarrasin",
        name="Sarrasin",
        crop_id="sarrasin",
        sowing_window=(5.5, 7.0),
        degree_days=600,
        frost_sensitive=True,
        values=_values(0.0, 0.2, 0.4, 0.4),
    ),
    CropSheet(
        id="luzerne-2",
        name="Luzerne ×2",
        crop_id="luzerne",
        sowing_window=(3.75, 5.0),
        harvest_month=8.75,
        production_years=2,
        january_minimum_c=-22,
        equipment=EQUIPMENT_FORAGE,
        values=_values(1.0, 1.0, 0.9, 0.4),
    ),
    CropSheet(
        id="luzerne-3",
        name="Luzerne ×3",
        crop_id="luzerne",
        sowing_window=(3.75, 5.0),
        harvest_month=8.75,
        production_years=3,
        january_minimum_c=-22,
        equipment=EQUIPMENT_FORAGE,
        values=_values(1.0, 1.0, 0.9, 0.4),
    ),
    CropSheet(
        id="foin-2",
        name="Foin ×2",
        crop_id="foin",
        sowing_window=(3.75, 5.0),
        harvest_month=8.75,
        production_years=2,
        january_minimum_c=-28,
        equipment=EQUIPMENT_FORAGE,
        values=_values(1.0, 0.6, 0.9, 0.35),
    ),
    CropSheet(
        id="foin-3",
        name="Foin ×3",
        crop_id="foin",
        sowing_window=(3.75, 5.0),
        harvest_month=8.75,
        production_years=3,
        january_minimum_c=-28,
        equipment=EQUIPMENT_FORAGE,
        values=_values(1.0, 0.6, 0.9, 0.35),
    ),
    CropSheet(
        id="seigle-couvert",
        name="Seigle (couvert)",
        crop_id="seigle",
        role=Role.COVER,
        sowing_window=(8.5, 10.5),
        harvest_month=4.3,
        january_minimum_c=-30,
        values=_values(0.2, 0.4, 0.6, 0.0),
    ),
    CropSheet(
        id=FALLOW_SHEET_ID,
        name="Jachère",
        crop_id="jachere",
        role=Role.FALLOW,
        values=_values(0.0, 0.0, 0.0, 0.0),
    ),
)

SHEETS: Final[dict[str, CropSheet]] = {sheet.id: sheet for sheet in CROP_SHEETS}

COVER_SHEETS: Final[tuple[CropSheet, ...]] = tuple(s for s in CROP_SHEETS if s.role is Role.COVER)


def crop_name(crop_or_sheet_id: str | None) -> str:
    """Display name of a crop id or a sheet id (the id itself if unknown)."""
    if crop_or_sheet_id is None:
        return "—"
    if crop_or_sheet_id in CROP_NAMES:
        return CROP_NAMES[crop_or_sheet_id]
    sheet = SHEETS.get(crop_or_sheet_id)
    return sheet.name if sheet else crop_or_sheet_id


def is_known_crop(crop_or_sheet_id: str) -> bool:
    return crop_or_sheet_id in CROP_NAMES or crop_or_sheet_id in SHEETS
