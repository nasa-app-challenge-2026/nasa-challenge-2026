"""Bibliographic references cited by thresholds, formulas and explanations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class Reference:
    id: str
    citation: str
    url: str | None
    accessed: date | None
    terms_fr: str
    """Licence or terms of use, as checked when the reference was added."""
    used_for_fr: str
