"""The data of a place the algorithm is built on, given from outside.

The algorithm never reads a data service itself: the server gives it the real data of the place
(NASA POWER projections of NEX-GDDP-CMIP6, the NASA POWER grid of observed climates, the crop maps
of the twins: `data_access/place_data.py`), the tests give it the reference data of field_shift.py
(`tests/helpers/reference_place.py`). Each source comes with what the plan says about it
(`DataSource`: real or not, and a label for the farmer).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from field_shift.algorithm.climate.target_climate_projector import ClimateModel
from field_shift.algorithm.sources.cycle_data_provider import EvidenceFor
from field_shift.algorithm.sources.data_source import DataSource
from field_shift.algorithm.twins.climate_twin_finder import CultivationCheck, GridCell

CLIMATE_MODELS_KEY = "climateModels"
TWINS_KEY = "twins"
TWIN_CROPS_KEY = "twinCrops"


@dataclass(frozen=True)
class PlaceSources:
    """Steps 3 to 7 of a place.

    models        climate models of the long term (step 3, case 2)
    models_label  name of their mean in the plan (None: the default name)
    grid          the observed climates where twins are searched (step 4)
    cultivation   says which cells of the grid are cultivated, when they are not known yet
    evidence_for  what the twin fields grow, for the soil of a field (steps 5 to 7)
    sources       where each of them comes from (shown in the plan)
    """

    models: Sequence[ClimateModel]
    grid: Sequence[GridCell]
    evidence_for: EvidenceFor
    sources: tuple[DataSource, ...]
    cultivation: CultivationCheck | None = None
    models_label: str | None = None
    notes: tuple[str, ...] = field(default=())
