"""The criteria a chain is scored on (step 9b).

The farmer ranks four priorities, the same four as the measures of the rotation ranking
(`measures.py`): rendement, eau, protection_sol, ravageurs. The algorithm turns the ranking into
weights (rank order centroid) and scores every chain on each of them, from 0 to 1.

field_shift.py v5.1 scored five more criteria (fourrage, azote, matiere_org, marche, reserve),
called the soil criterion `erosion`, and scored the pests with the return delays only. They are no
longer ranked nor scored. The chain scorer still computes them when a profile asks for them
(`V51_CRITERIA_IDS`, where the return delays are `delais_retour`): the reference tests compare the
planner with field_shift.py v5.1, on its nine criteria.
"""

from __future__ import annotations

from typing import Final

from field_shift.reference.measures import (
    MEASURE_IDS,
    MEASURE_PESTS,
    MEASURE_SOIL_PROTECTION,
    MEASURE_WATER,
    MEASURE_YIELD,
)

#: The four priorities, in their fixed order: the ids of the measures of the ranking.
CRITERIA_IDS: Final[tuple[str, ...]] = MEASURE_IDS

#: Yield: the precrop values of the successions, measured in the climate twins.
YIELD_CRITERION: Final = MEASURE_YIELD
#: Water: the water score of the whole chain (`algorithm/water`).
WATER_CRITERION: Final = MEASURE_WATER
#: Soil protection: the share of the time the soil is covered by a living crop.
SOIL_CRITERION: Final = MEASURE_SOIL_PROTECTION
#: Pests: the pressure of the soil diseases, nematodes and insects (`algorithm/pests`).
PESTS_CRITERION: Final = MEASURE_PESTS
#: The pests criterion of field_shift.py v5.1: the recommended return delays only.
V51_PESTS_CRITERION: Final = "delais_retour"

#: The nine criteria of field_shift.py v5.1, in its order (its `erosion` is `protection_sol`, its
#: `ravageurs` is `delais_retour`).
V51_CRITERIA_IDS: Final[tuple[str, ...]] = (
    YIELD_CRITERION,
    WATER_CRITERION,
    "fourrage",
    "azote",
    SOIL_CRITERION,
    "matiere_org",
    "marche",
    V51_PESTS_CRITERION,
    "reserve",
)

#: Criteria of v5.1 computed from the sheet values, weighted by the time each crop holds the field.
TIME_WEIGHTED_CRITERIA: Final[tuple[str, ...]] = ("fourrage", "azote", "matiere_org")
#: The forage criterion of v5.1 (its weight drops without livestock).
FORAGE_CRITERION: Final = "fourrage"
