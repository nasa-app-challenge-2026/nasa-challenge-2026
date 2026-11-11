"""Small, dependency-free statistics used to summarise yearly indicators.

Everything here describes what was observed in the analysed years. Nothing is a forecast.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import NormalDist, fmean, median, pstdev

MIN_YEARS_FOR_TREND = 10
"""Below this many years a monotonic trend test says very little; no trend is reported."""


def percentile(values: Sequence[float], fraction: float) -> float:
    """Percentile by linear interpolation between closest ranks (Hyndman & Fan type 7).

    ``fraction`` is between 0 and 1. This is the default of NumPy and R, stated here so the
    numbers can be reproduced elsewhere.
    """
    if not values:
        raise ValueError("percentile of an empty sequence is undefined")
    if not 0.0 <= fraction <= 1.0:
        raise ValueError(f"fraction must be within [0, 1], got {fraction}")
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


@dataclass(frozen=True, slots=True)
class Trend:
    """Monotonic trend of a yearly series.

    ``slope_per_decade`` is the Theil-Sen estimator (median of all pairwise slopes), robust
    to outliers. ``p_value`` is the two-sided Mann-Kendall test with tie correction and
    continuity correction (normal approximation). Both are the methods used for the trend
    analysis of the Atlas agroclimatique du Québec (source: audet_2012).
    """

    slope_per_decade: float
    p_value: float
    years: int

    @property
    def is_significant(self) -> bool:
        """Conventional 5 % level. A non-significant trend is not evidence of no change."""
        return self.p_value < 0.05


def theil_sen_slope(x: Sequence[float], y: Sequence[float]) -> float:
    """Median of the slopes of all pairs of points with distinct x."""
    if len(x) != len(y):
        raise ValueError("x and y must have the same length")
    slopes = [
        (y[j] - y[i]) / (x[j] - x[i])
        for i in range(len(x))
        for j in range(i + 1, len(x))
        if x[j] != x[i]
    ]
    if not slopes:
        raise ValueError("at least two points with distinct x are required")
    return median(slopes)


def mann_kendall_p_value(y: Sequence[float]) -> float:
    """Two-sided p-value of the Mann-Kendall trend test for a series in time order."""
    n = len(y)
    if n < 3:
        raise ValueError("the Mann-Kendall test needs at least three values")
    s = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            s += (y[j] > y[i]) - (y[j] < y[i])

    tie_counts: dict[float, int] = {}
    for value in y:
        tie_counts[value] = tie_counts.get(value, 0) + 1
    tie_term = sum(t * (t - 1) * (2 * t + 5) for t in tie_counts.values() if t > 1)
    variance = (n * (n - 1) * (2 * n + 5) - tie_term) / 18.0
    if variance <= 0:
        return 1.0  # every value identical: no evidence of any trend

    if s > 0:
        z = (s - 1) / math.sqrt(variance)
    elif s < 0:
        z = (s + 1) / math.sqrt(variance)
    else:
        z = 0.0
    return 2.0 * (1.0 - NormalDist().cdf(abs(z)))


def trend(years: Sequence[int], values: Sequence[float]) -> Trend | None:
    """Trend of a yearly series, or ``None`` when there are too few years to say anything."""
    if len(years) != len(values):
        raise ValueError("years and values must have the same length")
    if len(years) < MIN_YEARS_FOR_TREND:
        return None
    slope_per_year = theil_sen_slope([float(year) for year in years], values)
    return Trend(
        slope_per_decade=slope_per_year * 10.0,
        p_value=mann_kendall_p_value(values),
        years=len(years),
    )


@dataclass(frozen=True, slots=True)
class Summary:
    """Distribution of one indicator over the analysed years.

    The 20th and 80th percentiles are reported, as in the Atlas agroclimatique du Québec:
    a value at the 20th percentile was reached or exceeded in about 8 years out of 10.
    """

    count: int
    mean: float
    median: float
    p20: float
    p80: float
    minimum: float
    maximum: float
    standard_deviation: float
    trend: Trend | None


def summarize(years: Sequence[int], values: Sequence[float]) -> Summary | None:
    """Summary of a yearly series, or ``None`` when no year has a value."""
    if len(years) != len(values):
        raise ValueError("years and values must have the same length")
    if not values:
        return None
    return Summary(
        count=len(values),
        mean=fmean(values),
        median=median(values),
        p20=percentile(values, 0.2),
        p80=percentile(values, 0.8),
        minimum=min(values),
        maximum=max(values),
        standard_deviation=pstdev(values),
        trend=trend(years, values),
    )
