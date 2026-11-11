"""Registry of yearly climate indicators.

Each indicator is a named, documented, pure function of one ``YearContext``. Adding an
indicator means adding one entry here: the API, the summaries and the dashboard pick it up
without further change. Labels and definitions are in French because they are part of what
the farmer reads; the wording must stay in sync with ``docs/methodology.md``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from statistics import fmean

from fieldshift.domain.climate import precipitation as precip
from fieldshift.domain.climate.statistics import Summary, summarize
from fieldshift.domain.climate.year_context import YearContext

HAYMAKING_PERIOD = ((6, 1), (7, 31))
"""June and July: the period in which the interviewed farmer reported difficult dry-hay
harvests. First-cut dates vary by region (source: cqpf_hay_guide_2002, table 6)."""

HAYMAKING_DRY_DAYS = 3
"""Early-cut hay needs a forecast of at least three consecutive days without rain
(source: cqpf_hay_guide_2002, chapter III)."""


class IndicatorGroup(StrEnum):
    TEMPERATURE = "temperature"
    FROST = "frost"
    SEASON = "season"
    PRECIPITATION = "precipitation"
    WATER_BALANCE = "water_balance"
    FIELD_OPERATIONS = "field_operations"


class IndicatorKind(StrEnum):
    QUANTITY = "quantity"
    """A number with a unit."""
    DAY_OF_YEAR = "day_of_year"
    """A date inside the year, expressed as day of year (1 = 1 January)."""


@dataclass(frozen=True, slots=True)
class IndicatorDefinition:
    id: str
    group: IndicatorGroup
    kind: IndicatorKind
    label_fr: str
    unit: str
    definition_fr: str
    source_ids: tuple[str, ...]
    compute: Callable[[YearContext], float | None]


def _day_of_year(index: int | None) -> float | None:
    return None if index is None else float(index + 1)


def _mean(values: Sequence[float], window: tuple[int, int]) -> float:
    return fmean(values[window[0] : window[1]])


def _sum(values: Sequence[float], window: tuple[int, int]) -> float:
    return sum(values[window[0] : window[1]])


def _season_length(context: YearContext) -> float:
    season = context.growing_season
    return float(season.length_days) if season is not None else 0.0


def _crop_heat_units(context: YearContext) -> float:
    season = context.crop_heat_unit_season
    if season is None:
        return 0.0
    return sum(context.crop_heat_units[season.start_index : season.end_index])


def _frost_free_days(context: YearContext) -> float | None:
    season = context.frost_free_season
    return float(season.length_days) if season is not None else None


def _water_balance(context: YearContext) -> float:
    window = context.agroclimatic_window
    return _sum(context.data.precipitation_mm, window) - _sum(
        context.reference_evapotranspiration_mm, window
    )


def _haymaking_days(context: YearContext) -> float:
    start, stop = context.window(*HAYMAKING_PERIOD)
    return float(
        precip.count_dry_window_starts(
            context.data.precipitation_mm, start, stop, HAYMAKING_DRY_DAYS
        )
    )


_NASA = "nasa_power"

INDICATORS: tuple[IndicatorDefinition, ...] = (
    # --- Temperature ---------------------------------------------------------
    IndicatorDefinition(
        id="t_mean_annual_c",
        group=IndicatorGroup.TEMPERATURE,
        kind=IndicatorKind.QUANTITY,
        label_fr="Température moyenne de l'année",
        unit="°C",
        definition_fr="Moyenne sur l'année de la température moyenne quotidienne à 2 m.",
        source_ids=(_NASA,),
        compute=lambda c: fmean(c.data.t_mean_c),
    ),
    IndicatorDefinition(
        id="t_mean_growing_season_c",
        group=IndicatorGroup.TEMPERATURE,
        kind=IndicatorKind.QUANTITY,
        label_fr="Température moyenne, avril à octobre",
        unit="°C",
        definition_fr=(
            "Moyenne de la température moyenne quotidienne à 2 m du 1er avril au 31 octobre."
        ),
        source_ids=(_NASA, "aafc_agroclimate"),
        compute=lambda c: _mean(c.data.t_mean_c, c.agroclimatic_window),
    ),
    IndicatorDefinition(
        id="t_max_mean_growing_season_c",
        group=IndicatorGroup.TEMPERATURE,
        kind=IndicatorKind.QUANTITY,
        label_fr="Maximum quotidien moyen, avril à octobre",
        unit="°C",
        definition_fr="Moyenne des températures maximales quotidiennes du 1er avril au 31 octobre.",
        source_ids=(_NASA, "aafc_agroclimate"),
        compute=lambda c: _mean(c.data.t_max_c, c.agroclimatic_window),
    ),
    IndicatorDefinition(
        id="t_min_mean_growing_season_c",
        group=IndicatorGroup.TEMPERATURE,
        kind=IndicatorKind.QUANTITY,
        label_fr="Minimum quotidien moyen, avril à octobre",
        unit="°C",
        definition_fr="Moyenne des températures minimales quotidiennes du 1er avril au 31 octobre.",
        source_ids=(_NASA, "aafc_agroclimate"),
        compute=lambda c: _mean(c.data.t_min_c, c.agroclimatic_window),
    ),
    IndicatorDefinition(
        id="t_max_absolute_c",
        group=IndicatorGroup.TEMPERATURE,
        kind=IndicatorKind.QUANTITY,
        label_fr="Température la plus élevée de l'année",
        unit="°C",
        definition_fr="Plus haute température maximale quotidienne de l'année.",
        source_ids=(_NASA,),
        compute=lambda c: max(c.data.t_max_c),
    ),
    IndicatorDefinition(
        id="t_min_absolute_c",
        group=IndicatorGroup.TEMPERATURE,
        kind=IndicatorKind.QUANTITY,
        label_fr="Température la plus basse de l'année",
        unit="°C",
        definition_fr="Plus basse température minimale quotidienne de l'année.",
        source_ids=(_NASA,),
        compute=lambda c: min(c.data.t_min_c),
    ),
    # --- Frost ---------------------------------------------------------------
    IndicatorDefinition(
        id="frost_days",
        group=IndicatorGroup.FROST,
        kind=IndicatorKind.QUANTITY,
        label_fr="Jours de gel dans l'année",
        unit="jours",
        definition_fr=(
            "Nombre de jours de l'année où la température minimale est inférieure à 0 °C "
            "(indice FD de l'ETCCDI)."
        ),
        source_ids=("etccdi_indices",),
        compute=lambda c: float(sum(1 for t_min in c.data.t_min_c if t_min < 0.0)),
    ),
    IndicatorDefinition(
        id="last_spring_frost_doy",
        group=IndicatorGroup.FROST,
        kind=IndicatorKind.DAY_OF_YEAR,
        label_fr="Dernier gel du printemps",
        unit="jour de l'année",
        definition_fr=(
            "Dernier jour avant le 15 juillet où la température minimale est inférieure à 0 °C."
        ),
        source_ids=("plouffe_2011", "bourgeois_2012"),
        compute=lambda c: _day_of_year(c.last_spring_frost_index),
    ),
    IndicatorDefinition(
        id="first_fall_frost_doy",
        group=IndicatorGroup.FROST,
        kind=IndicatorKind.DAY_OF_YEAR,
        label_fr="Premier gel de l'automne",
        unit="jour de l'année",
        definition_fr=(
            "Premier jour à partir du 15 juillet où la température minimale est inférieure à 0 °C."
        ),
        source_ids=("plouffe_2011",),
        compute=lambda c: _day_of_year(c.first_fall_frost_index),
    ),
    IndicatorDefinition(
        id="first_fall_killing_frost_doy",
        group=IndicatorGroup.FROST,
        kind=IndicatorKind.DAY_OF_YEAR,
        label_fr="Premier gel meurtrier de l'automne",
        unit="jour de l'année",
        definition_fr=(
            "Premier jour à partir du 15 juillet où la température minimale atteint -2 °C "
            "ou moins. C'est la fin du cumul des unités thermiques maïs au Québec."
        ),
        source_ids=("bourgeois_2012",),
        compute=lambda c: _day_of_year(c.first_fall_killing_frost_index),
    ),
    IndicatorDefinition(
        id="frost_free_season_days",
        group=IndicatorGroup.FROST,
        kind=IndicatorKind.QUANTITY,
        label_fr="Saison sans gel",
        unit="jours",
        definition_fr=(
            "Nombre de jours entre le dernier gel du printemps et le premier gel de l'automne "
            "(seuil : minimum inférieur à 0 °C)."
        ),
        source_ids=("plouffe_2011",),
        compute=_frost_free_days,
    ),
    # --- Growing season and heat ---------------------------------------------
    IndicatorDefinition(
        id="growing_season_length_days",
        group=IndicatorGroup.SEASON,
        kind=IndicatorKind.QUANTITY,
        label_fr="Saison de croissance",
        unit="jours",
        definition_fr=(
            "Du premier épisode d'au moins 6 jours à plus de 5 °C de moyenne jusqu'au premier "
            "épisode, après le 1er juillet, de 6 jours à moins de 5 °C (indice GSL de l'ETCCDI)."
        ),
        source_ids=("etccdi_indices", "plouffe_2011"),
        compute=_season_length,
    ),
    IndicatorDefinition(
        id="growing_season_start_doy",
        group=IndicatorGroup.SEASON,
        kind=IndicatorKind.DAY_OF_YEAR,
        label_fr="Début de la saison de croissance",
        unit="jour de l'année",
        definition_fr=(
            "Premier jour du premier épisode d'au moins 6 jours à plus de 5 °C de moyenne. "
            "Repère thermique : ce n'est pas une date de semis."
        ),
        source_ids=("etccdi_indices",),
        compute=lambda c: _day_of_year(c.growing_season.start_index if c.growing_season else None),
    ),
    IndicatorDefinition(
        id="growing_season_end_doy",
        group=IndicatorGroup.SEASON,
        kind=IndicatorKind.DAY_OF_YEAR,
        label_fr="Fin de la saison de croissance",
        unit="jour de l'année",
        definition_fr=(
            "Dernier jour avant le premier épisode, après le 1er juillet, de 6 jours à moins "
            "de 5 °C de moyenne."
        ),
        source_ids=("etccdi_indices",),
        compute=lambda c: _day_of_year(c.growing_season.last_index if c.growing_season else None),
    ),
    IndicatorDefinition(
        id="gdd_base0",
        group=IndicatorGroup.SEASON,
        kind=IndicatorKind.QUANTITY,
        label_fr="Degrés-jours de croissance, base 0 °C",
        unit="degrés-jours",
        definition_fr=(
            "Somme, du 1er avril au 31 octobre, de la moyenne (maximum + minimum) / 2 "
            "au-dessus de 0 °C. Base utilisée pour les céréales."
        ),
        source_ids=("aafc_agroclimate", "omafra_fieldcropnews_2025"),
        compute=lambda c: _sum(c.degree_days_base0, c.agroclimatic_window),
    ),
    IndicatorDefinition(
        id="gdd_base5",
        group=IndicatorGroup.SEASON,
        kind=IndicatorKind.QUANTITY,
        label_fr="Degrés-jours de croissance, base 5 °C",
        unit="degrés-jours",
        definition_fr=(
            "Somme, du 1er avril au 31 octobre, de la moyenne (maximum + minimum) / 2 "
            "au-dessus de 5 °C. Base utilisée pour la luzerne et le canola."
        ),
        source_ids=("aafc_agroclimate", "omafra_fieldcropnews_2025"),
        compute=lambda c: _sum(c.degree_days(5.0), c.agroclimatic_window),
    ),
    IndicatorDefinition(
        id="gdd_base10",
        group=IndicatorGroup.SEASON,
        kind=IndicatorKind.QUANTITY,
        label_fr="Degrés-jours de croissance, base 10 °C",
        unit="degrés-jours",
        definition_fr=(
            "Somme, du 1er avril au 31 octobre, de la moyenne (maximum + minimum) / 2 "
            "au-dessus de 10 °C."
        ),
        source_ids=("aafc_agroclimate",),
        compute=lambda c: _sum(c.degree_days(10.0), c.agroclimatic_window),
    ),
    IndicatorDefinition(
        id="crop_heat_units",
        group=IndicatorGroup.SEASON,
        kind=IndicatorKind.QUANTITY,
        label_fr="Unités thermiques maïs (UTM)",
        unit="UTM",
        definition_fr=(
            "Chaleur utile aux cultures de saison chaude (maïs, soya), cumulée selon la méthode "
            "québécoise : du premier jour où la moyenne mobile sur 5 jours atteint 12,8 °C, après "
            "la date médiane du dernier gel, jusqu'au premier gel d'automne à -2 °C ou moins."
        ),
        source_ids=("bourgeois_2012",),
        compute=_crop_heat_units,
    ),
    IndicatorDefinition(
        id="crop_heat_unit_season_start_doy",
        group=IndicatorGroup.SEASON,
        kind=IndicatorKind.DAY_OF_YEAR,
        label_fr="Début du cumul des UTM",
        unit="jour de l'année",
        definition_fr=(
            "Premier jour, après la date médiane du dernier gel du printemps, où la moyenne "
            "mobile sur 5 jours de la température atteint 12,8 °C."
        ),
        source_ids=("bourgeois_2012",),
        compute=lambda c: _day_of_year(
            c.crop_heat_unit_season.start_index if c.crop_heat_unit_season else None
        ),
    ),
    # --- Precipitation -------------------------------------------------------
    IndicatorDefinition(
        id="precipitation_annual_mm",
        group=IndicatorGroup.PRECIPITATION,
        kind=IndicatorKind.QUANTITY,
        label_fr="Précipitations de l'année",
        unit="mm",
        definition_fr="Total des précipitations (pluie et neige en équivalent eau) de l'année.",
        source_ids=(_NASA,),
        compute=lambda c: sum(c.data.precipitation_mm),
    ),
    IndicatorDefinition(
        id="precipitation_growing_season_mm",
        group=IndicatorGroup.PRECIPITATION,
        kind=IndicatorKind.QUANTITY,
        label_fr="Précipitations, avril à octobre",
        unit="mm",
        definition_fr="Total des précipitations du 1er avril au 31 octobre.",
        source_ids=(_NASA, "aafc_agroclimate"),
        compute=lambda c: _sum(c.data.precipitation_mm, c.agroclimatic_window),
    ),
    IndicatorDefinition(
        id="precipitation_spring_mm",
        group=IndicatorGroup.PRECIPITATION,
        kind=IndicatorKind.QUANTITY,
        label_fr="Précipitations du printemps (mars à mai)",
        unit="mm",
        definition_fr="Total des précipitations du 1er mars au 31 mai.",
        source_ids=(_NASA,),
        compute=lambda c: _sum(c.data.precipitation_mm, c.window((3, 1), (5, 31))),
    ),
    IndicatorDefinition(
        id="precipitation_summer_mm",
        group=IndicatorGroup.PRECIPITATION,
        kind=IndicatorKind.QUANTITY,
        label_fr="Précipitations de l'été (juin à août)",
        unit="mm",
        definition_fr="Total des précipitations du 1er juin au 31 août.",
        source_ids=(_NASA,),
        compute=lambda c: _sum(c.data.precipitation_mm, c.window((6, 1), (8, 31))),
    ),
    IndicatorDefinition(
        id="precipitation_autumn_mm",
        group=IndicatorGroup.PRECIPITATION,
        kind=IndicatorKind.QUANTITY,
        label_fr="Précipitations de l'automne (septembre à novembre)",
        unit="mm",
        definition_fr="Total des précipitations du 1er septembre au 30 novembre.",
        source_ids=(_NASA,),
        compute=lambda c: _sum(c.data.precipitation_mm, c.window((9, 1), (11, 30))),
    ),
    IndicatorDefinition(
        id="wet_days_growing_season",
        group=IndicatorGroup.PRECIPITATION,
        kind=IndicatorKind.QUANTITY,
        label_fr="Jours de pluie, avril à octobre",
        unit="jours",
        definition_fr="Nombre de jours avec au moins 1 mm de précipitations, du 1er avril au 31 octobre.",
        source_ids=("etccdi_indices",),
        compute=lambda c: float(
            precip.count_wet_days(c.data.precipitation_mm, *c.agroclimatic_window)
        ),
    ),
    IndicatorDefinition(
        id="max_dry_spell_growing_season_days",
        group=IndicatorGroup.PRECIPITATION,
        kind=IndicatorKind.QUANTITY,
        label_fr="Plus longue période sèche, avril à octobre",
        unit="jours",
        definition_fr=(
            "Plus grand nombre de jours consécutifs avec moins de 1 mm de précipitations, "
            "du 1er avril au 31 octobre (indice CDD de l'ETCCDI, restreint à cette période)."
        ),
        source_ids=("etccdi_indices",),
        compute=lambda c: float(
            precip.longest_dry_spell(c.data.precipitation_mm, *c.agroclimatic_window)
        ),
    ),
    IndicatorDefinition(
        id="heavy_precipitation_days",
        group=IndicatorGroup.PRECIPITATION,
        kind=IndicatorKind.QUANTITY,
        label_fr="Jours de fortes précipitations, avril à octobre",
        unit="jours",
        definition_fr=(
            "Nombre de jours avec au moins 20 mm de précipitations, du 1er avril au 31 octobre "
            "(indice R20mm de l'ETCCDI, restreint à cette période)."
        ),
        source_ids=("etccdi_indices",),
        compute=lambda c: float(
            precip.count_days_at_or_above(
                c.data.precipitation_mm,
                *c.agroclimatic_window,
                precip.HEAVY_PRECIPITATION_THRESHOLD_MM,
            )
        ),
    ),
    IndicatorDefinition(
        id="max_one_day_precipitation_mm",
        group=IndicatorGroup.PRECIPITATION,
        kind=IndicatorKind.QUANTITY,
        label_fr="Plus forte précipitation en une journée",
        unit="mm",
        definition_fr="Plus grand total quotidien de précipitations de l'année (indice Rx1day de l'ETCCDI).",
        source_ids=("etccdi_indices",),
        compute=lambda c: max(c.data.precipitation_mm),
    ),
    # --- Water balance -------------------------------------------------------
    IndicatorDefinition(
        id="reference_evapotranspiration_growing_season_mm",
        group=IndicatorGroup.WATER_BALANCE,
        kind=IndicatorKind.QUANTITY,
        label_fr="Demande en eau de l'atmosphère, avril à octobre",
        unit="mm",
        definition_fr=(
            "Évapotranspiration de référence cumulée du 1er avril au 31 octobre, estimée à partir "
            "des températures (méthode de Hargreaves, FAO-56, équation 52). Ordre de grandeur : "
            "la méthode tend à surestimer en climat humide."
        ),
        source_ids=("fao56",),
        compute=lambda c: _sum(c.reference_evapotranspiration_mm, c.agroclimatic_window),
    ),
    IndicatorDefinition(
        id="climatic_water_balance_growing_season_mm",
        group=IndicatorGroup.WATER_BALANCE,
        kind=IndicatorKind.QUANTITY,
        label_fr="Bilan hydrique climatique, avril à octobre",
        unit="mm",
        definition_fr=(
            "Précipitations moins évapotranspiration de référence, du 1er avril au 31 octobre. "
            "Une valeur négative signifie que l'atmosphère demande plus d'eau qu'il n'en tombe ; "
            "l'eau stockée dans le sol n'est pas prise en compte."
        ),
        source_ids=("fao56", "audet_2012"),
        compute=_water_balance,
    ),
    # --- Field operations ----------------------------------------------------
    IndicatorDefinition(
        id="haymaking_days_june_july",
        group=IndicatorGroup.FIELD_OPERATIONS,
        kind=IndicatorKind.QUANTITY,
        label_fr="Jours de fauche possibles en juin et juillet",
        unit="jours",
        definition_fr=(
            "Nombre de jours, du 1er juin au 31 juillet, qui ouvrent une séquence d'au moins "
            "3 jours consécutifs avec moins de 1 mm de précipitations. Le foin hâtif demande "
            "au moins trois jours consécutifs sans pluie."
        ),
        source_ids=("cqpf_hay_guide_2002", "etccdi_indices"),
        compute=_haymaking_days,
    ),
    IndicatorDefinition(
        id="wet_days_june_july",
        group=IndicatorGroup.FIELD_OPERATIONS,
        kind=IndicatorKind.QUANTITY,
        label_fr="Jours de pluie en juin et juillet",
        unit="jours",
        definition_fr="Nombre de jours avec au moins 1 mm de précipitations, du 1er juin au 31 juillet.",
        source_ids=("etccdi_indices",),
        compute=lambda c: float(
            precip.count_wet_days(c.data.precipitation_mm, *c.window(*HAYMAKING_PERIOD))
        ),
    ),
)

INDICATORS_BY_ID: dict[str, IndicatorDefinition] = {
    indicator.id: indicator for indicator in INDICATORS
}


@dataclass(frozen=True, slots=True)
class IndicatorSeries:
    """One indicator across the analysed years. ``values`` is aligned with ``years``."""

    definition: IndicatorDefinition
    years: tuple[int, ...]
    values: tuple[float | None, ...]
    summary: Summary | None
    """Computed on the years where the indicator has a value."""


def compute_indicator_series(
    definition: IndicatorDefinition, contexts: Sequence[YearContext]
) -> IndicatorSeries:
    years = tuple(context.year for context in contexts)
    values = tuple(definition.compute(context) for context in contexts)
    known = [(year, value) for year, value in zip(years, values, strict=True) if value is not None]
    summary = summarize([year for year, _ in known], [value for _, value in known])
    return IndicatorSeries(definition=definition, years=years, values=values, summary=summary)


def compute_all_indicators(contexts: Sequence[YearContext]) -> tuple[IndicatorSeries, ...]:
    return tuple(compute_indicator_series(definition, contexts) for definition in INDICATORS)


@dataclass(frozen=True, slots=True)
class MonthlyNormal:
    """Average conditions of one calendar month over the analysed years."""

    month: int
    t_mean_c: float
    t_max_mean_c: float
    t_min_mean_c: float
    precipitation_mm: float
    """Mean monthly total."""


def compute_monthly_normals(contexts: Sequence[YearContext]) -> tuple[MonthlyNormal, ...]:
    """Monthly averages over all analysed years (empty when there is no year)."""
    if not contexts:
        return ()
    normals: list[MonthlyNormal] = []
    for month in range(1, 13):
        t_mean: list[float] = []
        t_max: list[float] = []
        t_min: list[float] = []
        totals: list[float] = []
        for context in contexts:
            data = context.data
            indices = [index for index, day in enumerate(data.days) if day.month == month]
            t_mean.extend(data.t_mean_c[index] for index in indices)
            t_max.extend(data.t_max_c[index] for index in indices)
            t_min.extend(data.t_min_c[index] for index in indices)
            totals.append(sum(data.precipitation_mm[index] for index in indices))
        normals.append(
            MonthlyNormal(
                month=month,
                t_mean_c=fmean(t_mean),
                t_max_mean_c=fmean(t_max),
                t_min_mean_c=fmean(t_min),
                precipitation_mm=fmean(totals),
            )
        )
    return tuple(normals)
