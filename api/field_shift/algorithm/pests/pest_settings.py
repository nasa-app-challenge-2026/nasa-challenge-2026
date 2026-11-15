"""Settings of the "ravageurs" criterion (pressure model, see README.md in this folder)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class PressureParams:
    """The settings of the pressure model.

    acceptable           ε: share of the pressure left after the recommended delay (0.1 = 90 % gone)
    growth               g: pressure gained by one year of a main host (1 = full in one year)
    first_pass_weight    weight of the cycle played with the real history, against the cycle that
                         repeats (the chain goes on): 0.5 = both count the same
    worst_case_weight    share of the worst organism (highest sensitivity × pressure) in the risk of
                         a crop, against the severity-weighted mean of all its organisms. 0 = the
                         mean only (README.md, "Dilution"); above 0, a crop with one organism at
                         full pressure is not diluted by the organisms that are absent
    explain_from_risk    risk from which a crop gets a sentence for the farmer
    warmup_cycles        copies of the cycle played before it when there is no history, to reach
                         the steady state of a chain that repeats
    """

    acceptable: float = 0.1
    growth: float = 1.0
    first_pass_weight: float = 0.5
    worst_case_weight: float = 0.0
    explain_from_risk: float = 0.25
    warmup_cycles: int = 4


DEFAULT_PRESSURE_PARAMS: Final = PressureParams()

#: Pressure from which it is called "élevée" / "moyenne" in the sentences (else "faible").
HIGH_PRESSURE: Final = 0.66
MEDIUM_PRESSURE: Final = 0.33
