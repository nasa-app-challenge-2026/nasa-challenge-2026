"""From the wire format (FarmInput) to the objects of the algorithm: time settings, farmer profile,
fields."""

from __future__ import annotations

from dataclasses import dataclass

from field_shift.algorithm.delays.field_history import PastCrop
from field_shift.algorithm.diagnostic.parcel_diagnostic import ParcelDiagnostic
from field_shift.algorithm.planning.farmer_profile import FarmerProfile
from field_shift.algorithm.planning.parcel import Parcel
from field_shift.algorithm.planning.time_settings import TimeSettings
from field_shift.algorithm.sources.field_data import FieldData, FieldDataSource
from field_shift.algorithm.timeline import month_time
from field_shift.algorithm.twins.soil_comparison import Soil
from field_shift.contract.farm_input import FarmInput, SectionInput


@dataclass(frozen=True)
class FarmContext:
    """A farm request, read: what the algorithm needs to plan every section."""

    time: TimeSettings
    farmer: FarmerProfile
    parcels: list[Parcel]
    field_data: dict[str, FieldData]


def harvest_time(year_month: str) -> float:
    """ "2026-10" → absolute time (the middle of October 2026)."""
    year, month = year_month.split("-")
    return month_time.of_year_month(int(year), int(month))


def _soil_of(section: SectionInput) -> Soil | None:
    test = section.soil_test
    return (
        None if test is None else Soil(test.clay_pct, test.sand_pct, test.organic_carbon, test.ph)
    )


def _parcel_of(section: SectionInput, data: FieldData) -> Parcel:
    in_harvest = section.current_harvest if section.current_crop else None
    return Parcel(
        id=section.id,
        diagnostic=ParcelDiagnostic(data.measures, irrigated=section.irrigated),
        in_place=section.current_crop,
        in_place_harvest=harvest_time(in_harvest) if in_harvest else None,
        past=tuple(PastCrop(h.year, h.crop) for h in section.history if h.crop),
        current_rotation=tuple(section.current_rotation),
        rotation_position=section.rotation_position,
        diseases=tuple(section.diseases),
    )


def read_farm_input(farm_input: FarmInput, field_data_source: FieldDataSource) -> FarmContext:
    farm = farm_input.farm
    field_data = {
        s.id: field_data_source.field_data(s.id, _soil_of(s)) for s in farm_input.sections
    }
    return FarmContext(
        time=TimeSettings(
            farm.time.cycle_years, farm.time.frequency_months, farm.time.horizon_years
        ),
        farmer=FarmerProfile(
            ranking=tuple(farm.priorities),
            livestock=farm.livestock,
            missing_equipment=frozenset(farm.missing_equipment),
            seeds=frozenset(farm.seeds.crops),
            reserve_mode=farm.seeds.mode,
        ),
        parcels=[_parcel_of(s, field_data[s.id]) for s in farm_input.sections],
        field_data=field_data,
    )
