"""From the results of the algorithm to the wire format (FarmPlan): dates as ISO dates, positions
from 1, French messages next to the structured data."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime

from field_shift.algorithm.chain.chain_scorer import ChainPests, ScoredChain
from field_shift.algorithm.chain.chain_step import ChainStep, sheet_ids
from field_shift.algorithm.config.timing import DAYS_PER_MONTH
from field_shift.algorithm.delays.occupation import Occupation
from field_shift.algorithm.delays.return_delay_checker import history_depth
from field_shift.algorithm.field_shift_algorithm import ALGORITHM_VERSION, FieldShiftAlgorithm
from field_shift.algorithm.planning.cycle_plan import CyclePlan, ParcelPlan
from field_shift.algorithm.planning.parcel import Parcel
from field_shift.algorithm.report.chain_label import chain_label
from field_shift.algorithm.report.messages import (
    impossible_text,
    shared_disease_text,
    succession_text,
    violation_text,
)
from field_shift.algorithm.sources.field_data import FieldData
from field_shift.algorithm.timeline import month_time
from field_shift.algorithm.twins.climate_twin_finder import is_good_twin
from field_shift.algorithm.water.water_model import WaterPressure, WaterScore
from field_shift.contract.farm_plan import (
    AlertReasonOut,
    ChainOut,
    ClimateOut,
    CycleOut,
    FarmPlan,
    FieldMeasuresOut,
    FieldOut,
    GapOut,
    HistoryEntry,
    ModelNoteOut,
    MonthDayOut,
    PestsOut,
    PlanMeta,
    PlanSettings,
    ReferenceAlertOut,
    RemovedCropOut,
    RisksOut,
    SectionPlanOut,
    SharedDiseaseOut,
    SoilOut,
    SourceInfo,
    StepKind,
    StepOut,
    TwinCellOut,
    TwinsOut,
    WaterOut,
    WaterPressureOut,
    YearAndSourceOut,
)
from field_shift.contract.input_mapper import FarmContext
from field_shift.reference.crops import CROP_SHEETS, SEED_IDS, Role

ENGINE_NAME = "field-shift-server"
#: The crops that have a sheet, once each, in sheet order.
SHEET_CROP_IDS = tuple(dict.fromkeys(sheet.crop_id for sheet in CROP_SHEETS))
#: Numbers of the plan are rounded to this many decimals.
DECIMALS = 3


def rounded(value: float) -> float:
    """A finite number rounded for the wire."""
    return round(float(value), DECIMALS)


def rounded_or_none(value: float | None) -> float | None:
    """Rounded for the wire; a missing number, or one that JSON cannot write (inf, nan), is null."""
    if value is None or not math.isfinite(value):
        return None
    return rounded(value)


def _rounded_values(values: Mapping[str, float]) -> dict[str, float]:
    return {key: rounded(value) for key, value in values.items()}


def _rounded_values_or_none(values: Mapping[str, float | None]) -> dict[str, float | None]:
    return {key: rounded_or_none(value) for key, value in values.items()}


def _step_kind(step: ChainStep) -> StepKind:
    if step.is_cover:
        return "couvert"
    return "jachere" if step.sheet.role is Role.FALLOW else "culture"


def _step_out(step: ChainStep) -> StepOut:
    kind = _step_kind(step)
    return StepOut(
        sheet=step.sheet_id,
        crop=step.sheet.crop_id,
        kind=kind,
        sowing=None if step.sowing is None else month_time.to_date(step.sowing),
        harvest=None if kind == "jachere" else month_time.to_date(step.harvest),
        positions=None if step.is_cover else (step.first_position + 1, step.last_position + 1),
    )


def _steps_in_calendar_order(scored: ScoredChain) -> list[StepOut]:
    """The crops of the chain and its covers, by sowing date (fallow by its start)."""
    steps = [*scored.chain, *scored.covers]
    ordered = sorted(
        enumerate(steps),
        key=lambda item: (item[1].harvest if item[1].sowing is None else item[1].sowing, item[0]),
    )
    return [_step_out(step) for _, step in ordered]


def water_pressure_out(water: WaterPressure) -> WaterPressureOut:
    return WaterPressureOut(
        pressure=rounded(water.pressure),
        worst=rounded(water.worst),
        components=_rounded_values(water.components),
        missing=list(water.missing),
        sources=dict(water.sources),
        aridity_index=rounded_or_none(water.aridity_index),
        aridity_class=water.aridity_class,
    )


def _water_out(water: WaterScore | None, irrigated: bool) -> WaterOut | None:
    """The water score of a chain; the irrigation is shown only for an irrigated section."""
    if water is None:
        return None
    figures = water.figures
    return WaterOut(
        note=rounded(water.note),
        worst=rounded(water.worst),
        sub_scores=_rounded_values(water.sub_scores),
        demand_mm_per_year=rounded(figures["demande_mm_an"]),
        shortfall_mm_per_year=rounded(figures["manque_mm_an"]),
        irrigation_mm_per_year=rounded(figures["irrigation_mm_an"]) if irrigated else None,
        rain_kept_pct=rounded(figures["pluie_gardee_pct"]),
        water_at_sowing_mm=rounded_or_none(figures["eau_au_semis_mm"]),
        alerts=list(water.alerts),
        by_model=[ModelNoteOut(model=name, note=rounded(note)) for name, note in water.by_model],
    )


def _pests_out(pests: ChainPests | None) -> PestsOut | None:
    if pests is None:
        return None
    return PestsOut(
        score=rounded(pests.score),
        confidence=rounded(pests.confidence),
        crops_without_data=list(pests.crops_without_data),
        sentences=list(pests.sentences),
    )


def chain_out(scored: ScoredChain | None, irrigated: bool = False) -> ChainOut | None:
    if scored is None:
        return None
    return ChainOut(
        score=round(scored.score, DECIMALS),
        criteria=_rounded_values_or_none(scored.criteria),
        label=chain_label(scored.chain, scored.covers),
        sheets=sheet_ids(scored.chain),
        steps=_steps_in_calendar_order(scored),
        gaps=[
            GapOut(
                previous=a,
                next=b,
                message=succession_text(a, b),
                assumed_pct=rounded(scored.gap_value),
            )
            for a, b in scored.gaps
        ],
        seeds_to_buy=scored.seeds_to_buy,
        warnings=[
            SharedDiseaseOut(
                disease=w.disease,
                previous=w.previous,
                next=w.next,
                years_without=w.years_without,
                advised=w.advised,
                message=shared_disease_text(w),
            )
            for w in scored.warnings
        ],
        water=_water_out(scored.water, irrigated),
        pests=_pests_out(scored.pests),
    )


def _month_day_out(month_in_year: float | None) -> MonthDayOut | None:
    if month_in_year is None:
        return None
    day = month_time.month_day(month_in_year)
    return MonthDayOut(month=day.month, day=day.day)


def _climate_out(cycle: CyclePlan) -> ClimateOut:
    climate = cycle.climate
    return ClimateOut(
        method=climate.method.value,
        source=climate.source,
        models=list(climate.models),
        last_spring_frost=_month_day_out(climate.last_spring_frost),
        first_fall_frost=_month_day_out(climate.first_fall_frost),
        january_minimum_c=rounded(climate.january_minimum_c),
        warming_c=rounded(climate.warming_c),
        summer_rain_change_pct=rounded(climate.summer_rain_change_pct),
        harvest_advance_days=round(climate.harvest_advance_months * DAYS_PER_MONTH),
    )


def _twins_out(cycle: CyclePlan) -> TwinsOut:
    evidence = cycle.evidence
    mean_sigma = evidence.sigma_mean
    return TwinsOut(
        sigma_mean=rounded_or_none(mean_sigma),
        reliable=mean_sigma is not None and is_good_twin(mean_sigma),
        cells=[
            TwinCellOut(
                lat=rounded(t.cell.lat),
                lon=rounded(t.cell.lon),
                sigma=rounded_or_none(t.sigma),
                sources=t.sources,
            )
            for t in evidence.twins
        ],
        crops=[crop for crop in SHEET_CROP_IDS if evidence.is_grown(crop)],
    )


def cycle_out(cycle: CyclePlan, cycle_years: int) -> CycleOut:
    irrigated = cycle.context.irrigated
    return CycleOut(
        index=cycle.index,
        years=cycle.years,
        decision=cycle.decision,
        climate=_climate_out(cycle),
        twins=_twins_out(cycle),
        risks=RisksOut(erosion=rounded(cycle.risks.erosion), water=rounded(cycle.risks.water)),
        water_pressure=water_pressure_out(cycle.water_pressure),
        weights=_rounded_values(cycle.weights),
        chosen=chain_out(cycle.chosen, irrigated),
        reference=chain_out(cycle.reference, irrigated),
        reference_alerts=[
            ReferenceAlertOut(
                reason=AlertReasonOut(
                    kind=v.reason.kind.value,
                    previous=v.reason.previous,
                    next=v.reason.next,
                    family=v.reason.family,
                    disease=v.reason.disease,
                ),
                years_without=v.years_without,
                minimum=v.minimum,
                start=YearAndSourceOut(year=v.start.year, source=v.start.source.value),
                end=YearAndSourceOut(year=v.end.year, source=v.end.source.value),
                message=violation_text(v),
            )
            for v in cycle.reference_alerts
        ],
        alternatives=[chain_out(a, irrigated) for a in cycle.alternatives],
        removed=[
            RemovedCropOut(
                sheet=sheet_id,
                required=info.required,
                possible=info.possible,
                occupied_years=info.occupied_years,
                message=impossible_text(sheet_id, info, cycle_years),
            )
            for sheet_id, info in cycle.removed.items()
        ],
        robustness=rounded_or_none(cycle.robustness),
        becomes_infeasible_later=cycle.becomes_infeasible_later,
    )


def _history_out(history: Sequence[Occupation]) -> list[HistoryEntry]:
    return [
        HistoryEntry(crop=o.crop_id, from_year=o.first_year, to_year=o.last_year) for o in history
    ]


def _field_out(parcel: Parcel, data: FieldData, water_today: WaterPressure) -> FieldOut:
    m = data.measures
    return FieldOut(
        measures=FieldMeasuresOut(**vars(m)),
        soil=SoilOut(
            clay_pct=data.soil.clay_pct,
            sand_pct=data.soil.sand_pct,
            organic_carbon=data.soil.organic_carbon,
            ph=data.soil.ph,
            source=data.soil_source,
        ),
        risks_today=RisksOut(
            erosion=rounded(parcel.diagnostic.erosion_risk),
            water=rounded(parcel.diagnostic.water_risk(water_today.pressure)),
        ),
        water_pressure=water_pressure_out(water_today),
    )


def section_plan_out(
    parcel: Parcel,
    plan: ParcelPlan,
    data: FieldData,
    cycle_years: int,
    water_today: WaterPressure,
) -> SectionPlanOut:
    cycles = [cycle_out(c, cycle_years) for c in plan.cycles]
    return SectionPlanOut(
        id=parcel.id,
        free_at=plan.free_on,
        first_year=cycles[0].years[0] if cycles else None,
        last_year=cycles[-1].years[1] if cycles else None,
        repeats_current_crop=parcel.repeats_in_place_crop,
        history_years=history_depth(SEED_IDS, parcel.diseases),
        history=_history_out(plan.history),
        field=_field_out(parcel, data, water_today),
        cycles=cycles,
    )


def farm_plan_out(
    context: FarmContext,
    plans: Sequence[ParcelPlan],
    algorithm: FieldShiftAlgorithm,
    today: date,
    generated_at: datetime | None = None,
) -> FarmPlan:
    """The plan of the whole farm: settings and weights once, then one plan per section."""
    time = context.time
    sources = (*algorithm.data_sources, context.field_source)
    return FarmPlan(
        meta=PlanMeta(
            engine=ENGINE_NAME,
            algorithm=ALGORITHM_VERSION,
            demo=any(not source.real for source in sources),
            generated_at=generated_at or datetime.now(UTC),
            sources={s.key: SourceInfo(real=s.real, label=s.label) for s in sources},
        ),
        settings=PlanSettings(
            cycle_years=time.cycle_years,
            frequency_months=time.frequency_months,
            positions_per_cycle=time.positions_per_cycle,
            horizon_years=time.horizon_years,
            current_year=today.year,
            priorities=list(context.farmer.ranking),
        ),
        weights=_rounded_values(context.farmer.base_weights),
        sections=[
            section_plan_out(
                parcel,
                plan,
                context.field_data[parcel.id],
                time.cycle_years,
                algorithm.water_today,
            )
            for parcel, plan in zip(context.parcels, plans, strict=True)
        ],
    )
