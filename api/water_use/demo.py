"""Données de démonstration SANS réseau (météo et sol synthétiques, reproductibles).

Sert à vérifier que le programme tourne et aux tests automatiques. Les vraies données
viennent de meteo.py (NASA POWER) et sol.py (SSURGO / SoilGrids).
  - "humide" : climat continental humide (~1000 mm/an, pluie toute l'année, hiver enneigé)
  - "sec"    : climat semi-aride à été sec (~380 mm/an, presque rien en juin-août)
"""
from __future__ import annotations

import numpy as np

from .et0 import rayonnement_extraterrestre
from .meteo import Meteo
from .sol import sol_manuel

CLIMATS = {
    "humide": dict(lat=45.4, t_moy=6.5, amplitude=15.5, pluie_an=1000, ete_sec=False, rh=75),
    "sec":    dict(lat=38.0, t_moy=14.0, amplitude=10.0, pluie_an=380, ete_sec=True, rh=50),
}


def meteo_demo(climat: str = "humide", debut: int = 2004, fin: int = 2024, graine: int = 7) -> Meteo:
    p = CLIMATS[climat]
    rng = np.random.default_rng(graine)
    dates = np.arange(np.datetime64(f"{debut}-01-01"), np.datetime64(f"{fin + 1}-01-01"))
    j = (dates - dates.astype("datetime64[Y]")).astype(int) + 1
    saison = -np.cos(2 * np.pi * (j - 15) / 365)                 # -1 mi-janvier, +1 mi-juillet
    tmoy = p["t_moy"] + p["amplitude"] * saison + rng.normal(0, 3, len(dates))
    tmax, tmin = tmoy + 5.5, tmoy - 5.5
    if p["ete_sec"]:
        proba = np.clip(0.28 - 0.26 * np.clip(saison, 0, 1) ** 0.5, 0.02, 0.4)
    else:
        proba = np.full(len(dates), 0.33)
    pluie_jour = rng.random(len(dates)) < proba
    quantite = rng.gamma(0.8, 1.0, len(dates)) * pluie_jour
    annees = dates.astype("datetime64[Y]").astype(int) + 1970
    for y in np.unique(annees):                                  # ~pluie_an chaque année ±15 %
        m = annees == y
        cible = p["pluie_an"] * rng.uniform(0.85, 1.15)
        if quantite[m].sum() > 0:
            quantite[m] *= cible / quantite[m].sum()
    ra = rayonnement_extraterrestre(p["lat"], j)
    rs = ra * np.where(pluie_jour, 0.35, 0.6)
    rh = np.clip(p["rh"] + 15 * pluie_jour - 10 * np.clip(saison, 0, 1) * p["ete_sec"], 20, 98)
    u2 = np.full(len(dates), 2.0)
    return Meteo(dates, tmax, tmin, rh, u2, rs, quantite, p["lat"], -73.0, 50.0,
                 source=f"DÉMO synthétique ({climat}) — pas une vraie météo")


def sol_demo():
    s = sol_manuel(sable=40, argile=20, mo=3.0)
    s.source = "DÉMO : loam (40 % sable, 20 % argile, 3 % MO) — pas un vrai sol"
    return s
