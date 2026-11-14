"""A candidate rotation: the crops that follow each other on a field, month by month.

A rotation is a cycle of *phases*. A phase is either a crop that holds the field for some months,
or bare soil between two crops. The cycle repeats for the whole simulation.

Two ways to write a step of a rotation:
  - only the crop: it holds the field for its usual season and the soil is bare until the end of
    the year. A rotation with one crop a year is then just a list of crops:
    maize, soybean, winter wheat  →  3 years;
  - the crop and its months: the phase lasts exactly that long and nothing is added. This is how
    double crops, cover crops and bare soil windows are written:
    winter wheat 10 months, rye (cover) 8 months, maize 6 months  →  2 years.

Every measure of the ranking (yield, water, soil protection, pests) reads the same `Rotation`.
"""

from __future__ import annotations

import math
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from itertools import product

from field_shift.reference.crops import crop_name
from field_shift.reference.planning import MONTHS_PER_YEAR
from field_shift.reference.soil_protection import (
    CoverKind,
    SoilProtectionProfile,
    crop_id_of,
    default_phase_months,
    soil_protection_profile,
)

#: Durations are compared with this tolerance (months).
MONTH_TOLERANCE = 1e-9


@dataclass(frozen=True)
class RotationStep:
    """One step of a rotation as the user writes it.

    crop    a crop id or a sheet id; None for bare soil
    months  how long it lasts; None to let the crop take its usual season, then leave the soil
            bare until the end of the year (not allowed for bare soil: its duration must be given)
    """

    crop: str | None
    months: float | None = None


@dataclass(frozen=True)
class RotationPhase:
    """A stretch of time of the cycle with one state of the field.

    crop_id  the crop in place, or None for bare soil
    months   duration of the phase
    """

    crop_id: str | None
    months: float

    @property
    def is_bare(self) -> bool:
        """True when nothing grows: bare soil between two crops, or a tilled fallow."""
        return self.crop_id is None or self.profile.kind is CoverKind.FALLOW

    @property
    def profile(self) -> SoilProtectionProfile | None:
        """The soil protection sheet of the crop in place (None for bare soil)."""
        return None if self.crop_id is None else soil_protection_profile(self.crop_id)

    def shortened_to(self, months: float) -> RotationPhase:
        """The same phase cut to `months` (the last phase of a simulation)."""
        return RotationPhase(self.crop_id, months)


@dataclass(frozen=True)
class Rotation:
    """A cycle of phases, with an id and a name for the reports."""

    id: str
    name: str
    phases: tuple[RotationPhase, ...]

    @classmethod
    def from_steps(
        cls, rotation_id: str, steps: Sequence[RotationStep], name: str = ""
    ) -> Rotation:
        """Builds the cycle from the steps the user wrote (see the module documentation).

        Raises ValueError (message in French, shown to the user) when the rotation is empty, has
        no crop, a crop is unknown, a duration is not positive or bare soil has no duration.
        """
        phases: list[RotationPhase] = []
        for step in steps:
            phases.extend(_phases_of_step(step))
        phases = _merged(phases)
        if not any(phase.crop_id is not None for phase in phases):
            raise ValueError("une rotation doit contenir au moins une culture")
        return cls(rotation_id, name or rotation_label(phases), tuple(phases))

    @property
    def cycle_months(self) -> float:
        """Duration of one cycle."""
        return sum(phase.months for phase in self.phases)

    @property
    def cycle_years(self) -> float:
        return self.cycle_months / MONTHS_PER_YEAR

    @property
    def crop_ids(self) -> tuple[str, ...]:
        """The crops of the cycle, in order, without the bare soil."""
        return tuple(phase.crop_id for phase in self.phases if phase.crop_id is not None)

    def timeline(self, simulation_months: float) -> tuple[RotationPhase, ...]:
        """The phases the field goes through during a simulation of `simulation_months`.

        The cycle is repeated from its first phase; the phase running when the simulation ends is
        cut there. A simulation shorter than the cycle only sees its first phases: this is why
        the same rotation can score differently over 3 and over 12 years.
        """
        if simulation_months <= 0:
            raise ValueError("la durée de la simulation doit être positive")
        phases: list[RotationPhase] = []
        remaining = simulation_months
        for phase in self._endless_phases():
            if remaining <= MONTH_TOLERANCE:
                break
            months = min(phase.months, remaining)
            phases.append(phase if months == phase.months else phase.shortened_to(months))
            remaining -= months
        return tuple(phases)

    def _endless_phases(self) -> Iterator[RotationPhase]:
        while True:
            yield from self.phases


