"""Constants of the diagnostic (step 8), the chain score (9b) and the plan (10)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class RiskTerm:
    """A measure divided by `saturation` (the value where it reaches its maximum), bounded
    to 0..1, then weighted by its `share` of the risk."""

    share: float
    saturation: float


# Step 8, erosion: slope (SRTM / NASADEM), days with 25 mm of rain (GPM IMERG), bare soil days.
EROSION_SLOPE: Final = RiskTerm(share=0.5, saturation=8)
EROSION_HEAVY_RAIN: Final = RiskTerm(share=0.3, saturation=8)
EROSION_BARE_SOIL: Final = RiskTerm(share=0.2, saturation=150)

# Step 8, water: the risk is the water pressure of the farm, given by the water model
# (`algorithm/water`). Its components and their weights are those of the model.
#: An irrigated field keeps 40 % of its water risk (the risk is divided by 2.5). The irrigation
#: also counts in the water score of the chain: whether to keep both is a decision of the team.
IRRIGATED_WATER_RISK_FACTOR: Final = 0.4

#: Without livestock, the weight of the forage criterion is multiplied by this.
NO_LIVESTOCK_FORAGE_FACTOR: Final = 0.3

#: Yield criterion: precrop values from −16 % to +16 % become 0 to 1.
PRECROP_VALUE_RANGE_PCT: Final = 16
#: Scores are on 100.
SCORE_SCALE: Final = 100

#: Beam search: partial chains kept at each position, complete chains returned.
BEAM_WIDTH: Final = 400
BEST_CHAINS: Final = 3
#: The chain in place is kept while it is at most this many points below the best.
KEEP_THRESHOLD_POINTS: Final = 5

#: Duration guard: never divide by an empty time span.
MIN_DURATION_MONTHS: Final = 1e-6

#: The farmer's reference rotation is continued over this many times the plan's positions.
REFERENCE_LENGTH_FACTOR: Final = 3
