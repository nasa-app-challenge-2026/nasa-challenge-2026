"""Soif de l'air : évapotranspiration de référence ET0 (mm/jour).

Penman-Monteith FAO-56 (Allen et al. 1998, chapitres 2 et 3, équation 6), pas de temps
journalier, flux de chaleur du sol G = 0. Repli : Hargreaves (FAO-56 éq. 52) quand l'humidité,
le vent ou le rayonnement manquent.
"""
from __future__ import annotations

import numpy as np

SIGMA = 4.903e-9  # constante de Stefan-Boltzmann, MJ K-4 m-2 jour-1


def pression_saturante(t):
    """e°(T) en kPa (FAO-56 éq. 11)."""
    return 0.6108 * np.exp(17.27 * t / (t + 237.3))


def rayonnement_extraterrestre(lat_deg, jour_annee):
    """Ra en MJ/m²/jour (FAO-56 éq. 21 à 25)."""
    phi = np.radians(lat_deg)
    j = np.asarray(jour_annee, dtype=float)
    dr = 1 + 0.033 * np.cos(2 * np.pi * j / 365)
    delta = 0.409 * np.sin(2 * np.pi * j / 365 - 1.39)
    ws = np.arccos(np.clip(-np.tan(phi) * np.tan(delta), -1.0, 1.0))
    return (24 * 60 / np.pi) * 0.0820 * dr * (
        ws * np.sin(phi) * np.sin(delta) + np.cos(phi) * np.cos(delta) * np.sin(ws))


def et0_penman_monteith(tmax, tmin, rs, u2, lat, altitude, jour_annee, rh_moy=None, ea=None):
    """ET0 FAO-56. `ea` (kPa) prime sur `rh_moy` (%) si les deux sont fournis."""
    tmax, tmin = np.asarray(tmax, float), np.asarray(tmin, float)
    tmoy = (tmax + tmin) / 2
    P = 101.3 * ((293 - 0.0065 * altitude) / 293) ** 5.26        # éq. 7
    gamma = 0.000665 * P                                           # éq. 8
    delta = 4098 * pression_saturante(tmoy) / (tmoy + 237.3) ** 2  # éq. 13
    es = (pression_saturante(tmax) + pression_saturante(tmin)) / 2
    if ea is None:
        ea = np.asarray(rh_moy, float) / 100.0 * es                # éq. 19
    ea = np.minimum(np.asarray(ea, float), es)
    ra = rayonnement_extraterrestre(lat, jour_annee)
    rso = (0.75 + 2e-5 * altitude) * ra                            # éq. 37
    rns = 0.77 * np.asarray(rs, float)                             # éq. 38, albédo 0,23
    rs_a = np.asarray(rs, float)
    rso_b = np.array(np.broadcast_to(rso, np.broadcast(rs_a, rso).shape), dtype=float)
    rapport = np.clip(np.divide(rs_a, rso_b, out=np.ones_like(rso_b), where=rso_b > 0), 0.3, 1.0)
    rnl = SIGMA * ((tmax + 273.16) ** 4 + (tmin + 273.16) ** 4) / 2 * (
        0.34 - 0.14 * np.sqrt(np.maximum(ea, 0))) * (1.35 * rapport - 0.35)   # éq. 39
    rn = rns - rnl
    u2 = np.maximum(np.asarray(u2, float), 0.5)                    # FAO-56 : u2 >= 0,5 m/s
    num = 0.408 * delta * rn + gamma * 900 / (tmoy + 273) * u2 * (es - ea)
    den = delta + gamma * (1 + 0.34 * u2)
    return np.maximum(num / den, 0.0)


def et0_hargreaves(tmax, tmin, lat, jour_annee):
    """ET0 de Hargreaves (FAO-56 éq. 52), températures seulement."""
    tmax, tmin = np.asarray(tmax, float), np.asarray(tmin, float)
    ra = rayonnement_extraterrestre(lat, jour_annee)
    return np.maximum(0.0023 * ((tmax + tmin) / 2 + 17.8) * np.sqrt(np.maximum(tmax - tmin, 0))
                      * 0.408 * ra, 0.0)


def et0_meteo(meteo) -> tuple[np.ndarray, str]:
    """ET0 quotidienne pour un objet Meteo ; Hargreaves là où une donnée manque."""
    pm = et0_penman_monteith(meteo.tmax, meteo.tmin, meteo.rs, meteo.u2, meteo.lat,
                             meteo.altitude, meteo.jour_annee, rh_moy=meteo.rh)
    hg = et0_hargreaves(meteo.tmax, meteo.tmin, meteo.lat, meteo.jour_annee)
    ok = np.isfinite(pm)
    methode = "Penman-Monteith FAO-56" if ok.all() else (
        f"Penman-Monteith FAO-56 ({(~ok).sum()} jours en Hargreaves)")
    return np.where(ok, pm, hg), methode
