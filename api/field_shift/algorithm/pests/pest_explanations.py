"""The sentences of the "ravageurs" criterion for the farmer (in French, like the reports)."""

from __future__ import annotations

from field_shift.algorithm.pests.pest_data import Pest
from field_shift.algorithm.pests.pest_settings import HIGH_PRESSURE, MEDIUM_PRESSURE
from field_shift.reference.crops import CROP_NAMES


def crop_name(crop_id: str) -> str:
    return CROP_NAMES.get(crop_id, crop_id)


def pressure_label(pressure: float) -> str:
    if pressure >= HIGH_PRESSURE:
        return "élevée"
    if pressure >= MEDIUM_PRESSURE:
        return "moyenne"
    return "faible"


def years_text(years: int) -> str:
    return f"{years} an" if years == 1 else f"{years} ans"


def exposure_sentence(
    crop_id: str,
    year: int,
    pest: Pest,
    pressure: float,
    last_host: tuple[str, int] | None,
    next_cycle: bool,
) -> str:
    """One sentence: the crop, the organism that threatens it most, and what raised it."""
    where = "Au cycle suivant, " if next_cycle else ""
    label = pressure_label(pressure)
    crop = f"{crop_name(crop_id)} {year}"
    if last_host is None:
        return (
            f"{where}{crop} : {pest.name}, pression {label} (maladie déclarée pour cette parcelle)."
        )
    host_crop, host_year = last_host
    gap = year - host_year - 1
    before = f"{crop_name(host_crop)} {host_year} puis {crop}"
    return (
        f"{where}{before} : {pest.name}, {years_text(max(gap, 0))} sans hôte pour "
        f"{pest.years_without_host} conseillés, pression {label}."
    )
