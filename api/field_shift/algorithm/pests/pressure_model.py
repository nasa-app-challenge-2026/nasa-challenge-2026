"""The pressure of one organism in a field, year after year.

P(t) is between 0 and 1 at the start of the year t. A year with a host crop raises it; a year
without one lowers it. The delay published for the organism (years without a host) sets the rate:

    host year      P(t + 1) = min(1, P(t) + g × s)     s = sensitivity of the best host of the year
    no host year   P(t + 1) = P(t) × d,    d = ε ^ (1 / L)

so that after L years without a host, a full pressure falls to ε (0.1 = 90 % gone). It is a single
exponential: a delay of 4 years gives a pressure that halves in about a year, which is what the
soybean cyst nematode does under a non-host crop. It does not give the two speeds of the clubroot
spores (most of them gone in 2 years, the rest very durable).

A pure function: crops of the timeline in, pressure out. Nothing here knows the criterion.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PressureState:
    """The pressure at the start of a year, and the last crop that raised it (None: nothing on
    the timeline did, the farmer declared the disease)."""

    pressure: float
    last_host: tuple[str, int] | None = None  # (crop id, year of that crop)


def decay_per_year(years_without_host: int, acceptable: float) -> float:
    """Share of the pressure left after one year without a host."""
    if years_without_host <= 0:
        raise ValueError("an organism needs at least one year without a host")
    return acceptable ** (1.0 / years_without_host)


def pressure_by_year(
    host_years: Mapping[int, tuple[float, str]],
    first_year: int,
    last_year: int,
    years_without_host: int,
    acceptable: float,
    growth: float,
    start: float = 0.0,
    floor_at: Mapping[int, float] | None = None,
) -> dict[int, PressureState]:
    """The pressure at the start of every year from `first_year` to `last_year + 1`.

    host_years  year → (sensitivity, crop id) of the best host that grows that year
    start       the pressure at the start of `first_year`
    floor_at    year → pressure the field has at least at the start of that year (a disease the
                farmer declared: the soil is infected now)
    """
    decay = decay_per_year(years_without_host, acceptable)
    states: dict[int, PressureState] = {}
    pressure, last_host = start, None
    for year in range(first_year, last_year + 2):
        if floor_at is not None and floor_at.get(year, 0.0) > pressure:
            pressure, last_host = floor_at[year], None  # declared: no crop of the timeline did it
        states[year] = PressureState(pressure, last_host)
        host = host_years.get(year)
        if host is None:
            pressure *= decay
        else:
            sensitivity, crop_id = host
            pressure = min(1.0, pressure + growth * sensitivity)
            last_host = (crop_id, year)
    return states
