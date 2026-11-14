"""Soil protection sheet of every crop: the classification matrix of the Rotation Protection Index.

Each crop is classified from 1 (poor) to 5 (excellent) on three biological properties:

    Infiltration (root architecture)
        1  short taproot or sparse fibrous roots: minimal channels (soybean, dry bean)
        2  moderate taproot: limited reach into the subsoil (field pea, sunflower)
        3  deep taproot: dense vertical reach (grain maize, chickpea)
        4  dense fibrous roots: massive network near the surface (sorghum-sudan, ryegrass)
        5  deep perennial or massive fibrous roots: deep macropores (alfalfa, brome)

    Erosion (biomass and surface residue)
        1  low residue, fast decay (potato, silage maize, soybean)
        2  moderately low residue, light biomass (canola, flax)
        3  moderately high, persistent residue (winter wheat, oat, rye)
        4  high residue, slow decay (grain maize, grain sorghum)
        5  perennial mat, living roots and stubble (permanent pasture, turf)

    Cover (duration of the living canopy)
        1  short window: bare soil more than 8 months a year (summer fallow, spring root crops)
        2  moderate window: bare soil 6 to 8 months a year (spring wheat, barley)
        3  extended window: soil covered 6 to 9 months a year (winter wheat, fall rye)
        4  long window: cover or catch crops, bare soil less than 3 months
        5  continuous cover: permanent living canopy (perennial forage)

Sources: the classification matrix of the team's specification (RPI), itself built on the RUSLE2
handbook (USDA, 2001: cover-management factor) and on the infiltration meta-analysis of Basche and
DeLonge (PLOS ONE, 2019).

VALUES ARE INDICATIVE: the examples of the matrix (soybean, potato, maize, winter wheat, alfalfa,
permanent grass...) are taken as written; the other crops are classified by analogy. An agronomist
must check them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from field_shift.reference.crops import CROP_NAMES, SHEETS
from field_shift.reference.planning import MONTHS_PER_YEAR

#: Lowest and highest score of the classification matrix.
MIN_SCORE: Final = 1
MAX_SCORE: Final = 5


class CoverKind(StrEnum):
    """How a crop holds the soil, for the erosion and infiltration models.

    ANNUAL     a cash crop sown and harvested within a year (the conventional control of the
               infiltration meta-analysis);
    COVER      a cover crop, grown to protect the soil and not harvested;
    PERENNIAL  a crop that stays several years without tillage (alfalfa, hay);
    FALLOW     tilled bare soil.
    """

    ANNUAL = "annuelle"
    COVER = "couvert"
    PERENNIAL = "perenne"
    FALLOW = "jachere"


@dataclass(frozen=True)
class SoilProtectionProfile:
    """The three scores of a crop (1 to 5) and how long it usually holds the field.

    infiltration   root architecture: channels and macropores the roots leave in the soil
    residue        biomass and surface residue left to break the raindrops and slow the runoff
    cover          duration of the living canopy over a year
    season_months  months the crop usually occupies the field in one year (used when a rotation
                   does not say how long a phase lasts)
    kind           see `CoverKind`
    """

    crop_id: str
    infiltration: int
    residue: int
    cover: int
    season_months: float
    kind: CoverKind = CoverKind.ANNUAL

    def __post_init__(self) -> None:
        for name in ("infiltration", "residue", "cover"):
            score = getattr(self, name)
            if not MIN_SCORE <= score <= MAX_SCORE:
                raise ValueError(f"{self.crop_id}: {name} must be between 1 and 5, not {score}")
        if not 0 < self.season_months <= MONTHS_PER_YEAR:
            raise ValueError(f"{self.crop_id}: season_months must be between 0 and 12")

    @property
    def intrinsic_score(self) -> float:
        """SC of the specification: the mean of the three scores."""
        return (self.infiltration + self.residue + self.cover) / 3


def _profile(
    crop_id: str,
    infiltration: int,
    residue: int,
    cover: int,
    season_months: float,
    kind: CoverKind = CoverKind.ANNUAL,
) -> SoilProtectionProfile:
    return SoilProtectionProfile(crop_id, infiltration, residue, cover, season_months, kind)


_PROFILES: Final[tuple[SoilProtectionProfile, ...]] = (
    # Field crops ------------------------------------------------- infiltration, residue, cover
    _profile("mais", 3, 4, 2, 6),  # grain maize: deep roots, high slow-decaying residue
    _profile("soya", 1, 1, 2, 5),  # short taproot, low residue
    _profile("soya-2e", 1, 1, 2, 4),
    _profile("ble-automne", 3, 3, 3, 10),  # winter wheat: soil covered from September to July
    _profile("orge", 3, 3, 2, 4),  # spring cereal: bare soil 6 to 8 months
    _profile("avoine", 3, 3, 2, 4),
    _profile("canola", 2, 2, 2, 4.5),  # moderate taproot, light biomass
    _profile("sarrasin", 2, 1, 1, 3),  # short season, residue that decays fast
    _profile("haricot-sec", 1, 1, 1, 3.5),
    _profile("pois", 2, 2, 1, 3),  # field pea: moderate taproot
    # Perennials and cover crops
    _profile("luzerne", 5, 4, 5, 12, CoverKind.PERENNIAL),  # deep perennial roots, macropores
    _profile("foin", 5, 5, 5, 12, CoverKind.PERENNIAL),  # permanent grass: perennial mat
    _profile("seigle", 4, 3, 3, 8, CoverKind.COVER),  # fall rye: dense fibrous roots
    _profile("jachere", 1, 1, 1, 12, CoverKind.FALLOW),
    # Vegetables: spring root and leaf crops, little residue, long bare soil window
    _profile("pomme-de-terre", 1, 1, 1, 4),
    _profile("carotte", 1, 1, 1, 4),
    _profile("navet", 1, 1, 1, 3),
    _profile("radis", 1, 1, 1, 2),
    _profile("betterave", 2, 1, 1, 4),
    _profile("oignon", 1, 1, 1, 4),
    _profile("celeri", 1, 1, 1, 4),
    _profile("laitue", 1, 1, 1, 2.5),
    _profile("epinard", 1, 1, 1, 2),
    _profile("chou", 2, 1, 1, 4),
    _profile("tomate", 2, 1, 1, 4),
    _profile("courge", 2, 2, 2, 4),
)

#: The soil protection sheet of every crop of `CROP_NAMES`, by crop id.
SOIL_PROTECTION_PROFILES: Final[dict[str, SoilProtectionProfile]] = {
    profile.crop_id: profile for profile in _PROFILES
}

_missing = set(CROP_NAMES) - set(SOIL_PROTECTION_PROFILES)
if _missing:  # a crop added to CROP_NAMES must get its soil protection sheet
    raise RuntimeError(f"Soil protection profile missing for: {sorted(_missing)}")


def crop_id_of(crop_or_sheet_id: str) -> str:
    """The crop behind a crop id or a sheet id ("luzerne-3" → "luzerne").

    Raises KeyError if the id is neither a crop nor a sheet.
    """
    if crop_or_sheet_id in SOIL_PROTECTION_PROFILES:
        return crop_or_sheet_id
    return SHEETS[crop_or_sheet_id].crop_id


def soil_protection_profile(crop_or_sheet_id: str) -> SoilProtectionProfile:
    """The soil protection sheet of a crop id or a sheet id. Raises KeyError if unknown."""
    return SOIL_PROTECTION_PROFILES[crop_id_of(crop_or_sheet_id)]


def default_phase_months(crop_or_sheet_id: str) -> float:
    """Months a crop holds the field when the rotation does not say it.

    A sheet of a perennial ("luzerne-3") holds the field for its production years; any other crop
    for its usual season.
    """
    sheet = SHEETS.get(crop_or_sheet_id)
    if sheet is not None and sheet.is_perennial:
        return float(sheet.production_years * MONTHS_PER_YEAR)
    return soil_protection_profile(crop_or_sheet_id).season_months
