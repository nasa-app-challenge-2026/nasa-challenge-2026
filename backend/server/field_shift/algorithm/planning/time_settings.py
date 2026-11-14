"""Step 1, block C of the algorithm: the cycle (C years), the harvest frequency (f months) and the
horizon (a multiple of C)."""

from __future__ import annotations

from dataclasses import dataclass

from field_shift.reference.planning import (
    FREQUENCIES,
    MAX_CYCLE_YEARS,
    MIN_CYCLE_YEARS,
    MONTHS_PER_YEAR,
    Frequency,
)


def _frequency(months: int) -> Frequency | None:
    return next((f for f in FREQUENCIES if f.months == months), None)


@dataclass(frozen=True)
class TimeSettings:
    """How the plan is cut in time. Invalid settings raise a ValueError with a French message."""

    cycle_years: int
    frequency_months: int
    horizon_years: int

    def __post_init__(self) -> None:
        errors = self.errors(self.cycle_years, self.frequency_months, self.horizon_years)
        if errors:
            raise ValueError(" ".join(errors))

    @staticmethod
    def errors(cycle_years: int, frequency_months: int, horizon_years: int) -> list[str]:
        """Why these settings are not valid (empty list = valid)."""
        errors = []
        valid_cycle = MIN_CYCLE_YEARS <= cycle_years <= MAX_CYCLE_YEARS
        if not valid_cycle:
            errors.append(f"Le cycle doit durer de {MIN_CYCLE_YEARS} à {MAX_CYCLE_YEARS} ans.")
        frequency = _frequency(frequency_months)
        if frequency is None:
            months = ", ".join(str(f.months) for f in FREQUENCIES)
            errors.append(f"Fréquence : {months} mois.")
        elif valid_cycle and (MONTHS_PER_YEAR * cycle_years) % frequency_months:
            errors.append(f"{frequency_months} mois ne divise pas un cycle de {cycle_years} ans.")
        if horizon_years <= 0 or (valid_cycle and horizon_years % cycle_years):
            errors.append(
                f"L’horizon ({horizon_years} ans) doit être un multiple du cycle "
                f"({cycle_years} ans)."
            )
        return errors

    @property
    def positions_per_cycle(self) -> int:
        """N: number of positions (crops) in one cycle."""
        return MONTHS_PER_YEAR * self.cycle_years // self.frequency_months

    @property
    def cycle_count(self) -> int:
        return self.horizon_years // self.cycle_years

    @property
    def position_start_month(self) -> int:
        """Month (0-based) where the positions start: January (12 months) or February."""
        frequency = _frequency(self.frequency_months)
        assert frequency is not None  # checked in __post_init__
        return frequency.position_start_month