def _phases_of_step(step: RotationStep) -> list[RotationPhase]:
    """The phase of a step and, when its duration is left to the crop, the bare soil after it."""
    if step.months is not None and step.months <= 0:
        raise ValueError("la durée d’une phase doit être positive")
    if step.crop is None:
        if step.months is None:
            raise ValueError("une phase de sol nu doit donner sa durée (months)")
        return [RotationPhase(None, step.months)]
    try:
        crop_id = crop_id_of(step.crop)
    except KeyError:
        raise ValueError(f"culture inconnue : {step.crop}") from None
    if step.months is not None:
        return [RotationPhase(crop_id, step.months)]
    months = default_phase_months(step.crop)
    years = math.ceil(months / MONTHS_PER_YEAR - MONTH_TOLERANCE)
    bare_months = years * MONTHS_PER_YEAR - months
    phases = [RotationPhase(crop_id, months)]
    if bare_months > MONTH_TOLERANCE:
        phases.append(RotationPhase(None, bare_months))
    return phases


def _merged(phases: Sequence[RotationPhase]) -> list[RotationPhase]:
    """Neighbouring phases in the same state become one (alfalfa, alfalfa → alfalfa for 2 years):
    a perennial kept several years is one stand, not a new sowing every year."""
    merged: list[RotationPhase] = []
    for phase in phases:
        if merged and merged[-1].crop_id == phase.crop_id:
            merged[-1] = RotationPhase(phase.crop_id, merged[-1].months + phase.months)
        else:
            merged.append(phase)
    return merged


def _phase_label(phase: RotationPhase) -> str:
    """The name of the crop of a phase, with its years when it stays several ("Luzerne ×3")."""
    years = phase.months / MONTHS_PER_YEAR
    name = crop_name(phase.crop_id)
    if years >= 2 and abs(years - round(years)) < MONTH_TOLERANCE:
        return f"{name} ×{round(years)}"
    return name


def rotation_label(phases: Sequence[RotationPhase]) -> str:
    """ "Luzerne ×3 → Maïs → Blé d’automne": the crops of a cycle, in order."""
    return " → ".join(_phase_label(phase) for phase in phases if phase.crop_id is not None)


def _is_first_of_its_cycle(sequence: tuple[str, ...]) -> bool:
    """True for one sequence only among those that are the same cycle started at another crop
    (maize, soybean, wheat = soybean, wheat, maize)."""
    turns = (sequence[i:] + sequence[:i] for i in range(1, len(sequence)))
    return all(sequence <= turn for turn in turns)


def generate_rotations(crops: Sequence[str], cycle_years: int, limit: int) -> list[Rotation]:
    """Every rotation of `cycle_years` years with one of `crops` each year.

    Used when the user gives crops and a cycle length instead of writing the rotations. The same
    cycle started at another crop is given once. The rotations come in the order of `crops`
    (the first crops first), and get the ids "R1", "R2"...

    Raises ValueError when there would be more than `limit` rotations: the user must then select
    fewer crops, shorten the cycle or write the rotations himself.
    """
    distinct = list(dict.fromkeys(crops))
    if not distinct:
        raise ValueError("aucune culture sélectionnée pour générer les rotations")
    if cycle_years < 1:
        raise ValueError("la durée du cycle doit être d’au moins un an")
    rotations: list[Rotation] = []
    for sequence in product(distinct, repeat=cycle_years):
        if not _is_first_of_its_cycle(sequence):
            continue
        if len(rotations) >= limit:
            raise ValueError(
                f"plus de {limit} rotations possibles avec {len(distinct)} cultures sur "
                f"{cycle_years} ans : réduisez la sélection ou donnez les rotations à comparer"
            )
        steps = [RotationStep(crop) for crop in sequence]
        rotations.append(Rotation.from_steps(f"R{len(rotations) + 1}", steps))
    return rotations
