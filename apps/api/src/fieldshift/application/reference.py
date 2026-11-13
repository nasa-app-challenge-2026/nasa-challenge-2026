"""Reference data the application is configured with (crops, templates, sources, demos)."""

from __future__ import annotations

from dataclasses import dataclass

from fieldshift.domain.agronomy.crops import CropCatalog
from fieldshift.domain.agronomy.farm import CropRotation, FarmProfile
from fieldshift.domain.references import Reference


@dataclass(frozen=True, slots=True)
class DemoFarm:
    id: str
    profile: FarmProfile
    description_fr: str
    provenance_fr: str
    """Where the profile comes from (for example an interview), and what is not known."""


@dataclass(frozen=True, slots=True)
class ReferenceData:
    catalog: CropCatalog
    rotation_templates: tuple[CropRotation, ...]
    references: tuple[Reference, ...]
    demo_farms: tuple[DemoFarm, ...]

    def demo_farm(self, demo_id: str) -> DemoFarm | None:
        return next((demo for demo in self.demo_farms if demo.id == demo_id), None)
