"""Return delays: how many years without a crop before it may come back on the same field.

A delay counts the years WITHOUT the crop: "potato: 3" = harvest 2027, nothing in 2028,
2029 and 2030, harvest 2031.

Two sources (field_shift.py v5.1, part B):
  - Fruchtfolge (Pahmeyer et al. 2021, open-source tool): one break per crop, "1 year out
    of N" converted to N − 1 years without the crop;
  - SARE, Crop Rotation on Organic Farms, appendix 3 (McGrath 2009): years without a host
    crop, per soil-borne disease (north-east of the U.S.).
The algorithm derives a minimum (hard constraint) and a recommended delay (pest criterion)
from them: see `algorithm/delays/return_delay_catalog.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

#: Families whose different crops may follow each other (grasses, SARE chapter 5).
EXEMPT_FAMILIES: Final[frozenset[str]] = frozenset({"Poacées"})

#: Crops of the sheets that share the return delays of another crop.
DELAY_ALIASES: Final[dict[str, str]] = {"soya-2e": "soya"}


@dataclass(frozen=True)
class SoilDisease:
    """A soil-borne disease (SARE appendix 3). `low` / `high` = years without a host.

    `cross_family`: the disease hits crops of different families (gives a warning).
    """

    name: str
    latin: str
    low: int
    high: int
    cross_family: bool
    hosts: tuple[str, ...]


SOIL_DISEASES: Final[dict[str, SoilDisease]] = {
    "moisissure-blanche": SoilDisease(
        name="moisissure blanche",
        latin="Sclerotinia sclerotiorum",
        low=5,
        high=5,
        cross_family=True,
        hosts=(
            "haricot-sec",
            "pois",
            "soya",
            "pomme-de-terre",
            "carotte",
            "chou",
            "courge",
            "canola",
        ),
    ),
    "hernie-cruciferes": SoilDisease(
        name="hernie des crucifères",
        latin="Plasmodiophora brassicae",
        low=7,
        high=7,
        cross_family=False,
        hosts=("chou", "navet", "radis", "canola"),
    ),
    "jambe-noire": SoilDisease(
        name="jambe noire",
        latin="Leptosphaeria maculans (Phoma lingam)",
        low=4,
        high=4,
        cross_family=False,
        hosts=("chou", "navet", "radis", "canola"),
    ),
    "pourriture-noire": SoilDisease(
        name="pourriture noire",
        latin="Xanthomonas campestris",
        low=3,
        high=3,
        cross_family=False,
        hosts=("chou", "navet", "radis"),
    ),
    "gale-commune": SoilDisease(
        name="gale commune",
        latin="Streptomyces scabies",
        low=3,
        high=4,
        cross_family=True,
        hosts=("pomme-de-terre", "betterave", "carotte", "navet", "radis"),
    ),
    "fusariose": SoilDisease(
        name="fusariose de l’épi / gibbérelle",
        latin="Fusarium graminearum",
        low=2,
        high=3,
        cross_family=False,
        hosts=("ble-automne", "orge", "avoine", "seigle", "mais"),
    ),
    "pourriture-brune": SoilDisease(
        name="pourriture brune de la tige",
        latin="Phialophora gregata",
        low=2,
        high=3,
        cross_family=False,
        hosts=("soya",),
    ),
    "nematode-kyste-soya": SoilDisease(
        name="nématode à kyste du soya",
        latin="Heterodera glycines",
        low=4,
        high=4,
        cross_family=False,
        hosts=("soya",),
    ),
    "pourridies-legumineuses": SoilDisease(
        name="pourridiés des légumineuses",
        latin="Pythium, Rhizoctonia, Fusarium",
        low=3,
        high=4,
        cross_family=False,
        hosts=("haricot-sec", "pois"),
    ),
    "anthracnose-luzerne": SoilDisease(
        name="anthracnose de la luzerne",
        latin="Colletotrichum trifolii (et Aphanomyces)",
        low=2,
        high=3,
        cross_family=False,
        hosts=("luzerne",),
    ),
    "tache-profonde": SoilDisease(
        name="tache profonde",
        latin="Pythium spp.",
        low=3,
        high=4,
        cross_family=False,
        hosts=("carotte",),
    ),
    "septoriose-celeri": SoilDisease(
        name="septoriose du céleri",
        latin="Septoria apiicola",
        low=2,
        high=2,
        cross_family=False,
        hosts=("celeri",),
    ),
    "brulure-botrytique": SoilDisease(
        name="brûlure botrytique",
        latin="Botrytis squamosa",
        low=3,
        high=4,
        cross_family=False,
        hosts=("oignon",),
    ),
    "mildiou-laitue": SoilDisease(
        name="mildiou de la laitue",
        latin="Bremia lactucae",
        low=2,
        high=3,
        cross_family=False,
        hosts=("laitue",),
    ),
    "mildiou-epinard": SoilDisease(
        name="mildiou de l’épinard",
        latin="Peronospora effusa",
        low=2,
        high=2,
        cross_family=False,
        hosts=("epinard",),
    ),
    "cercosporiose-betterave": SoilDisease(
        name="cercosporiose de la betterave",
        latin="Cercospora beticola",
        low=3,
        high=3,
        cross_family=False,
        hosts=("betterave",),
    ),
    "anthracnose-cucurbitacees": SoilDisease(
        name="anthracnose des cucurbitacées",
        latin="Colletotrichum orbiculare",
        low=2,
        high=2,
        cross_family=False,
        hosts=("courge",),
    ),
    "fletrissure-cucurbitacees": SoilDisease(
        name="flétrissure fusarienne des cucurbitacées",
        latin="Fusarium oxysporum",
        low=5,
        high=7,
        cross_family=False,
        hosts=("courge",),
    ),
    "septoriose-tomate": SoilDisease(
        name="septoriose de la tomate",
        latin="Septoria lycopersici",
        low=3,
        high=3,
        cross_family=False,
        hosts=("tomate",),
    ),
    "fletrissure-tomate": SoilDisease(
        name="flétrissure fusarienne de la tomate",
        latin="Fusarium oxysporum f. sp. lycopersici",
        low=5,
        high=7,
        cross_family=False,
        hosts=("tomate",),
    ),
}


@dataclass(frozen=True)
class CropDelayRow:
    """One line per crop: family, Fruchtfolge delay (N − 1, None if absent), SARE disease."""

    family: str
    fruchtfolge_years_without: int | None
    reference_disease: str | None
    perennial: bool = False


CROP_DELAYS: Final[dict[str, CropDelayRow]] = {
    "mais": CropDelayRow("Poacées", 1, "fusariose"),
    "ble-automne": CropDelayRow("Poacées", 1, "fusariose"),
    "orge": CropDelayRow("Poacées", 1, "fusariose"),
    "avoine": CropDelayRow("Poacées", 2, "fusariose"),
    "seigle": CropDelayRow("Poacées", 1, "fusariose"),
    "foin": CropDelayRow("Poacées", 0, None, perennial=True),
    "sarrasin": CropDelayRow("Polygonacées", 1, None),
    "soya": CropDelayRow("Fabacées", 2, "pourriture-brune"),
    "haricot-sec": CropDelayRow("Fabacées", 2, "pourridies-legumineuses"),
    "pois": CropDelayRow("Fabacées", 4, "pourridies-legumineuses"),
    "luzerne": CropDelayRow("Fabacées", 3, "anthracnose-luzerne", perennial=True),
    "canola": CropDelayRow("Brassicacées", 3, "jambe-noire"),
    "chou": CropDelayRow("Brassicacées", 4, "jambe-noire"),
    "navet": CropDelayRow("Brassicacées", 2, "pourriture-noire"),
    "radis": CropDelayRow("Brassicacées", 2, "pourriture-noire"),
    "pomme-de-terre": CropDelayRow("Solanacées", 2, "gale-commune"),
    "tomate": CropDelayRow("Solanacées", None, "septoriose-tomate"),
    "carotte": CropDelayRow("Apiacées", 3, "tache-profonde"),
    "celeri": CropDelayRow("Apiacées", 2, "septoriose-celeri"),
    "oignon": CropDelayRow("Amaryllidacées", 2, "brulure-botrytique"),
    "laitue": CropDelayRow("Astéracées", 1, "mildiou-laitue"),
    "epinard": CropDelayRow("Amaranthacées", 1, "mildiou-epinard"),
    "betterave": CropDelayRow("Amaranthacées", 3, "cercosporiose-betterave"),
    "courge": CropDelayRow("Cucurbitacées", 1, "anthracnose-cucurbitacees"),
}
