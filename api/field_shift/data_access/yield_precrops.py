"""The value of each previous crop (step 7) from the regional yield model of the team
(`algorithm/yield_model`): how much the vigor of a crop changes after each previous crop, in the
fields of the region of the farm.

    vigor          MODIS MOD13Q1 NDVI of the summers 2018–2024 (Planetary Computer), 64 × 64
                   pixels over 8 km around the farm, corrected for the weather of each year
                   (NASA POWER, ridge regression)
    previous crop  the crop maps of the same years: AAFC Annual Crop Inventory in Canada, USDA
                   Cropland Data Layer in the United States (calibrated on the USDA NASS yields
                   there, when the model has a key)

The values fill the ones the twins leave unknown (their greenness, NASA HLS, is not read yet):
`TwinEvidence.with_precrop_values`. They come from the region of the farm today, the same for
every cycle. A pair seen fewer than `MIN_SAMPLES` times stays unknown, like a succession seen in
too few twin fields; as in the yield model, an unknown pair counts as unfavourable (its penalty:
the first quartile of the effects of the region, −1.5 % at least), so that a crop the maps do not
know (hay, canola, buckwheat) does not win for being unknown. A crop after itself takes its
regional value. When the model cannot read its data, every value stays unknown and counts 0 %,
as in field_shift.py v5.1, and the plan says why.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Final

from field_shift.algorithm.sources.cycle_data_provider import EvidenceFor
from field_shift.algorithm.sources.data_source import DataSource
from field_shift.algorithm.twins.climate_twin_finder import Twin
from field_shift.algorithm.twins.soil_comparison import Soil
from field_shift.algorithm.twins.twin_evidence import TwinEvidence
from field_shift.algorithm.yield_model import (
    CONFIG,
    build_transition_observations,
    compute_regional_pair_matrix,
    resolve_pair_evidence,
)
from field_shift.algorithm.yield_model.sources import (
    calibrate_pair_matrix_with_nass_yields,
    fetch_nasa_power_series,
    fetch_nass_state_yields,
    fetch_regional_crop_history,
    fetch_regional_ndvi_series,
)
from field_shift.algorithm.yield_model.yield_optimizer import compute_unobserved_pair_penalty

#: Key of the precrop values among the data sources of a plan.
PRECROP_KEY: Final = "precropValues"
#: Crop of the plan (sold crop of a sheet) → crop of the yield model. Canola, buckwheat and hay are
#: not in its crop maps: their successions stay unknown.
YIELD_MODEL_CROPS: Final[dict[str, str]] = {
    "mais": "mais",
    "soya": "soya",
    "soya-2e": "soya",
    "ble-automne": "ble",
    "orge": "orge",
    "luzerne": "luzerne",
}
#: Fewest field transitions for a pair to count (the "medium confidence" of the yield model).
MIN_SAMPLES: Final = CONFIG["sampling"]["minSamplesMediumConfidence"]
SAMPLING: Final = CONFIG["sampling"]

#: (lat, lon) → the pair matrix of the yield model.
PairMatrixReader = Callable[[float, float], Mapping[str, Any]]
PrecropValues = dict[tuple[str, str], float]


def regional_pair_matrix(lat: float, lon: float) -> Mapping[str, Any]:
    """The pair matrix of the region (the yield model reads and keeps its data on disk)."""
    start, end, window = SAMPLING["startYear"], SAMPLING["endYear"], SAMPLING["halfWindowKm"]
    power = fetch_nasa_power_series(lat=lat, lon=lon, start_year=start, end_year=end)
    ndvi = fetch_regional_ndvi_series(
        lat=lat, lon=lon, start_year=start, end_year=end, half_window_km=window
    )
    crops = fetch_regional_crop_history(
        lat=lat,
        lon=lon,
        bbox=ndvi["bbox"],
        grid_size=ndvi.get("nrows") or SAMPLING.get("gridSize", 64),
        half_window_km=window,
        start_year=start,
        end_year=end,
    )
    try:
        nass = fetch_nass_state_yields(lat=lat, lon=lon, start_year=start, end_year=end)
    except Exception:  # the calibration is optional: the model goes on without it
        nass = {"available": False}
    observations = build_transition_observations(
        ndvi_series=ndvi, crop_history=crops, climate_seasons=power["seasons"]
    )
    return calibrate_pair_matrix_with_nass_yields(compute_regional_pair_matrix(observations), nass)


def precrop_values(pair_matrix: Mapping[str, Any]) -> PrecropValues:
    """(previous crop, next crop) of the plan → value in %, for the pairs the region saw at least
    `MIN_SAMPLES` times."""
    pairs = pair_matrix.get("pairs") or {}
    values: PrecropValues = {}
    for previous, previous_model in YIELD_MODEL_CROPS.items():
        for next_crop, next_model in YIELD_MODEL_CROPS.items():
            stat = pairs.get(f"{previous_model}>{next_model}")
            if not stat:
                continue
            evidence = resolve_pair_evidence(stat, "all")
            if evidence["sampleCount"] >= MIN_SAMPLES:
                values[(previous, next_crop)] = evidence["meanEffectPct"]
    return values


@dataclass(frozen=True)
class RegionalPrecrops:
    """What the regional yield model says of the successions of a place.

    values            (previous crop, next crop) → value in %, the pairs the region measured
    unmeasured_value  what any other succession counts (the penalty of the model; 0 % without it)
    source            what the plan says about them
    """

    values: PrecropValues
    unmeasured_value: float
    source: DataSource


def read_precrop_values(
    lat: float, lon: float, reader: PairMatrixReader = regional_pair_matrix
) -> RegionalPrecrops:
    """The values of the region of the farm and what the plan says about them. A model that cannot
    read its data gives no value (the criterion stays neutral), never a made-up one."""
    try:
        pair_matrix = reader(lat, lon)
        values = precrop_values(pair_matrix)
        penalty = compute_unobserved_pair_penalty(pair_matrix)
    except Exception as error:  # MODIS, the crop maps or NASA POWER did not answer
        return RegionalPrecrops(
            {},
            0.0,
            DataSource(
                PRECROP_KEY,
                False,
                f"Valeur du précédent : modèle régional de rendement indisponible ({error}) ; "
                "les valeurs restent inconnues et le critère rendement est neutre",
            ),
        )
    period = f"{SAMPLING['startYear']}–{SAMPLING['endYear']}"
    penalty_text = f"{penalty:+.1f}".replace(".", ",")
    return RegionalPrecrops(
        values,
        penalty,
        DataSource(
            PRECROP_KEY,
            True,
            f"Valeur du précédent : modèle régional de rendement de l’équipe ({len(values)} "
            f"successions mesurées), vigueur MODIS NDVI {period} corrigée de la météo NASA POWER, "
            f"après chaque précédent des cartes AAC / USDA, {SAMPLING['halfWindowKm']} km autour "
            f"de la ferme ; une succession jamais mesurée compte {penalty_text} %",
        ),
    )


def with_regional_precrops(evidence_for: EvidenceFor, regional: RegionalPrecrops) -> EvidenceFor:
    """The evidence of the twins, with the values of the region where theirs are unknown."""

    def evidence(
        first_year: int, last_year: int, twins: list[Twin], soil: Soil | None
    ) -> TwinEvidence:
        return evidence_for(first_year, last_year, twins, soil).with_precrop_values(
            regional.values, regional.unmeasured_value
        )

    return evidence
