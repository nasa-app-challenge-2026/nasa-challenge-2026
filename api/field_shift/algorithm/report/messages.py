"""French messages of the plan, built from the structured results of the algorithm.

Kept apart so that the algorithm returns data and the wording lives in one place. No message names
a study: studies only appear on the sources page of the app (team rule).
"""

from __future__ import annotations

from field_shift.algorithm.delays.return_delay_checker import (
    DelayViolation,
    ImpossibleCrop,
    SharedDiseaseWarning,
)
from field_shift.algorithm.delays.return_delay_rules import RuleKind, RuleReason
from field_shift.reference.crops import SHEETS, crop_name
from field_shift.reference.return_delays import SOIL_DISEASES


def disease_name(disease_id: str) -> str:
    disease = SOIL_DISEASES.get(disease_id)
    return disease.name if disease else disease_id


def rule_reason_text(reason: RuleReason) -> str:
    """ "Soya après Soya", "même famille (Fabacées) : Luzerne après Soya"…"""
    pair = f"{crop_name(reason.next)} après {crop_name(reason.previous)}"
    if reason.kind is RuleKind.SAME_FAMILY:
        return f"même famille ({reason.family}) : {pair}"
    if reason.kind is RuleKind.DISEASE:
        return f"{disease_name(reason.disease or '')} présente : {pair}"
    return pair


def violation_text(violation: DelayViolation) -> str:
    """ "Soya après Soya : 2025 puis 2027, 1 an(s) sans, minimum 2"."""
    return (
        f"{rule_reason_text(violation.reason)} : {violation.start.year} puis {violation.end.year}, "
        f"{violation.years_without} an(s) sans, minimum {violation.minimum}"
    )


def shared_disease_text(warning: SharedDiseaseWarning) -> str:
    """Warning about a soil disease shared by two crops of different families."""
    return (
        f"{crop_name(warning.next)} {warning.years_without} an(s) après "
        f"{crop_name(warning.previous)} : tous deux hôtes de la {disease_name(warning.disease)} "
        f"({warning.advised} ans sans hôte conseillés si elle apparaît)."
    )


def impossible_text(sheet_id: str, impossible: ImpossibleCrop, cycle_years: int) -> str:
    """Why a crop cannot come back every cycle."""
    sheet = SHEETS[sheet_id]
    what = "peuplements" if sheet.is_perennial else "récoltes"
    return (
        f"{sheet.name} demande {impossible.required} an(s) sans {crop_name(sheet.crop_id).lower()} "
        f"entre deux {what} ; un cycle de {cycle_years} ans n’en laisse que {impossible.possible}. "
        f"Il faudrait un cycle d’au moins {impossible.required + impossible.occupied_years} ans."
    )


def succession_text(previous: str, next_crop: str) -> str:
    """ "Blé d’automne → Sarrasin" (a succession whose precrop value is unknown)."""
    return f"{crop_name(previous)} → {crop_name(next_crop)}"
