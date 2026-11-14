"""Saturated hydraulic conductivity (Ksat) from the texture and the organic matter of a soil.

Saxton and Rawls, "Soil water characteristic estimates by texture and organic matter for
hydrologic solutions", Soil Science Society of America Journal 70(5), 1569–1578, 2006. The
equations were fitted on the USDA soil characterisation database (about 2000 samples); S and C are
the sand and clay fractions (0 to 1), OM the organic matter in % by weight:

    θ1500   moisture at −1500 kPa (wilting point)          equations 1
    θ33     moisture at −33 kPa (field capacity)            equations 2
    θS−33   moisture between saturation and −33 kPa         equations 3
    θS      saturated moisture                              equation 5
    λ       slope of the log tension / log moisture curve   equations 14 and 15
    Ks      1930 (θS − θ33)^(3 − λ)  in mm/h                 equation 16

Density and gravel corrections of the paper are not applied (normal density, no gravel).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from field_shift.algorithm.config.soil_protection import (
    KSAT_COEFFICIENT_MM_H,
    PEDOTRANSFER_MAX_ORGANIC_MATTER_PCT,
)

#: Tensions (kPa) of the wilting point and of the field capacity.
WILTING_POINT_KPA = 1500.0
FIELD_CAPACITY_KPA = 33.0


@dataclass(frozen=True)
class KsatEstimate:
    """Ksat of a soil and the organic matter the equations were run with (bounded to their
    range of validity)."""

    ksat_mm_h: float
    organic_matter_used_pct: float

    @property
    def organic_matter_bounded(self) -> bool:
        return self.organic_matter_used_pct == PEDOTRANSFER_MAX_ORGANIC_MATTER_PCT


def saxton_rawls_ksat(sand_pct: float, clay_pct: float, organic_matter_pct: float) -> KsatEstimate:
    """Ksat (mm/h) of [SR06] (see the module documentation).

    The organic matter is bounded to 8 %, the upper limit of the data the equations were fitted
    on. Raises ValueError for a texture the equations cannot describe (e.g. pure sand or clay,
    where the moisture curve degenerates).
    """
    s, c = sand_pct / 100, clay_pct / 100
    om = min(max(organic_matter_pct, 0.0), PEDOTRANSFER_MAX_ORGANIC_MATTER_PCT)

    t1500 = -0.024 * s + 0.487 * c + 0.006 * om + 0.005 * s * om - 0.013 * c * om
    t1500 += 0.068 * s * c + 0.031
    theta_1500 = t1500 + (0.14 * t1500 - 0.02)

    t33 = -0.251 * s + 0.195 * c + 0.011 * om + 0.006 * s * om - 0.027 * c * om
    t33 += 0.452 * s * c + 0.299
    theta_33 = t33 + (1.283 * t33**2 - 0.374 * t33 - 0.015)

    ts33 = 0.278 * s + 0.034 * c + 0.022 * om - 0.018 * s * om - 0.027 * c * om
    ts33 += -0.584 * s * c + 0.078
    theta_s33 = ts33 + (0.636 * ts33 - 0.107)

    theta_s = theta_33 + theta_s33 - 0.097 * s + 0.043
    if not 0 < theta_1500 < theta_33 < theta_s:
        raise ValueError(
            f"texture hors du domaine de Saxton et Rawls (sable {sand_pct} %, argile {clay_pct} %)"
        )
    b = (math.log(WILTING_POINT_KPA) - math.log(FIELD_CAPACITY_KPA)) / (
        math.log(theta_33) - math.log(theta_1500)
    )
    slope = 1 / b
    ksat = KSAT_COEFFICIENT_MM_H * (theta_s - theta_33) ** (3 - slope)
    return KsatEstimate(ksat, om)
