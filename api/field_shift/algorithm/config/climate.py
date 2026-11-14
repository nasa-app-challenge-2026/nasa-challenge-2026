"""Constants of the climate steps (2 to 4)."""

from __future__ import annotations

from typing import Final, NamedTuple


class YearRange(NamedTuple):
    first: int
    last: int


class MonthRange(NamedTuple):
    first_month: int
    last_month: int


#: A cycle that ends within this many years of today uses the NASA POWER trend only.
SHORT_TERM_HORIZON_YEARS: Final = 10
#: The 20 most recent complete years of NASA POWER, shifted by the trend (case 1).
RECENT_WINDOW: Final = YearRange(2005, 2024)
#: Baseline of the deltas: NEX-GDDP-CMIP6 historical runs stop in 2014 (case 2).
MODEL_BASELINE: Final = YearRange(1985, 2014)
#: A climate needs 20 years: window = centre − 10 … centre + 9 (case 2).
CLIMATE_WINDOW_BEFORE_YEARS: Final = 10
CLIMATE_WINDOW_AFTER_YEARS: Final = 9
#: Years when the twins' crops are known (AAFC inventory in Québec from 2011).
TWIN_PERIOD: Final = YearRange(2011, 2024)
#: NASA POWER years used for the farm.
FARM_WEATHER_YEARS: Final = YearRange(1985, 2024)

#: Growing degree-days: base 10 °C, temperatures capped at 30 °C, April to October.
DEGREE_DAY_BASE_C: Final = 10
DEGREE_DAY_CAP_C: Final = 30
GROWING_SEASON: Final = MonthRange(4, 10)
#: Summer rain: June to August.
SUMMER: Final = MonthRange(6, 8)
#: A hot day goes above 30 °C; a frost is a minimum at or below 0 °C.
HOT_DAY_C: Final = 30
FROST_C: Final = 0
#: Days of the year before this one are spring frosts, the others fall frosts.
FIRST_FALL_DAY_OF_YEAR: Final = 182
#: Frost-free season when a year has no spring / no fall frost.
NO_SPRING_FROST_DAY: Final = 0
NO_FALL_FROST_DAY: Final = 366
JANUARY: Final = 1

#: The rain ratio of a model is bounded (case 2).
MIN_RAIN_RATIO: Final = 0.5
MAX_RAIN_RATIO: Final = 2
#: Fixed-date harvests come ~3 days earlier per °C of warming (hypothesis, to check).
HARVEST_ADVANCE_MONTHS_PER_C: Final = 0.1

#: Twins kept for each target climate.
TWINS_PER_TARGET: Final = 10
#: Beyond this sigma, no real twin exists.
GOOD_TWIN_MAX_SIGMA: Final = 2
#: A covariance that is singular gets this share of its mean variance on the diagonal.
COVARIANCE_RIDGE_SHARE: Final = 1e-6
