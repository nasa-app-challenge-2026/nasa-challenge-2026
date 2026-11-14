"""The two translators of the rotation ranking: request → objects of the algorithm, results →
answer. No computation here: the numbers come from `algorithm/`, this module only renames, rounds
and puts the scores on 100.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from urllib.parse import urlsplit

from field_shift.algorithm.config.scoring import SCORE_SCALE
from field_shift.algorithm.config.soil_protection import SOIL_LOSS_TOLERANCE_T_HA_YEAR
from field_shift.algorithm.ranking.measure_weights import measure_weights
from field_shift.algorithm.ranking.measures import MeasureResult
from field_shift.algorithm.ranking.rotation_ranker import RankedRotation
from field_shift.algorithm.rotation.rotation import (
    Rotation,
    RotationPhase,
    RotationStep,
    generate_rotations,
)
from field_shift.algorithm.soil_protection.protection_index import ProtectionClass
from field_shift.algorithm.soil_protection.site_conditions import (
    ORIGIN_SECTION,
    SITE_VARIABLES,
    SiteConditions,
    SiteReading,
)
from field_shift.algorithm.soil_protection.soil_protection import SoilProtection
from field_shift.contract.rotation_ranking import (
    MAX_ROTATIONS,
    CropOut,
    CropProtectionOut,
    ErosionOut,
    InfiltrationOut,
    MeasureOut,
    PhaseInput,
    PhaseOut,
    RankedRotationOut,
    RankingInput,
    RankingSectionInput,
    RotationInput,
    RusleFactorsOut,
    SiteValueOut,
    SoilProtectionOut,
)
from field_shift.reference.crops import CROP_NAMES, crop_name
from field_shift.reference.measures import MEASURE_NAMES, MEASURE_UNITS
from field_shift.reference.planning import MONTHS_PER_YEAR
from field_shift.reference.soil_protection import SOIL_PROTECTION_PROFILES

BARE_SOIL_NAME = "Sol nu"

PROTECTION_LABELS = {
    ProtectionClass.HIGH_RISK: "Risque d’érosion élevé, infiltration médiocre (alerte dégradation)",
    ProtectionClass.MODERATE: "Protection modérée",
    ProtectionClass.EXCELLENT: "Excellente protection, la structure du sol se régénère",
}

# Decimals kept on the wire.
SCORE_DECIMALS = 1
INDEX_DECIMALS = 2
VALUE_DECIMALS = 2
FACTOR_DECIMALS = 4
WEIGHT_DECIMALS = 4


# --- Request → algorithm --------------------------------------------------------------------------


@dataclass(frozen=True)
class RankingRequest:
    """A ranking request in the objects of the algorithm.

    rotations           the candidate rotations (written by the user or generated)
    generated           True when they were generated from the crops and the cycle length
    simulation_months   duration of the simulation
    weights             weight of each measure, adding up to 1
    """

    rotations: tuple[Rotation, ...]
    generated: bool
    simulation_months: float
    weights: dict[str, float]


def _step(phase: str | PhaseInput) -> RotationStep:
    if isinstance(phase, str):
        return RotationStep(phase)
    return RotationStep(phase.crop, phase.months)


def _rotations(inputs: Sequence[RotationInput]) -> tuple[Rotation, ...]:
    """The rotations the user wrote; those without id are numbered "R1", "R2"… by position."""
    taken = {rotation.id for rotation in inputs if rotation.id}
    rotations = []
    for position, rotation in enumerate(inputs, start=1):
        rotation_id = rotation.id or f"R{position}"
        if not rotation.id and rotation_id in taken:
            raise ValueError(f"l’id {rotation_id} est déjà pris par une autre rotation")
        steps = [_step(phase) for phase in rotation.phases]
        rotations.append(Rotation.from_steps(rotation_id, steps, rotation.name or ""))
    return tuple(rotations)


def read_ranking_input(ranking_input: RankingInput) -> RankingRequest:
    """The request in the objects of the algorithm.

    Raises ValueError (message in French) for what the models could not check: too many
    generated rotations, an id taken twice.
    """
    generated = not ranking_input.rotations
    if generated:
        rotations = tuple(
            generate_rotations(ranking_input.crops, ranking_input.cycle_years, MAX_ROTATIONS)
        )
    else:
        rotations = _rotations(ranking_input.rotations)
    return RankingRequest(
        rotations=rotations,
        generated=generated,
        simulation_months=ranking_input.simulation_years * MONTHS_PER_YEAR,
        weights=measure_weights(ranking_input.priorities),
    )


def section_readings(section: RankingSectionInput) -> list[SiteReading]:
    """What the section itself says of its soil, relief and climate."""
    return [
        SiteReading(key, value, ORIGIN_SECTION)
        for key in SITE_VARIABLES
        if (value := getattr(section.site, key)) is not None
    ]


# --- Results → answer -----------------------------------------------------------------------------


def _phase_name(crop_id: str | None) -> str:
    return BARE_SOIL_NAME if crop_id is None else crop_name(crop_id)


def _phase_out(phase: RotationPhase) -> PhaseOut:
    return PhaseOut(
        crop=phase.crop_id, name=_phase_name(phase.crop_id), months=round(phase.months, 2)
    )


def _on_100(score: float) -> float:
    return round(SCORE_SCALE * score, SCORE_DECIMALS)


def _crop_table(protection: SoilProtection) -> list[CropProtectionOut]:
    """The RPI table with one line per crop: the phases of the same crop over the simulation
    are added (a 12-year simulation of a 3-year rotation would otherwise give 4 lines per crop)."""
    months: dict[str | None, float] = {}
    weighted: dict[str | None, float] = {}
    scores: dict[str | None, tuple[float, float]] = {}
    for phase in protection.index.phases:
        months[phase.crop_id] = months.get(phase.crop_id, 0.0) + phase.months
        weighted[phase.crop_id] = weighted.get(phase.crop_id, 0.0) + phase.weighted
        scores[phase.crop_id] = (phase.intrinsic, phase.adjusted)
    return [
        CropProtectionOut(
            crop=crop_id,
            name=_phase_name(crop_id),
            months=round(months[crop_id], 2),
            share_pct=round(100 * months[crop_id] / protection.simulation_months, 1),
            score=round(scores[crop_id][0], INDEX_DECIMALS),
            adjusted_score=round(scores[crop_id][1], INDEX_DECIMALS),
            weighted_score=round(weighted[crop_id], INDEX_DECIMALS + 1),
        )
        for crop_id in months
    ]


def soil_protection_out(protection: SoilProtection) -> SoilProtectionOut:
    erosion, infiltration = protection.erosion, protection.infiltration
    return SoilProtectionOut(
        rpi=round(protection.index.rpi, INDEX_DECIMALS),
        adjusted_rpi=round(protection.index.adjusted_rpi, INDEX_DECIMALS),
        protection_class=protection.index.protection_class.value,
        protection_label=PROTECTION_LABELS[protection.index.protection_class],
        erosion=ErosionOut(
            soil_loss_t_ha_year=round(erosion.soil_loss_t_ha_year, VALUE_DECIMALS),
            bare_soil_loss_t_ha_year=round(erosion.bare_soil_loss_t_ha_year, VALUE_DECIMALS),
            cumulative_soil_loss_t_ha=round(protection.cumulative_soil_loss_t_ha, VALUE_DECIMALS),
            tolerance_t_ha_year=SOIL_LOSS_TOLERANCE_T_HA_YEAR,
            tolerance_ratio=round(erosion.tolerance_ratio, VALUE_DECIMALS),
            factors=RusleFactorsOut(
                r=round(erosion.r_factor, 1),
                k=round(erosion.k_factor, FACTOR_DECIMALS),
                ls=round(erosion.ls_factor, FACTOR_DECIMALS),
                c=round(erosion.c_factor, FACTOR_DECIMALS),
                p=round(erosion.p_factor, FACTOR_DECIMALS),
            ),
            score=_on_100(erosion.score),
        ),
        infiltration=InfiltrationOut(
            baseline_mm_h=round(infiltration.baseline_mm_h, VALUE_DECIMALS),
            rotation_gain_pct=round(infiltration.gain_pct, 1),
            potential_mm_h=round(infiltration.potential_mm_h, VALUE_DECIMALS),
            effective_mm_h=round(infiltration.effective_mm_h, VALUE_DECIMALS),
            storm_intensity_mm_h=round(infiltration.storm_intensity_mm_h, VALUE_DECIMALS),
            infiltrated_share_pct=round(100 * infiltration.infiltrated_share, 1),
            score=_on_100(infiltration.infiltrated_share),
        ),
        crops=_crop_table(protection),
    )


def measure_out(result: MeasureResult, weight: float) -> MeasureOut:
    return MeasureOut(
        id=result.measure_id,
        name=MEASURE_NAMES[result.measure_id],
        available=result.available,
        score=None if result.score is None else _on_100(result.score),
        value=None if result.value is None else round(result.value, VALUE_DECIMALS),
        unit=MEASURE_UNITS[result.measure_id],
        weight=round(weight, WEIGHT_DECIMALS),
        note=result.note,
    )


def ranked_rotation_out(ranked: RankedRotation) -> RankedRotationOut:
    rotation = ranked.rotation
    details = [result.detail for result in ranked.results.values() if result.detail is not None]
    return RankedRotationOut(
        rank=ranked.rank,
        rotation_id=rotation.id,
        name=rotation.name,
        cycle_years=round(rotation.cycle_years, 2),
        phases=[_phase_out(phase) for phase in rotation.phases],
        score=None if ranked.score is None else round(ranked.score, SCORE_DECIMALS),
        measures={
            measure: measure_out(result, ranked.weights[measure])
            for measure, result in ranked.results.items()
        },
        soil_protection=soil_protection_out(details[0]) if details else None,
    )


def site_out(readings: Sequence[SiteReading]) -> list[SiteValueOut]:
    """The conditions a section was computed with, in the order of `SITE_VARIABLES`."""
    by_key = {reading.key: reading for reading in readings}
    return [
        SiteValueOut(
            key=key,
            label=variable.label,
            value=round(by_key[key].value, FACTOR_DECIMALS),
            unit=variable.unit,
            origin=by_key[key].origin,
            method=by_key[key].method,
        )
        for key, variable in SITE_VARIABLES.items()
        if key in by_key
    ]


def _number(value: float) -> str:
    """A value for a French sentence: at most 4 significant digits, decimal comma."""
    return f"{value:.4g}".replace(".", ",")


def _quantity(key: str, value: float) -> str:
    unit = SITE_VARIABLES[key].unit
    return f"{_number(value)} {unit}" if unit else _number(value)


def site_notes(readings: Sequence[SiteReading], site: SiteConditions) -> list[str]:
    """Every value of a section that is not a value given in the request or read as is from a
    data service: conversions, statistics and published models, each with how it was computed
    and from what."""
    by_key = {reading.key: reading for reading in readings}
    notes = [
        f"{SITE_VARIABLES[key].label} : {_quantity(key, by_key[key].value)} — "
        f"{by_key[key].method} ({by_key[key].origin})."
        for key in SITE_VARIABLES
        if key in by_key and by_key[key].method
    ]
    origins = sorted({by_key[key].origin for key in ("sand_pct", "clay_pct")})
    notes.append(
        f"Limon : {_number(site.silt_pct)} % — calculé comme le reste de la texture "
        f"(100 − sable − argile ; {', '.join(origins)})."
    )
    return notes


def crops_out() -> list[CropOut]:
    """Every crop a rotation can contain, with its soil protection sheet."""
    return [
        CropOut(
            id=crop_id,
            name=name,
            kind=SOIL_PROTECTION_PROFILES[crop_id].kind.value,
            season_months=SOIL_PROTECTION_PROFILES[crop_id].season_months,
            infiltration_score=SOIL_PROTECTION_PROFILES[crop_id].infiltration,
            residue_score=SOIL_PROTECTION_PROFILES[crop_id].residue,
            cover_score=SOIL_PROTECTION_PROFILES[crop_id].cover,
        )
        for crop_id, name in CROP_NAMES.items()
    ]


def public_url(url: str | None) -> str | None:
    """An address without its query string: keys and tokens written in it are not shown."""
    if not url:
        return None
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}"
