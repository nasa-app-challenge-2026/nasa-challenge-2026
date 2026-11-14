"""The organisms of the rotation, indexed by crop, with their severity."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from field_shift.algorithm.pests.pest_data import PESTS, Pest


class PestCatalog:
    """The organisms that each crop hosts.

    severities  overrides of the severity of some organisms (id → weight), to test how much the
                result depends on them
    """

    def __init__(
        self,
        pests: Mapping[str, Pest] = PESTS,
        severities: Mapping[str, float] | None = None,
    ) -> None:
        self.pests = dict(pests)
        self._severities = dict(severities or {})
        self._by_crop: dict[str, list[Pest]] = {}
        for pest in self.pests.values():
            for host in pest.hosts:
                if host.sensitivity > 0:
                    self._by_crop.setdefault(host.crop_id, []).append(pest)

    def pests_of(self, crop_id: str) -> tuple[Pest, ...]:
        """The organisms the crop is a host of (empty: nothing is known about it)."""
        return tuple(self._by_crop.get(crop_id, ()))

    def severity(self, pest: Pest) -> float:
        return self._severities.get(pest.id, pest.severity)

    def weight(self, pest: Pest, crop_id: str) -> float:
        """Weight of the organism in the risk of the crop: severity × sensitivity."""
        return self.severity(pest) * pest.sensitivity_of(crop_id)


DEFAULT_PEST_CATALOG: Final = PestCatalog()
