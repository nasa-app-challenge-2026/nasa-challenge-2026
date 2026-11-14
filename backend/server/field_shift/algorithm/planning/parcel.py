"""A field (parcelle) as the algorithm sees it (step 1, block A).

The crop in place and when it is harvested (or ends, for a perennial), the crops of the previous
years, the rotation the farmer started and where he is in it, the soil diseases he knows, and the
diagnostic of the field (irrigation and satellite measures, step 8).
"""

from __future__ import annotations

from dataclasses import dataclass

from field_shift.algorithm.delays.field_history import PastCrop
from field_shift.algorithm.diagnostic.parcel_diagnostic import ParcelDiagnostic
from field_shift.reference.crops import FALLOW_SHEET_ID, SHEETS, Role


@dataclass(frozen=True)
class Parcel:
    """One field.

    in_place          crop in place: a sheet id (or another crop id), None = free
    in_place_harvest  absolute month of its harvest / end, None = free now
    past              crops of the previous years
    current_rotation  sheet ids of the rotation the farmer started
    rotation_position index of the crop in place in that rotation
    diseases          declared soil diseases
    """

    id: str
    diagnostic: ParcelDiagnostic
    in_place: str | None = None
    in_place_harvest: float | None = None
    past: tuple[PastCrop, ...] = ()
    current_rotation: tuple[str, ...] = ()
    rotation_position: int = 0
    diseases: tuple[str, ...] = ()

    @property
    def in_place_sheet_id(self) -> str | None:
        """The crop in place as a sold sheet (the entry of the first cycle), or None."""
        sheet = SHEETS.get(self.in_place or "")
        return sheet.id if sheet and sheet.role is Role.SOLD else None

    @property
    def repeats_in_place_crop(self) -> bool:
        """Without a current rotation, the reference repeats the crop in place (the app says so)."""
        return not self.current_rotation

    def reference_sequence(self, length: int) -> list[str]:
        """The farmer's rotation continued from the crop after the one in place: the reference the
        plan is compared with."""
        rotation = self.current_rotation or (self.in_place_sheet_id or FALLOW_SHEET_ID,)
        return [rotation[(self.rotation_position + 1 + i) % len(rotation)] for i in range(length)]
