"""Part de la pluie qui ruisselle : méthode des « curve numbers » du NRCS.

Valeurs : NRCS TR-55 (1986) tableau 2-2b et NEH 630 chapitre 9 tableau 9-1, condition
d'humidité moyenne (AMC II), Ia = 0,2 S. Colonnes = groupes hydrologiques A, B, C, D.
« SR » = rangs droits ; « CR » = résidus de culture (s'appliquent seulement si au moins 5 %
de la surface en est couverte ; « bon » = au moins 20 %).

Les tableaux valent pour une pente d'environ 5 %. Quand la pente de la parcelle est connue
(SRTM, voir terrain.py), le curve number est corrigé par la formule de Williams (1995),
reprise dans SWAT (Neitsch et al. 2011, Soil and Water Assessment Tool Theoretical
Documentation, éq. 2:1.1.3 et 2:1.1.4).
"""
from __future__ import annotations

import math

TABLE_CN = {
    "sol_nu":                     (77, 86, 91, 94),
    "jachere_residus_mediocre":   (76, 85, 90, 93),
    "jachere_residus_bon":        (74, 83, 88, 90),
    "rangs_mediocre":             (72, 81, 88, 91),
    "rangs_bon":                  (67, 78, 85, 89),
    "rangs_residus_mediocre":     (71, 80, 87, 90),
    "rangs_residus_bon":          (64, 75, 82, 85),
    "cereales_mediocre":          (65, 76, 84, 88),
    "cereales_bon":               (63, 75, 83, 87),
    "cereales_residus_mediocre":  (64, 75, 83, 86),
    "cereales_residus_bon":       (60, 72, 80, 84),
    "legumineuses_mediocre":      (66, 77, 85, 89),
    "legumineuses_bon":           (58, 72, 81, 85),
    "prairie":                    (30, 58, 71, 78),
}
COLONNE = {"A": 0, "B": 1, "C": 2, "D": 3}


def ajuster_pente(cn2: float, pente: float | None) -> float:
    """CN corrigé pour la pente (m/m). Inchangé à 5 %, plus bas sur terrain plat, plus haut
    sur pente forte. CN3 = CN2 · exp(0,00673 · (100 − CN2)) ;
    CN2 pente = (CN3 − CN2) / 3 · (1 − 2 · exp(−13,86 · pente)) + CN2."""
    if pente is None:
        return cn2
    cn3 = cn2 * math.exp(0.00673 * (100.0 - cn2))
    return min((cn3 - cn2) / 3.0 * (1.0 - 2.0 * math.exp(-13.86 * max(pente, 0.0))) + cn2, 99.0)


def curve_number(etat: str, groupe: str, pente: float | None = None) -> float:
    return ajuster_pente(float(TABLE_CN[etat][COLONNE[groupe.upper()]]), pente)


def etat_cn(type_cn: str | None, residus: float, bonne_condition: bool) -> str:
    """Choisit la ligne du tableau selon ce qui couvre le sol ce jour-là.
    type_cn None = pas de culture vivante (sol nu ou résidus)."""
    if type_cn is None:
        if residus < 0.05:
            return "sol_nu"
        return "jachere_residus_bon" if residus >= 0.20 else "jachere_residus_mediocre"
    if type_cn == "prairie":
        return "prairie"
    if type_cn == "legumineuses":
        return "legumineuses_bon" if bonne_condition else "legumineuses_mediocre"
    cond = "bon" if bonne_condition else "mediocre"
    if residus >= 0.05:
        return f"{type_cn}_residus_{cond}"
    return f"{type_cn}_{cond}"


def ruissellement(pluie_mm: float, cn: float) -> float:
    """Q = (P - 0,2 S)² / (P + 0,8 S), S = 25400/CN - 254 (mm). Nul si P <= 0,2 S."""
    if pluie_mm <= 0:
        return 0.0
    s = 25400.0 / cn - 254.0
    ia = 0.2 * s
    if pluie_mm <= ia:
        return 0.0
    return (pluie_mm - ia) ** 2 / (pluie_mm + 0.8 * s)
