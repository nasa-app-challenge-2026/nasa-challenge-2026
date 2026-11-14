"""Small numeric helpers shared by the algorithm."""

from __future__ import annotations


def clamp01(value: float) -> float:
    """Bound a number to the range 0..1."""
    return min(1.0, max(0.0, value))


def percent_change(value: float, reference: float) -> float:
    """Change in percent of `value` compared with `reference`."""
    return 100 * (value / reference - 1)
