"""Météo quotidienne NASA POWER (vraie base, API publique, sans clé).

API : https://power.larc.nasa.gov/api/temporal/daily/point
Communauté AG (agroclimatologie). Variables demandées :
  T2M_MAX, T2M_MIN  température max/min à 2 m (°C)
  RH2M              humidité relative moyenne à 2 m (%)
  WS2M              vent à 2 m (m/s)
  ALLSKY_SFC_SW_DWN rayonnement solaire au sol (MJ/m²/jour en communauté AG)
  PRECTOTCORR       pluie corrigée (mm/jour)
  GWETROOT          humidité du sol racinaire, 0 = sec, 1 = saturé (modèle MERRA-2 de la NASA) ;
                    sert seulement à la pression sur l'eau quand SMAP n'est pas disponible
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .reseau import ErreurDonnees, get_json

URL_POWER = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMETRES = ["T2M_MAX", "T2M_MIN", "RH2M", "WS2M", "ALLSKY_SFC_SW_DWN", "PRECTOTCORR", "GWETROOT"]


@dataclass
class Meteo:
    dates: np.ndarray        # datetime64[D]
    tmax: np.ndarray         # °C
    tmin: np.ndarray         # °C
    rh: np.ndarray           # % (moyenne du jour), NaN si inconnue
    u2: np.ndarray           # m/s à 2 m, NaN si inconnu
    rs: np.ndarray           # MJ/m²/jour, NaN si inconnu
    pluie: np.ndarray        # mm/jour
    lat: float
    lon: float
    altitude: float          # m
    source: str = ""
    jours_bouches: int = 0   # valeurs manquantes remplacées
    humidite_racines: np.ndarray | None = None   # GWETROOT MERRA-2 (0-1), NaN si manquante

    @property
    def annees(self) -> np.ndarray:
        return self.dates.astype("datetime64[Y]").astype(int) + 1970

    @property
    def mois(self) -> np.ndarray:
        return self.dates.astype("datetime64[M]").astype(int) % 12 + 1

    @property
    def jour_annee(self) -> np.ndarray:
        return (self.dates - self.dates.astype("datetime64[Y]")).astype(int) + 1

    def sous_periode(self, debut: int, fin: int) -> "Meteo":
        m = (self.annees >= debut) & (self.annees <= fin)
        return Meteo(self.dates[m], self.tmax[m], self.tmin[m], self.rh[m], self.u2[m],
                     self.rs[m], self.pluie[m], self.lat, self.lon, self.altitude,
                     self.source, self.jours_bouches,
                     None if self.humidite_racines is None else self.humidite_racines[m])


def _boucher(valeurs: np.ndarray, jour_annee: np.ndarray, zero_si_vide: bool = False):
    """Remplace les trous : moyenne du même jour de l'année, sinon interpolation."""
    v = valeurs.astype(float).copy()
    trous = ~np.isfinite(v)
    n = int(trous.sum())
    if n == 0:
        return v, 0
    if zero_si_vide:
        v[trous] = 0.0
        return v, n
    for j in np.unique(jour_annee[trous]):
        memes = (jour_annee == j) & ~trous
        if memes.any():
            v[trous & (jour_annee == j)] = np.nanmean(valeurs[memes])
    reste = ~np.isfinite(v)
    if reste.any() and (~reste).any():
        idx = np.arange(len(v))
        v[reste] = np.interp(idx[reste], idx[~reste], v[~reste])
    return v, n


def lire_reponse_power(js: dict, lat: float, lon: float) -> Meteo:
    """Transforme la réponse JSON de NASA POWER en objet Meteo (testable hors ligne)."""
    try:
        param = js["properties"]["parameter"]
    except (KeyError, TypeError):
        msg = js.get("messages") or js.get("message") or js.get("errors") if isinstance(js, dict) else js
        raise ErreurDonnees(f"Réponse NASA POWER inattendue : {str(msg)[:300]}")
    remplissage = float(js.get("header", {}).get("fill_value", -999))
    unites = {k: v.get("units", "") for k, v in js.get("parameters", {}).items()}
    cles = sorted(param["T2M_MAX"].keys())
    dates = np.array([f"{c[:4]}-{c[4:6]}-{c[6:8]}" for c in cles], dtype="datetime64[D]")

    def serie(nom):
        d = param.get(nom, {})
        a = np.array([d.get(c, np.nan) for c in cles], dtype=float)
        a[(a == remplissage) | (a <= -998)] = np.nan
        return a

    rs = serie("ALLSKY_SFC_SW_DWN")
    if "kw" in unites.get("ALLSKY_SFC_SW_DWN", "").lower():   # kWh/m²/jour -> MJ/m²/jour
        rs = rs * 3.6
    elif "w/m" in unites.get("ALLSKY_SFC_SW_DWN", "").lower():  # W/m² moyen -> MJ/m²/jour
        rs = rs * 0.0864
    jda = (dates - dates.astype("datetime64[Y]")).astype(int) + 1
    total = 0
    tmax, n = _boucher(serie("T2M_MAX"), jda); total += n
    tmin, n = _boucher(serie("T2M_MIN"), jda); total += n
    pluie, n = _boucher(serie("PRECTOTCORR"), jda, zero_si_vide=True); total += n
    rh, n = _boucher(serie("RH2M"), jda); total += n
    u2, n = _boucher(serie("WS2M"), jda); total += n
    rs, n = _boucher(rs, jda); total += n
    humidite = serie("GWETROOT") if "GWETROOT" in param else None   # trous laissés en NaN
    if humidite is not None and not np.isfinite(humidite).any():
        humidite = None
    coords = js.get("geometry", {}).get("coordinates", [lon, lat, 0])
    altitude = float(coords[2]) if len(coords) > 2 and coords[2] is not None else 0.0
    return Meteo(dates, tmax, tmin, rh, u2, rs, np.maximum(pluie, 0.0), lat, lon, altitude,
                 source="NASA POWER (communauté AG, quotidien)", jours_bouches=total,
                 humidite_racines=humidite)


def telecharger_power(lat: float, lon: float, debut: int, fin: int,
                      utiliser_cache: bool = True) -> Meteo:
    """Télécharge la météo quotidienne du 1er janvier `debut` au 31 décembre `fin`."""
    import datetime as _dt
    fin_date = min(_dt.date(fin, 12, 31), _dt.date.today() - _dt.timedelta(days=10))
    if fin_date < _dt.date(fin, 12, 31):
        raise ErreurDonnees(f"L'année {fin} n'est pas encore complète dans NASA POWER : "
                            f"choisissez une fin au plus égale à {fin_date.year - 1}.")
    params = dict(parameters=",".join(PARAMETRES), community="AG", longitude=f"{lon:.4f}",
                  latitude=f"{lat:.4f}", start=f"{debut}0101", end=fin_date.strftime("%Y%m%d"),
                  format="JSON")
    js = get_json(URL_POWER, params, "NASA POWER", timeout=180, utiliser_cache=utiliser_cache)
    return lire_reponse_power(js, lat, lon)
