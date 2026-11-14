"""Sécheresse du sol racinaire, entre 0 (normal ou humide) et 1 (très sec).

Ordre des sources :
  1. SMAP L4 (satellite NASA, via AppEEARS, compte Earthdata) : percentile racinaire déjà
     calculé par la NASA (earthdata.smap_percentile) ;
  2. sinon MERRA-2 (modèle de la NASA, servi par NASA POWER avec la météo) : humidité
     racinaire GWETROOT, convertie ici en percentile de sa propre climatologie.

Percentile MERRA-2 : chaque jour de la saison de culture des ANNEES_RECENTES dernières
années est comparé aux jours à ± FENETRE_JOURS de la même date sur toute la période ;
on fait la moyenne. Sécheresse = (50 − percentile) / 40, bornée entre 0 et 1 : la même règle
que pour les nappes (notes.secheresse_depuis_percentile).
"""
from __future__ import annotations

import numpy as np

from .earthdata import ANNEES_RECENTES, mois_saison
from .notes import secheresse_depuis_percentile

FENETRE_JOURS = 15


def percentile_climatologique(dates, valeurs, lat: float, debut: int, fin: int,
                              annees_recentes: int = ANNEES_RECENTES,
                              fenetre: int = FENETRE_JOURS) -> float | None:
    v = np.asarray(valeurs, dtype=float)
    annees = dates.astype("datetime64[Y]").astype(int) + 1970
    mois = dates.astype("datetime64[M]").astype(int) % 12 + 1
    jda = (dates - dates.astype("datetime64[Y]")).astype(int) + 1
    ok = np.isfinite(v) & (annees >= debut) & (annees <= fin)
    recents = ok & (annees > fin - annees_recentes) & np.isin(mois, mois_saison(lat))
    if recents.sum() < 30 or (annees[ok].max() - annees[ok].min()) < 9:
        return None
    pcts = []
    for t in np.flatnonzero(recents):
        ecart = np.abs(jda - jda[t])
        ecart = np.minimum(ecart, 365 - ecart)
        echantillon = v[ok & (ecart <= fenetre)]
        pcts.append(100.0 * ((echantillon < v[t]).sum() + 0.5 * (echantillon == v[t]).sum())
                    / len(echantillon))
    return float(np.mean(pcts))


def secheresse_merra2(meteo, debut: int, fin: int) -> dict | None:
    if meteo.humidite_racines is None:
        return None
    p = percentile_climatologique(meteo.dates, meteo.humidite_racines, meteo.lat, debut, fin)
    if p is None:
        return None
    return dict(percentile=round(p, 1), secheresse=round(secheresse_depuis_percentile(p), 3),
                source=f"MERRA-2 GWETROOT via NASA POWER (modèle, pas une mesure ; "
                       f"saisons {fin - ANNEES_RECENTES + 1}-{fin} vs {debut}-{fin})")
