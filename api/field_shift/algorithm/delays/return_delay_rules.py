"""Which return delays apply when crop `next` follows crop `previous`.

- the same crop: its own delay (minimum / recommended);
- another crop of the same family: never two years in a row (grasses exempted); the shorter
  recommended delay of the two counts in the pest criterion;
- a soil disease declared by the farmer that hosts both: its high value, compulsory
  (e.g. clubroot: 7 years without a crucifer).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from field_shift.algorithm.delays.return_delay_catalog import ReturnDelayCatalog


class RuleKind(StrEnum):
    SAME_CROP = "meme-culture"
    SAME_FAMILY = "meme-famille"
    DISEASE = "maladie"


#: Between two crops of a family, the hard constraint stays "not two years in a row".
SAME_FAMILY_MINIMUM: Final = 1


@dataclass(frozen=True)
class RuleReason:
    """Why a delay applies between two crops."""

    kind: RuleKind
    previous: str
    next: str
    family: str | None = None
    disease: str | None = None

    @property
    def key(self) -> tuple:
        """Same reason, same crops: reported once."""
        return (self.kind, self.disease, self.previous, self.next)


@dataclass(frozen=True)
class DelayRule:
    """A delay between two crops: years without the crop, at least and as advised."""

    minimum: int
    recommended: int
    reason: RuleReason


def delay_rules(
    catalog: ReturnDelayCatalog,
    previous: str,
    next_crop: str,
    declared_diseases: Sequence[str] = (),
) -> list[DelayRule]:
    """The delays that apply between two crops (empty if either is unknown to the tables)."""
    a, b = catalog.get(previous), catalog.get(next_crop)
    if a is None or b is None:
        return []
    rules: list[DelayRule] = []
    if a.id == b.id:
        rules.append(
            DelayRule(a.minimum, a.recommended, RuleReason(RuleKind.SAME_CROP, a.id, b.id))
        )
    elif a.family == b.family and not catalog.is_exempt_family(a.family):
        rules.append(
            DelayRule(
                minimum=min(SAME_FAMILY_MINIMUM, a.minimum, b.minimum),
                recommended=min(a.recommended, b.recommended),
                reason=RuleReason(RuleKind.SAME_FAMILY, a.id, b.id, family=a.family),
            )
        )
    for disease in declared_diseases:
        info = catalog.diseases.get(disease)
        if info and a.id in info.hosts and b.id in info.hosts:
            rules.append(
                DelayRule(
                    minimum=info.high,
                    recommended=info.high,
                    reason=RuleReason(RuleKind.DISEASE, a.id, b.id, disease=disease),
                )
            )
    return rules
