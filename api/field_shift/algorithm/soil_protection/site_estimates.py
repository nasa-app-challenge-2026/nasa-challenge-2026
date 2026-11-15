"""The three variables of a section computed by a published model from the other ones, when
neither the request nor a data source gives them:

    ksat_mm_h   Saxton and Rawls (2006)       from the texture and the organic matter
    k_factor    EPIC, Williams (1995)         from the texture and the organic matter
    r_factor    Renard and Freimund (1994)    from the annual rain

These are not default values: they transform measured data with a peer-reviewed equation, and
every reading they add says so (`origin` and `method`).
"""

from __future__ import annotations

from collections.abc import Sequence

from field_shift.algorithm.config.soil_protection import PEDOTRANSFER_MAX_ORGANIC_MATTER_PCT
from field_shift.algorithm.soil_protection.erosion import (
    erodibility_from_texture,
    erosivity_from_annual_rain,
)
from field_shift.algorithm.soil_protection.pedotransfer import saxton_rawls_ksat
from field_shift.algorithm.soil_protection.site_conditions import (
    MissingSiteDataError,
    SiteReading,
    check_texture,
)

ORIGIN_SAXTON_RAWLS = "calcul : Saxton et Rawls (2006)"
ORIGIN_EPIC = "calcul : EPIC, Williams (1995)"
ORIGIN_RENARD_FREIMUND = "calcul : Renard et Freimund (1994)"

#: The variables this module can compute, and the ones each needs.
ESTIMATED_FROM: dict[str, tuple[str, ...]] = {
    "ksat_mm_h": ("sand_pct", "clay_pct", "organic_matter_pct"),
    "k_factor": ("sand_pct", "clay_pct", "organic_matter_pct"),
    "r_factor": ("annual_rain_mm",),
}


def _number(value: float) -> str:
    return f"{value:.4g}".replace(".", ",")


def with_estimates(readings: Sequence[SiteReading]) -> list[SiteReading]:
    """The readings, plus Ksat, K and R computed for those that are missing.

    Raises MissingSiteDataError when a variable a model needs is missing itself.
    """
    by_key = {reading.key: reading for reading in readings}
    needed = {
        source
        for key, sources in ESTIMATED_FROM.items()
        if key not in by_key
        for source in sources
        if source not in by_key
    }
    if needed:
        raise MissingSiteDataError(sorted(needed))
    if "sand_pct" in by_key and "clay_pct" in by_key:
        check_texture(by_key["sand_pct"].value, by_key["clay_pct"].value)
    added: list[SiteReading] = []
    if "ksat_mm_h" not in by_key or "k_factor" not in by_key:
        sand = by_key["sand_pct"].value
        clay = by_key["clay_pct"].value
        organic = by_key["organic_matter_pct"].value
        silt = max(0.0, 100 - sand - clay)
        texture = (
            f"sable {_number(sand)} %, argile {_number(clay)} %, "
            f"matière organique {_number(organic)} %"
        )
        if "ksat_mm_h" not in by_key:
            estimate = saxton_rawls_ksat(sand, clay, organic)
            bounded = (
                f" ; matière organique ramenée à {_number(PEDOTRANSFER_MAX_ORGANIC_MATTER_PCT)} %, "
                "limite des données de l’équation"
                if estimate.organic_matter_bounded and organic > estimate.organic_matter_used_pct
                else ""
            )
            added.append(
                SiteReading(
                    "ksat_mm_h",
                    estimate.ksat_mm_h,
                    ORIGIN_SAXTON_RAWLS,
                    f"fonction de pédotransfert de Saxton et Rawls (2006) à partir de la texture "
                    f"et de la matière organique ({texture}{bounded})",
                )
            )
        if "k_factor" not in by_key:
            added.append(
                SiteReading(
                    "k_factor",
                    erodibility_from_texture(sand, silt, clay, organic),
                    ORIGIN_EPIC,
                    f"équation EPIC (Williams, 1995) à partir de la texture et de la matière "
                    f"organique ({texture})",
                )
            )
    if "r_factor" not in by_key:
        rain = by_key["annual_rain_mm"]
        added.append(
            SiteReading(
                "r_factor",
                erosivity_from_annual_rain(rain.value),
                ORIGIN_RENARD_FREIMUND,
                f"relation de Renard et Freimund (1994) à partir de la pluie annuelle "
                f"({_number(rain.value)} mm, {rain.origin}), calée sur les États-Unis",
            )
        )
    return [*readings, *added]
