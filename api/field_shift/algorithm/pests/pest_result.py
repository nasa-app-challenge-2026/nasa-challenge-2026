"""What the "ravageurs" criterion gives back: its score and the way it was computed.

`pest_measure.py` turns it into the `MeasureResult` of the rotation ranking.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PestResult:
    """score        0 to 1, 1 = best
    details      sub-scores and figures of the calculation
    explanations sentences for the farmer
    confidence   0 to 1: share of the crops of the rotation the catalogue has an organism for
    """

    score: float
    details: dict[str, float] = field(default_factory=dict)
    explanations: list[str] = field(default_factory=list)
    confidence: float | None = None
