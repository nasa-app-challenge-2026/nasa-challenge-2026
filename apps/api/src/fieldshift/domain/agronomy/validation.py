"""Structural rules a rotation must respect before it can be evaluated."""

from __future__ import annotations

from fieldshift.domain.agronomy.crops import CropCatalog, CropCategory
from fieldshift.domain.agronomy.farm import CropRotation


class InvalidRotationError(ValueError):
    """The rotation cannot be evaluated as described. The message is shown to the user."""


def validate_rotation(rotation: CropRotation, catalog: CropCatalog) -> None:
    unknown = [crop_id for crop_id in rotation.crop_ids if crop_id not in catalog]
    if unknown:
        raise InvalidRotationError(
            f"Rotation « {rotation.name_fr} » : culture(s) inconnue(s) : {', '.join(unknown)}."
        )
    woody = [
        crop_id
        for crop_id in rotation.crop_ids
        if catalog.get(crop_id).category is CropCategory.PERENNIAL_WOODY
    ]
    if woody:
        raise InvalidRotationError(
            f"Rotation « {rotation.name_fr} » : {', '.join(woody)} est une culture pérenne "
            "ligneuse (érablière, verger, sapinière...). C'est une décision d'aménagement sur "
            "plusieurs décennies, pas une année d'une rotation."
        )
