"""Step 9b, the candidate crops of a cycle.

- a sold crop is a candidate only if it is grown in the twins of the cycle;
- a crop that needs equipment the farmer does not have is removed;
- in "reserve only" mode, only the seeds of the reserve (plus fallow);
- with one crop a year, rye is not a candidate: it is placed automatically between two crops
  (see `cover_crop_planner.py`);
- a crop whose minimum return delay does not fit in the cycle is removed, with a message.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from field_shift.algorithm.delays.return_delay_catalog import ReturnDelayCatalog
from field_shift.algorithm.delays.return_delay_checker import ImpossibleCrop, impossible_crops
from field_shift.algorithm.planning.farmer_profile import FarmerProfile
from field_shift.algorithm.twins.twin_evidence import TwinEvidence
from field_shift.reference.crops import CROP_SHEETS, Role
from field_shift.reference.planning import MONTHS_PER_YEAR, ReserveMode


@dataclass(frozen=True)
class Candidates:
    """The sheets that may fill a position (in sheet order), and the crops removed with why."""

    sheet_ids: tuple[str, ...]
    removed: dict[str, ImpossibleCrop]


def candidate_sheets(
    evidence: TwinEvidence,
    farmer: FarmerProfile,
    frequency_months: int,
    cycle_years: int,
    diseases: Sequence[str],
    catalog: ReturnDelayCatalog,
) -> Candidates:
    allowed = [
        sheet
        for sheet in CROP_SHEETS
        if not (sheet.role is Role.COVER and frequency_months >= MONTHS_PER_YEAR)
        and not (sheet.role is Role.SOLD and not evidence.is_grown(sheet.crop_id))
        and not (sheet.equipment and sheet.equipment in farmer.missing_equipment)
        and not (
            farmer.reserve_mode is ReserveMode.ONLY
            and sheet.role is not Role.FALLOW
            and sheet.seed_id not in farmer.seeds
        )
    ]
    removed = impossible_crops(
        cycle_years, [s for s in allowed if s.role is Role.SOLD], diseases, catalog
    )
    return Candidates(
        sheet_ids=tuple(s.id for s in allowed if s.id not in removed),
        removed=removed,
    )
