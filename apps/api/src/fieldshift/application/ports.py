"""Contracts the application needs from the outside world.

Implementations live in ``fieldshift.infrastructure`` and are wired in the composition root
(``fieldshift.api.dependencies``). Tests substitute in-memory fakes.
"""

from __future__ import annotations

from typing import Protocol

from fieldshift.domain.geo import GeoPoint, GridCell
from fieldshift.domain.provenance import ClimateDataset


class HistoricalClimateProvider(Protocol):
    """Daily historical climate for a location.

    Implementations raise ``ClimateDataUnavailableError`` when no trustworthy data can be
    returned, and never fabricate values.
    """

    @property
    def first_available_year(self) -> int: ...

    @property
    def spatial_resolution(self) -> str: ...

    def grid_cell(self, location: GeoPoint) -> GridCell: ...

    def daily_history(self, location: GeoPoint, first_year: int, last_year: int) -> ClimateDataset:
        """Daily records from 1 January ``first_year`` to 31 December ``last_year``."""
        ...
