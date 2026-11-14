"""Return delay of every crop, derived from the two sources (Fruchtfolge, SARE).

    minimum (hard constraint)         = the smaller of the two values
    recommended (pest criterion)      = the larger
With a single source, the minimum is 1 year (never two years in a row).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from field_shift.reference.return_delays import (
    CROP_DELAYS,
    DELAY_ALIASES,
    EXEMPT_FAMILIES,
    SOIL_DISEASES,
    CropDelayRow,
    SoilDisease,
)

#: With a single source, a crop must still skip one year.
SINGLE_SOURCE_MINIMUM: Final = 1


@dataclass(frozen=True)
class CropDelay:
    """Years without the crop before it may come back, and the soil diseases it hosts."""

    id: str
    family: str
    minimum: int
    recommended: int
    perennial: bool
    diseases: tuple[str, ...]


class ReturnDelayCatalog:
    """The return delays of every crop of the reference tables."""

    def __init__(
        self,
        crops: Mapping[str, CropDelayRow] = CROP_DELAYS,
        diseases: Mapping[str, SoilDisease] = SOIL_DISEASES,
        aliases: Mapping[str, str] = DELAY_ALIASES,
    ) -> None:
        self.diseases = dict(diseases)
        self._aliases = dict(aliases)
        self._exempt_families = EXEMPT_FAMILIES
        self._delays = {crop_id: self._derive(crop_id, row) for crop_id, row in crops.items()}

    def _derive(self, crop_id: str, row: CropDelayRow) -> CropDelay:
        sare = self.diseases[row.reference_disease].low if row.reference_disease else None
        values = [v for v in (row.fruchtfolge_years_without, sare) if v is not None]
        if len(values) == 2:
            minimum = min(values)
        elif values:
            minimum = min(SINGLE_SOURCE_MINIMUM, values[0])
        else:
            minimum = SINGLE_SOURCE_MINIMUM
        return CropDelay(
            id=crop_id,
            family=row.family,
            minimum=minimum,
            recommended=max(values) if values else minimum,
            perennial=row.perennial,
            diseases=tuple(d for d, info in self.diseases.items() if crop_id in info.hosts),
        )

    def species_of(self, crop_id: str) -> str:
        """The crop whose delays apply (double-crop soybean = soybean)."""
        return self._aliases.get(crop_id, crop_id)

    def get(self, crop_id: str) -> CropDelay | None:
        return self._delays.get(self.species_of(crop_id))

    def is_exempt_family(self, family: str) -> bool:
        return family in self._exempt_families

    def declared_disease_delay(self, crop_id: str, declared_diseases: Sequence[str]) -> int:
        """Years without a host required by a declared disease for this crop (0 if none)."""
        species = self.species_of(crop_id)
        return max(
            (
                self.diseases[d].high
                for d in declared_diseases
                if d in self.diseases and species in self.diseases[d].hosts
            ),
            default=0,
        )


DEFAULT_DELAY_CATALOG: Final = ReturnDelayCatalog()
