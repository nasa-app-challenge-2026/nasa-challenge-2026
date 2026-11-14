"""Step 4: find the places that already had, between 2011 and 2024, the climate the farm will have.

The grid is made of NASA POWER cells (about 0.5°, ~50 km); only cultivated cells covered by crop
maps can be twins.

Short term: one target climate → the 10 closest cells. Long term: one search per climate model,
the twins of all models brought together; a cell found by several models keeps its smallest sigma
and the list of those models (one arrow per model on the map of the app).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

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


@dataclass(frozen=True, eq=False)
class GridCell:
    """A cell of the grid with its observed climate (computed once for all cycles)."""

    id: str
    lat: float
    lon: float
    cultivated: bool
    indicators: IndicatorTable


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
    ) -> None:
        self._cells = list(cells)
        self._twins_per_target = twins_per_target
        self._cultivated = np.array([cell.cultivated for cell in self._cells])
        # (years, cells, indicators)
        self._observed = np.stack(
            [cell.indicators.between(period.first, period.last).rows for cell in self._cells],
            axis=1,
        )

    def closest_cells(self, target_rows: np.ndarray) -> list[Twin]:
        """The closest cultivated cells to one target climate, closest first."""
        sigma = sigma_dissimilarities(target_rows, self._observed)
        sigma = np.where(self._cultivated, sigma, np.inf)
        closest = np.argsort(sigma, kind="stable")[: self._twins_per_target]
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
