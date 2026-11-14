"""A chain = the crops that fill the N positions of a cycle, in order.

Each step is one sheet sown at `sowing` and harvested at `harvest` (absolute months), from position
`first_position` to `last_position` (relative to the cycle). A fallow step has no sowing: its
harvest is the previous harvest. Cover crops placed between two steps have no position.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from field_shift.algorithm.delays.occupation import Occupation
from field_shift.algorithm.delays.return_delay_catalog import ReturnDelayCatalog
from field_shift.algorithm.timeline import month_time
from field_shift.reference.crops import FALLOW_SHEET_ID, SHEETS, CropSheet, Role


@dataclass(frozen=True, slots=True)
class ChainStep:
    sheet_id: str
    sowing: float | None
    harvest: float
    first_position: int | None = None
    last_position: int | None = None

    @property
    def sheet(self) -> CropSheet:
        return SHEETS[self.sheet_id]

    @property
    def is_sold(self) -> bool:
        return self.sheet.role is Role.SOLD

    @property
    def is_fallow(self) -> bool:
        return self.sheet_id == FALLOW_SHEET_ID

    @property
    def is_cover(self) -> bool:
        """A cover crop sits between two steps and holds no position."""
        return self.first_position is None


Chain = Sequence[ChainStep]


def fallow_step(previous_harvest: float, position: int) -> ChainStep:
    """A position left without crop: nothing is sown, the harvest time does not move."""
    return ChainStep(FALLOW_SHEET_ID, None, previous_harvest, position, position)


def sheet_ids(chain: Chain) -> list[str]:
    """The sheet ids of the steps: the identity of a chain."""
    return [step.sheet_id for step in chain]


def last_harvest(chain: Chain) -> float:
    return chain[-1].harvest


def last_sold_sheet(chain: Chain, fallback: str | None = None) -> str | None:
    """The last sold sheet of a chain, or `fallback`."""
    return next((step.sheet_id for step in reversed(chain) if step.is_sold), fallback)


def to_occupations(chain: Chain, catalog: ReturnDelayCatalog) -> list[Occupation]:
    """The sold crops of a chain as occupations of the field (years), for the return delays: an
    annual crop counts for the year of its harvest, a perennial from the year it is sown to its
    last harvest."""
    occupations = []
    for step in chain:
        if not step.is_sold:
            continue
        sheet = step.sheet
        last_year = month_time.year_of(step.harvest)
        first_year = month_time.year_of(step.sowing) if sheet.is_perennial else last_year
        occupations.append(Occupation(catalog.species_of(sheet.crop_id), first_year, last_year))
    return occupations
