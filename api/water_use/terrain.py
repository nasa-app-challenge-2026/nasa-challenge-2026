"""Relief de la parcelle : pente tirée du SRTM (NASA, Shuttle Radar Topography Mission).

Source : SRTM GL1 (1 seconde d'arc, ~30 m), servi par l'API publique OpenTopoData
(https://api.opentopodata.org/v1/srtm30m, sans clé, 100 points et 1 requête par seconde au plus).

Le SRTM est arrondi au mètre et bruité de quelques mètres d'un pixel à l'autre : une pente
calculée entre deux pixels voisins serait fausse sur un champ plat. On lit donc une grille de
5 × 5 points espacés de 90 m (un carré de 360 m, la taille d'un champ) et on ajuste un plan
par moindres carrés ; la pente du plan est la pente de la parcelle.

La pente sert à corriger le curve number du ruissellement (voir ruissellement.ajuster_pente).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .reseau import ErreurDonnees, get_json

URL_OPENTOPO = "https://api.opentopodata.org/v1/srtm30m"
PAS_M = 90.0             # écart entre deux points de la grille
N_COTE = 5               # grille 5 × 5
M_PAR_DEGRE = 111_320.0  # longueur d'un degré de latitude (m)


@dataclass
class Terrain:
    altitude: float          # m, centre de la grille
    pente: float             # m/m (0,02 = 2 %)
    source: str
    details: dict = field(default_factory=dict)


def grille(lat: float, lon: float, pas: float = PAS_M, n: int = N_COTE):
    """Points (lat, lon) et leurs décalages (est, nord) en mètres autour du centre."""
    k = (n - 1) / 2
    m_par_deg_lon = M_PAR_DEGRE * math.cos(math.radians(lat))
    points, decalages = [], []
    for i in range(n):
        for j in range(n):
            nord, est = (i - k) * pas, (j - k) * pas
            points.append((lat + nord / M_PAR_DEGRE, lon + est / m_par_deg_lon))
            decalages.append((est, nord))
    return points, decalages


def pente_plan(decalages, altitudes) -> tuple[float, float]:
    """Plan z = a·est + b·nord + c ajusté par moindres carrés.
    Renvoie (pente en m/m, écart type des résidus en m)."""
    xy = np.asarray(decalages, dtype=float)
    z = np.asarray(altitudes, dtype=float)
    A = np.column_stack([xy[:, 0], xy[:, 1], np.ones(len(z))])
    coef, *_ = np.linalg.lstsq(A, z, rcond=None)
    residus = z - A @ coef
    return float(math.hypot(coef[0], coef[1])), float(residus.std())


def lire_reponse_opentopo(js: dict, decalages) -> Terrain:
    if not isinstance(js, dict) or js.get("status") != "OK":
        msg = js.get("error") if isinstance(js, dict) else js
        raise ErreurDonnees(f"Réponse SRTM (OpenTopoData) inattendue : {str(msg)[:300]}")
    alt = [r.get("elevation") for r in js.get("results", [])]
    if len(alt) != len(decalages) or any(a is None for a in alt):
        raise ErreurDonnees("Le SRTM n'a pas d'altitude à ce point (mer, ou hors de 56° S - 60° N). "
                            "Donnez la pente à la main avec --pente.")
    pente, bruit = pente_plan(decalages, alt)
    centre = alt[len(alt) // 2]
    return Terrain(float(centre), pente, source="SRTM 30 m (NASA) via OpenTopoData",
                   details=dict(pente_pct=round(100 * pente, 2),
                                denivele_m=float(max(alt) - min(alt)),
                                bruit_m=round(bruit, 1),
                                grille=f"{N_COTE}×{N_COTE} points espacés de {PAS_M:.0f} m"))


def terrain_srtm(lat: float, lon: float, utiliser_cache: bool = True) -> Terrain:
    points, decalages = grille(lat, lon)
    params = dict(locations="|".join(f"{a:.6f},{b:.6f}" for a, b in points),
                  interpolation="bilinear")
    js = get_json(URL_OPENTOPO, params, "SRTM (OpenTopoData)", timeout=60,
                  utiliser_cache=utiliser_cache)
    return lire_reponse_opentopo(js, decalages)
