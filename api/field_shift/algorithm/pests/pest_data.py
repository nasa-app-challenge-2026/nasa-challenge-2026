"""Pests of the rotation: the organisms whose pressure the "ravageurs" criterion follows.

One organism `p` has hosts (crops, each with a sensitivity from 0 to 1) and the number of years
without a host that it takes for its pressure to fall to an acceptable level (`years_without_host`,
called L_p in README.md). Nothing is invented here: each entry is derived from a source
listed in `sources`, and a number that no source gives stays at its neutral value.

Where the entries come from:
  - the 20 soil diseases of SARE (McGrath 2009, appendix 3): `SOIL_DISEASES` of
    `reference/return_delays.py`. L_p is the HIGH end of the SARE range (the delay after which the
    soil is clean), while the hard constraint of the return delays keeps using the low end;
  - one "crop complex" per crop that has a Fruchtfolge delay (Pahmeyer et al. 2021): the break the
    German rotation tool asks between two crops of the same species, whatever the cause;
  - the corn rootworms (Diabrotica), added for the grain crops of Québec.

SEVERITY. `severity` (sev_p in README.md) weighs an organism against the others on the same
crop. It is 1 for every organism: the yield losses the sources give are not comparable (a "up to
30 %" for the soybean cyst nematode, a 15 % difference between two previous crops for the wheat
scab), and mixing them would give more weight to the organisms that have no figure. They are kept
in `reported_yield_loss` for a later calibration, and are not used by the score.

NOT CODED, on purpose:
  - rotation-resistant corn rootworm (northern: eggs that wait 2 winters; western "soybean
    variant": eggs laid in soybean). The sources place them in the U.S. Midwest; the 2007-2008
    scouting of the MAPAQ found no soybean variant in Québec. Check the zone before coding them;
  - wireworms (Agriotes): 2 to 6 years of larval life, kept by grass and small grains, and they
    hurt crops (potato, carrot) that do not keep them. One host list cannot say both, and no
    source gives a number of years without host.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from field_shift.reference.crops import CROP_NAMES
from field_shift.reference.return_delays import CROP_DELAYS, SOIL_DISEASES, SoilDisease

#: Weight of an organism against the others on a crop, until the sources allow to tell them apart.
DEFAULT_SEVERITY: Final = 1.0

SARE: Final = "SARE, Crop Rotation on Organic Farms, annexe 3 (McGrath 2009)"
FRUCHTFOLGE: Final = "Fruchtfolge (Pahmeyer, Kuhn & Britz 2021)"
AGRIRESEAU_CRM: Final = (
    "Agri-Réseau, Les chrysomèles des racines du maïs en grandes cultures (document 118135), "
    "https://www.agrireseau.net/documents/Document_118135.pdf"
)
AGRIRESEAU_ROTATION: Final = (
    "Agri-Réseau, une seule année de soya réduit drastiquement les populations de chrysomèles "
    "(document 118489), https://www.agrireseau.net/documents/Document_118489.pdf"
)
MAPAQ_DEPISTAGE: Final = (
    "MAPAQ, Rapport de dépistage de la chrysomèle des racines du maïs dans le maïs et le soya au "
    "Québec en 2007 et 2008 (variante soya de la chrysomèle de l’Ouest non détectée)"
)
ISU_CRW: Final = "Iowa State University, Corn rootworm life cycle, https://cornrootworm.extension.iastate.edu/basics/life-cycle"
OSU_SCN: Final = (
    "Ohio State University, Soybean cyst nematode factsheet: populations may decline by 50 % per "
    "year under non-host crops, https://u.osu.edu/knoxcountyag/files/2023/07/SCN-Factsheet.pdf"
)
SCN_LOSS: Final = (
    "Farm Progress, 6 ways to manage soybean cyst nematode (up to 30 % yield loss), "
    "https://farmprogress.com/crop-disease/6-ways-to-manage-soybean-cyst-nematode"
)
FHB_LOSS: Final = (
    "Dill-Macky & Jones 2000, Plant Disease 84:71-76: wheat yielded about 15 % less after corn or "
    "wheat than after soybean"
)
CLUBROOT_DECAY: Final = (
    "AAFC Normandin (Québec): about 90 % of the resting spores gone after a 2-year break, the "
    "rest very durable; half-life of 3 to 6 years elsewhere (PNW Plant Disease Handbook)"
)


class PestType(StrEnum):
    """What kind of organism it is (the criterion reports each kind apart)."""

    SOIL_DISEASE = "maladie-sol"
    NEMATODE = "nematode"
    SOIL_INSECT = "insecte-sol"
    CROP_COMPLEX = "complexe-culture"


@dataclass(frozen=True)
class Host:
    """A crop that keeps the organism, and how much (1 = main host, 0.5 = secondary host)."""

    crop_id: str
    sensitivity: float = 1.0


@dataclass(frozen=True)
class Pest:
    """One organism of the rotation.

    years_without_host    years without a host after which its pressure is acceptable (> 0)
    severity              weight against the other organisms of a crop (see the module docstring)
    reported_yield_loss   loss the sources report, as a share (not used by the score)
    """

    id: str
    name: str
    latin: str
    type: PestType
    hosts: tuple[Host, ...]
    years_without_host: int
    sources: tuple[str, ...]
    severity: float = DEFAULT_SEVERITY
    reported_yield_loss: float | None = None
    notes: str = ""

    def sensitivity_of(self, crop_id: str) -> float:
        """0 when the crop is not a host."""
        return next((h.sensitivity for h in self.hosts if h.crop_id == crop_id), 0.0)


#: Soil diseases that are not diseases.
_TYPE_OF_DISEASE: Final[dict[str, PestType]] = {"nematode-kyste-soya": PestType.NEMATODE}
_REPORTED_LOSS: Final[dict[str, tuple[float, str]]] = {
    "nematode-kyste-soya": (0.30, SCN_LOSS),
    "fusariose": (0.15, FHB_LOSS),
}
_EXTRA_SOURCES: Final[dict[str, tuple[str, ...]]] = {
    "nematode-kyste-soya": (OSU_SCN,),
    "hernie-cruciferes": (CLUBROOT_DECAY,),
}


def _from_soil_disease(disease_id: str, disease: SoilDisease) -> Pest:
    loss = _REPORTED_LOSS.get(disease_id)
    return Pest(
        id=disease_id,
        name=disease.name,
        latin=disease.latin,
        type=_TYPE_OF_DISEASE.get(disease_id, PestType.SOIL_DISEASE),
        hosts=tuple(Host(crop_id) for crop_id in disease.hosts),
        years_without_host=disease.high,
        sources=(SARE, *_EXTRA_SOURCES.get(disease_id, ())),
        reported_yield_loss=loss[0] if loss else None,
        notes=f"SARE: {disease.low} to {disease.high} years without a host."
        + (f" Yield loss: {loss[1]}." if loss else ""),
    )


def _crop_complexes() -> dict[str, Pest]:
    """One per crop with a Fruchtfolge break: a delay with no named cause."""
    complexes: dict[str, Pest] = {}
    for crop_id, row in CROP_DELAYS.items():
        years = row.fruchtfolge_years_without
        if not years:
            continue  # no delay (hay) or no Fruchtfolge value (tomato)
        complexes[f"fruchtfolge-{crop_id}"] = Pest(
            id=f"fruchtfolge-{crop_id}",
            name=f"complexe propre à la culture ({CROP_NAMES[crop_id].lower()})",
            latin="",
            type=PestType.CROP_COMPLEX,
            hosts=(Host(crop_id),),
            years_without_host=years,
            sources=(FRUCHTFOLGE,),
            notes="Break between two crops of the same species, whatever the cause.",
        )
    return complexes


_CORN_ROOTWORMS: Final = Pest(
    id="chrysomele-racines-mais",
    name="chrysomèle des racines du maïs",
    latin="Diabrotica virgifera virgifera, D. barberi",
    type=PestType.SOIL_INSECT,
    hosts=(Host("mais"),),
    years_without_host=1,
    sources=(AGRIRESEAU_CRM, AGRIRESEAU_ROTATION, MAPAQ_DEPISTAGE, ISU_CRW),
    notes=(
        "One generation a year; the larvae feed on corn roots only and starve in another crop, "
        "so one year without corn breaks the cycle. Rotation-resistant variants are not coded: "
        "see the module docstring."
    ),
)


def _build_pests() -> dict[str, Pest]:
    pests = {d: _from_soil_disease(d, info) for d, info in SOIL_DISEASES.items()}
    pests[_CORN_ROOTWORMS.id] = _CORN_ROOTWORMS
    pests.update(_crop_complexes())
    return pests


PESTS: Final[dict[str, Pest]] = _build_pests()
