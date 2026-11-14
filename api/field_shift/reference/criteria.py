"""The nine criteria of the chain score (step 9b of field_shift.py v5.1).

The farmer ranks the ones that matter to him; the algorithm turns the ranking into weights
(rank order centroid) and scores every chain on each criterion, from 0 to 1.
"""

from __future__ import annotations

from typing import Final

#: Fixed order of the criteria (field_shift.py, CRITERES).
CRITERIA_IDS: Final[tuple[str, ...]] = (
    "rendement",
    "eau",
    "fourrage",
    "azote",
    "erosion",
    "matiere_org",
    "marche",
    "ravageurs",
    "reserve",
)

#: Criteria computed from the sheet values, weighted by the time each crop holds the field.
TIME_WEIGHTED_CRITERIA: Final[tuple[str, ...]] = ("eau", "fourrage", "azote", "matiere_org")
