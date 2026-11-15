"""FICTITIOUS steps 5 to 7: what the twin fields grow and the value of each previous crop
(field_shift.py, `donnees_cycle` of the demo).

Real values come from the crop maps (USDA Crop Sequence Boundaries, AAFC inventory) and NASA HLS
greenness of the twin fields, after the soil filter (`twin_evidence_builder.py`).

Near twins still grow canola; once the cycle is 1.5 °C warmer than 2015, the twins look like Ohio,
with double-cropped soybean after winter wheat.
"""

from __future__ import annotations

from collections.abc import Sequence
from statistics import fmean
from typing import Final

from field_shift.algorithm.twins.climate_twin_finder import Twin
from field_shift.algorithm.twins.twin_evidence import TwinEvidence

WARMING_C_PER_YEAR: Final = 0.07
WARMING_REFERENCE_YEAR: Final = 2015
OHIO_LIKE_WARMING_C: Final = 1.5

CROPS: Final = ("mais", "soya", "ble-automne", "orge", "luzerne", "foin", "sarrasin")
#: (previous, next, yield gain %); None = seen in fewer than 20 fields.
SUCCESSIONS: Final[tuple[tuple[str, str, float | None], ...]] = (
    ("soya", "mais", 8),
    ("ble-automne", "mais", 6),
    ("luzerne", "mais", 9),
    ("foin", "mais", 7),
    ("mais", "soya", 5),
    ("ble-automne", "soya", 4),
    ("soya", "ble-automne", 6),
    ("mais", "orge", 3),
    ("orge", "luzerne", None),
    ("orge", "foin", None),
    ("ble-automne", "luzerne", None),
    ("ble-automne", "foin", None),
    ("soya", "orge", 4),
    ("orge", "mais", 5),
    ("mais", "luzerne", None),
    ("soya", "luzerne", None),
    ("sarrasin", "ble-automne", None),
    ("ble-automne", "sarrasin", None),
    ("sarrasin", "mais", 3),
    ("soya", "sarrasin", None),
)
NORTHERN_CROPS: Final = ("canola",)
NORTHERN_SUCCESSIONS: Final[tuple[tuple[str, str, float | None], ...]] = (
    ("canola", "ble-automne", 5),
    ("ble-automne", "canola", None),
    ("orge", "canola", None),
    ("canola", "mais", 4),
)
SOUTHERN_CROPS: Final = ("soya-2e",)
SOUTHERN_SUCCESSIONS: Final[tuple[tuple[str, str, float | None], ...]] = (
    ("ble-automne", "soya-2e", None),
    ("soya-2e", "mais", 6),
    ("soya-2e", "ble-automne", None),
)


def demo_warming(first_year: int, last_year: int) -> float:
    """Fictitious warming of a cycle compared with 2015, in °C."""
    return max(0.0, WARMING_C_PER_YEAR * ((first_year + last_year) / 2 - WARMING_REFERENCE_YEAR))


def demo_twin_evidence(first_year: int, last_year: int, twins: Sequence[Twin]) -> TwinEvidence:
    """The crops and successions of the fictitious twin fields of a cycle."""
    northern = demo_warming(first_year, last_year) < OHIO_LIKE_WARMING_C
    extra_crops = NORTHERN_CROPS if northern else SOUTHERN_CROPS
    extra_successions = NORTHERN_SUCCESSIONS if northern else SOUTHERN_SUCCESSIONS
    finite = [t.sigma for t in twins if t.sigma != float("inf")]
    return TwinEvidence(
        crops=[*CROPS, *extra_crops],
        successions=[*SUCCESSIONS, *extra_successions],
        sigma_mean=fmean(finite) if finite else None,
        twins=twins,
    )
