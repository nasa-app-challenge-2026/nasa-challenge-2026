"""Constants of the twin fields: soil filter (step 5), rotations (6), precrop values (7)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class SoilTolerances:
    """Each soil difference is divided by its tolerance; a distance of 1 or less = same soil."""

    clay_pct: float
    sand_pct: float
    #: Organic carbon is compared in logarithm: a ratio of 1.5 counts as 1.
    organic_carbon_ratio: float
    ph: float

    def widened(self, factor: float) -> SoilTolerances:
        return SoilTolerances(
            clay_pct=self.clay_pct * factor,
            sand_pct=self.sand_pct * factor,
            organic_carbon_ratio=self.organic_carbon_ratio**factor,
            ph=self.ph * factor,
        )


SOIL_TOLERANCES: Final = SoilTolerances(clay_pct=8, sand_pct=12, organic_carbon_ratio=1.5, ph=0.6)
SAME_SOIL_MAX_DISTANCE: Final = 1
#: Fewer fields than this after the filter: widen the tolerances by 25 % (shown in the app).
MIN_FIELDS_AFTER_SOIL_FILTER: Final = 200
SOIL_TOLERANCE_WIDENING: Final = 1.25

#: Rotations: cycles of 2 to 4 years, at most one atypical year.
SHORTEST_ROTATION_YEARS: Final = 2
LONGEST_ROTATION_YEARS: Final = 4
ATYPICAL_YEARS_ALLOWED: Final = 1
TOP_ROTATIONS: Final = 3

# Greenness → yield gap (Peltonen-Sainio et al. 2019): 0 at the 90th percentile of the fields
# of the same crop, zone and year, 0.30 at the median, 0.55 at the 25th percentile.
YIELD_GAP_AT_MEDIAN: Final = 0.3
YIELD_GAP_MEDIAN_TO_Q25: Final = 0.25
MAX_YIELD_GAP: Final = 1
PERCENT: Final = 100
#: Smallest spread between the median and the 25th percentile (avoids dividing by 0).
MIN_PERCENTILE_SPREAD: Final = 1e-6
#: A precrop value needs at least 20 fields in each group, else it stays unknown.
MIN_FIELDS_PER_GROUP: Final = 20
