"""Step 7: greenness → yield → value of the previous crop (Peltonen-Sainio et al. 2019).

The peak NDVI (NASA HLS, 30 m) of a field is compared with the fields of the same crop, zone and
year (comparing the same year cancels the weather of the year). Its rank becomes an estimated
yield gap: 0 at the 90th percentile, 0.30 at the median, 0.55 at the 25th percentile. The value of
crop A before crop B is the mean gap of B after B (monoculture) minus the mean gap of B after A:
positive = A helps B. At least 20 fields per group, else the value stays unknown.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from statistics import fmean

from field_shift.algorithm.config.twins import (
    MAX_YIELD_GAP,
    MIN_FIELDS_PER_GROUP,
    MIN_PERCENTILE_SPREAD,
    PERCENT,
    YIELD_GAP_AT_MEDIAN,
    YIELD_GAP_MEDIAN_TO_Q25,
)


@dataclass(frozen=True)
class NdviPercentiles:
    """Peak NDVI of the fields of the same crop, zone and year."""

    p90: float
    p50: float
    p25: float


@dataclass(frozen=True)
class FieldYear:
    """One field in one year: its crop, the crop before, and its estimated yield gap (0 to 1)."""

    crop: str
    previous: str
    yield_gap: float


def yield_gap_from_ndvi(ndvi: float, percentiles: NdviPercentiles) -> float:
    """Estimated yield gap (0 to 1) of a field from its peak NDVI."""
    p = percentiles
    if ndvi >= p.p90:
        return 0.0
    if ndvi > p.p50:
        return YIELD_GAP_AT_MEDIAN * (p.p90 - ndvi) / (p.p90 - p.p50)
    return min(
        MAX_YIELD_GAP,
        YIELD_GAP_AT_MEDIAN
        + YIELD_GAP_MEDIAN_TO_Q25 * (p.p50 - ndvi) / max(p.p50 - p.p25, MIN_PERCENTILE_SPREAD),
    )


def precrop_value(
    field_years: Sequence[FieldYear],
    previous: str,
    next_crop: str,
    min_fields: int = MIN_FIELDS_PER_GROUP,
) -> float | None:
    """Yield gain (%) of `next_crop` when it follows `previous` rather than itself.

    None = gap in the data (fewer than 20 fields in a group)."""

    def gaps_after(before: str) -> list[float]:
        return [r.yield_gap for r in field_years if r.crop == next_crop and r.previous == before]

    monoculture = gaps_after(next_crop)
    after_previous = gaps_after(previous)
    if len(monoculture) < min_fields or len(after_previous) < min_fields:
        return None
    return PERCENT * (fmean(monoculture) - fmean(after_previous))
