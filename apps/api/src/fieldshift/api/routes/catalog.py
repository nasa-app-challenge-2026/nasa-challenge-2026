from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from fieldshift import __version__
from fieldshift.api.dependencies import ContainerDep
from fieldshift.api.schemas.catalog import (
    CropOut,
    DemoFarmOut,
    ReferenceOut,
    RotationOut,
    crop_out,
    demo_farm_out,
    reference_out,
    rotation_out,
)

router = APIRouter()


class HealthOut(BaseModel):
    status: str
    version: str
    climate_source: str
    crops: int
    rotation_templates: int


@router.get("/health", tags=["système"])
def health(container: ContainerDep) -> HealthOut:
    return HealthOut(
        status="ok",
        version=__version__,
        climate_source=container.settings.climate_source.value,
        crops=len(container.reference.catalog),
        rotation_templates=len(container.reference.rotation_templates),
    )


@router.get("/crops", tags=["référentiel"])
def crops(container: ContainerDep) -> list[CropOut]:
    return [crop_out(crop) for crop in container.reference.catalog]


@router.get("/rotation-templates", tags=["référentiel"])
def rotation_templates(container: ContainerDep) -> list[RotationOut]:
    return [rotation_out(t) for t in container.reference.rotation_templates]


@router.get("/sources", tags=["référentiel"])
def sources(container: ContainerDep) -> list[ReferenceOut]:
    return [reference_out(r) for r in container.reference.references]


@router.get("/demo-farms", tags=["référentiel"])
def demo_farms(container: ContainerDep) -> list[DemoFarmOut]:
    return [demo_farm_out(d) for d in container.reference.demo_farms]
