"""Where a kind of data of the plan comes from (shown to the farmer)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DataSource:
    """A kind of data (`key`), whether it is real, and a label for the farmer."""

    key: str
    real: bool
    label: str
