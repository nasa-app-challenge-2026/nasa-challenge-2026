"""The four measures a rotation is ranked on, behind one interface.

A measure looks at one rotation on one section and returns a `MeasureResult`: a score from 0
(worst) to 1 (best), comparable between measures so they can be added, and its main value in its
own unit (kg/ha for the yield, the RPI for the soil protection...).

    rendement        yield                          NOT WRITTEN YET
    eau              water demand                   NOT WRITTEN YET
    protection_sol   erosion and infiltration       `SoilProtectionMeasure`
    ravageurs        pests and diseases             NOT WRITTEN YET

To write one of the three missing measures: fill the `evaluate` method of its class below (it
receives everything the soil protection measure receives), return a `MeasureResult` with a score
between 0 and 1, and set `implemented = True`. Nothing else changes: the ranking, the routes and
the contract already carry the four measures.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from field_shift.algorithm.rotation.rotation import Rotation
from field_shift.algorithm.soil_protection.site_conditions import SiteConditions
from field_shift.algorithm.soil_protection.soil_protection import (
    SoilProtection,
    evaluate_soil_protection,
)
from field_shift.reference.measures import (
    MEASURE_NAMES,
    MEASURE_PESTS,
    MEASURE_SOIL_PROTECTION,
    MEASURE_WATER,
    MEASURE_YIELD,
)


class MeasureNotImplementedError(NotImplementedError):
    """The logic of a measure is not written yet (its route answers 501)."""

    def __init__(self, measure_id: str) -> None:
        super().__init__(
            f"La mesure « {MEASURE_NAMES[measure_id]} » ({measure_id}) n’est pas encore calculée."
        )
        self.measure_id = measure_id


@dataclass(frozen=True)
class SectionContext:
    """Everything a measure may read about the section and the simulation.

    section_id          id of the section in the request
    lat, lon            place of the section (the field, unless the section gives its own)
    area_ha             area of the section, when known
    irrigated           True when the section is irrigated
    site                soil, relief, rain and satellite measures of the section
    simulation_months   duration of the simulation
    """

    section_id: str
    lat: float
    lon: float
    site: SiteConditions
    simulation_months: float
    area_ha: float | None = None
    irrigated: bool = False


@dataclass(frozen=True)
class MeasureResult:
    """The result of one measure for one rotation on one section.

    score      from 0 (worst) to 1 (best); None when the measure is not available
    value      main value, in the unit of the measure (see `reference.measures.MEASURE_UNITS`)
    available  False when the measure is not computed: it is then left out of the total
    note       why the measure is not available, or a remark on the result
    detail     the full result of the measure, for the report (a `SoilProtection` today)
    """

    measure_id: str
    score: float | None = None
    value: float | None = None
    available: bool = True
    note: str = ""
    detail: SoilProtection | None = None

    @classmethod
    def unavailable(cls, measure_id: str, note: str) -> MeasureResult:
        return cls(measure_id, available=False, note=note)


class Measure(Protocol):
    """A measure of the ranking. `evaluate` raises `MeasureNotImplementedError` while its logic
    is not written."""

    id: str
    #: False while the logic of the measure is not written.
    implemented: bool

    def evaluate(self, rotation: Rotation, context: SectionContext) -> MeasureResult: ...


class SoilProtectionMeasure:
    """Erosion and infiltration (see `algorithm/soil_protection`). The value is the adjusted
    Rotation Protection Index, from 1 to 5."""

    id = MEASURE_SOIL_PROTECTION
    implemented = True

    def evaluate(self, rotation: Rotation, context: SectionContext) -> MeasureResult:
        protection = evaluate_soil_protection(rotation, context.site, context.simulation_months)
        return MeasureResult(
            self.id,
            score=protection.score,
            value=protection.index.adjusted_rpi,
            detail=protection,
        )


class YieldMeasure:
    """Yield of the rotation, in kg/ha. TODO: not written yet."""

    id = MEASURE_YIELD
    implemented = False

    def evaluate(self, rotation: Rotation, context: SectionContext) -> MeasureResult:
        raise MeasureNotImplementedError(self.id)


class WaterDemandMeasure:
    """Water demand of the rotation, in mm. TODO: not written yet."""

    id = MEASURE_WATER
    implemented = False

    def evaluate(self, rotation: Rotation, context: SectionContext) -> MeasureResult:
        raise MeasureNotImplementedError(self.id)


class PestsMeasure:
    """Pests and diseases pressure of the rotation. TODO: not written yet."""

    id = MEASURE_PESTS
    implemented = False

    def evaluate(self, rotation: Rotation, context: SectionContext) -> MeasureResult:
        raise MeasureNotImplementedError(self.id)


def all_measures() -> tuple[Measure, ...]:
    """The four measures, in the order of `reference.measures.MEASURE_IDS`."""
    return (YieldMeasure(), WaterDemandMeasure(), SoilProtectionMeasure(), PestsMeasure())
