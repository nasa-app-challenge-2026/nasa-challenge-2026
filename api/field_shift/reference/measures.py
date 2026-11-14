"""The four measures of the rotation ranking (`POST /rotations/rank`).

Every candidate rotation gets one result per measure; the results are then added, weighted by the
priorities of the farmer, to give the score the rotations are ranked by.

Only `protection_sol` is computed today. The three others have their route and their place in the
ranking, and are reported as "not available" until their logic is written.
"""

from __future__ import annotations

from typing import Final

#: Yield of the rotation, in kg/ha.
MEASURE_YIELD: Final = "rendement"
#: Water demand of the rotation.
MEASURE_WATER: Final = "eau"
#: Soil protection: erosion and water infiltration (see `algorithm/soil_protection`).
MEASURE_SOIL_PROTECTION: Final = "protection_sol"
#: Pests and diseases pressure.
MEASURE_PESTS: Final = "ravageurs"

#: Fixed order of the measures (the order of the results and of the documentation).
MEASURE_IDS: Final[tuple[str, ...]] = (
    MEASURE_YIELD,
    MEASURE_WATER,
    MEASURE_SOIL_PROTECTION,
    MEASURE_PESTS,
)

MEASURE_NAMES: Final[dict[str, str]] = {
    MEASURE_YIELD: "Rendement",
    MEASURE_WATER: "Demande en eau",
    MEASURE_SOIL_PROTECTION: "Protection du sol (érosion et infiltration)",
    MEASURE_PESTS: "Ravageurs et maladies",
}

#: Unit of the main value of each measure (None: an index without unit).
MEASURE_UNITS: Final[dict[str, str | None]] = {
    MEASURE_YIELD: "kg/ha",
    MEASURE_WATER: "mm",
    MEASURE_SOIL_PROTECTION: "RPI (1 à 5)",
    MEASURE_PESTS: None,
}
