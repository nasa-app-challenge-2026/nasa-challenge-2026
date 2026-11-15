"""Step 4: find the places that already had, between 2011 and 2024, the climate the farm will have.

The grid is made of NASA POWER cells (about 0.5°, ~50 km); only cultivated cells covered by crop
maps can be twins.

Whether a cell is cultivated can be known when the grid is built (`GridCell.cultivated`), or asked
to the crop maps only for the cells that are candidates (`cultivation`): the closest cells are
checked, in order of sigma, until 10 cultivated ones are found. Reading the crop maps of the
hundreds of cells of a grid would take minutes; the twins only need a few dozen.

Short term: one target climate → the 10 closest cells. Long term: one search per climate model,
the twins of all models brought together; a cell found by several models keeps its smallest sigma
and the list of those models (one arrow per model on the map of the app).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Final

import numpy as np

from field_shift.algorithm.climate.indicator_table import IndicatorTable
from field_shift.algorithm.climate.target_climate_projector import ClimateTarget
from field_shift.algorithm.config.climate import (
    GOOD_TWIN_MAX_SIGMA,
    TWIN_PERIOD,
    TWINS_PER_TARGET,
    YearRange,
)
from field_shift.algorithm.twins.sigma_dissimilarity import sigma_dissimilarities

#: Cells whose cultivation is unknown are checked this many at a time (in parallel by the data
#: layer), closest first.
CULTIVATION_BATCH: Final = 8


@dataclass(frozen=True, eq=False)
class GridCell:
    """A cell of the grid with its observed climate (computed once for all cycles).

    `cultivated` is None while it is not known (asked to `cultivation` when needed)."""

    id: str
    lat: float
    lon: float
    cultivated: bool | None
    indicators: IndicatorTable


#: Says which of these cells are cultivated (one answer per cell, in the same order).
CultivationCheck = Callable[[Sequence[GridCell]], Sequence[bool]]


@dataclass
class Twin:
    """A cell that looks like the target climate; `sources` = what it was found for."""

    cell: GridCell
    sigma: float
    sources: list[str] = field(default_factory=list)


def is_good_twin(sigma: float) -> bool:
    """σ ≤ 2: the target climate exists somewhere; beyond, the advice is less reliable."""
    return sigma <= GOOD_TWIN_MAX_SIGMA


class ClimateTwinFinder:
    """Searches the twins of target climates in a grid of observed climates."""

    def __init__(
        self,
        cells: Sequence[GridCell],
        period: YearRange = TWIN_PERIOD,
        twins_per_target: int = TWINS_PER_TARGET,
        cultivation: CultivationCheck | None = None,
    ) -> None:
        self._cells = list(cells)
        self._twins_per_target = twins_per_target
        self._cultivation = cultivation
        #: True / False once known, None until the crop maps are asked.
        self._known: list[bool | None] = [cell.cultivated for cell in self._cells]
        if cultivation is None and any(known is None for known in self._known):
            raise ValueError("une case sans culture connue demande une vérification (cultivation)")
        # (years, cells, indicators)
        self._observed = np.stack(
            [cell.indicators.between(period.first, period.last).rows for cell in self._cells],
            axis=1,
        )

    def _is_cultivated(self, index: int, order: Sequence[int], position: int) -> bool:
        """Is the cell cultivated? Unknown: this cell and the next unknown ones (in `order`, from
        `position`) are checked together."""
        if self._known[index] is None:
            batch = [i for i in order[position:] if self._known[i] is None][:CULTIVATION_BATCH]
            answers = list(self._cultivation([self._cells[i] for i in batch]))  # type: ignore[misc]
            if len(answers) != len(batch):
                raise ValueError("la vérification des cultures doit répondre pour chaque case")
            for i, answer in zip(batch, answers, strict=True):
                self._known[i] = bool(answer)
        return bool(self._known[index])

    def closest_cells(self, target_rows: np.ndarray) -> list[Twin]:
        """The closest cultivated cells to one target climate, closest first."""
        sigma = sigma_dissimilarities(target_rows, self._observed)
        order = [int(i) for i in np.argsort(sigma, kind="stable")]
        closest: list[int] = []
        for position, index in enumerate(order):
            if len(closest) == self._twins_per_target:
                break
            if self._is_cultivated(index, order, position):
                closest.append(index)
        return [Twin(self._cells[i], float(sigma[i])) for i in closest]

    def twins_of(self, targets: Sequence[ClimateTarget]) -> list[Twin]:
        """The twins of every target climate brought together, smallest sigma first."""
        found: dict[str, Twin] = {}
        for target in targets:
            for twin in self.closest_cells(target.indicators.rows):
                known = found.get(twin.cell.id)
                if known is None:
                    found[twin.cell.id] = Twin(twin.cell, twin.sigma, [target.source])
                else:
                    known.sigma = min(known.sigma, twin.sigma)
                    known.sources.append(target.source)
        return sorted(found.values(), key=lambda twin: twin.sigma)
