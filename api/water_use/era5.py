"""ERA5 (réanalyse ECMWF / Copernicus), servi sans clé par l'API historique d'Open-Meteo.

API : https://archive-api.open-meteo.com/v1/archive  (modèle « era5 », maille ~25 km, 1940 à
aujourd'hui ; données ERA5 sous licence CC BY 4.0, usage non commercial gratuit chez Open-Meteo).
L'accès officiel (Copernicus Climate Data Store) demande une clé et des fichiers GRIB/NetCDF ;
Open-Meteo renvoie directement la série quotidienne au point.

Sert de source INDÉPENDANTE de NASA POWER pour la commande « valider » :
  precipitation_sum               pluie + neige (mm/jour)
  et0_fao_evapotranspiration      ET0 FAO-56 calculée par Open-Meteo à partir d'ERA5 (mm/jour)
  soil_moisture_0_to_100cm_mean   humidité du sol 0-100 cm (m³/m³)
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .reseau import ErreurDonnees, get_json

URL_OPEN_METEO = "https://archive-api.open-meteo.com/v1/archive"
VARIABLES = ["precipitation_sum", "et0_fao_evapotranspiration", "soil_moisture_0_to_100cm_mean"]


@dataclass
class Era5:
    dates: np.ndarray
    pluie: np.ndarray
    et0: np.ndarray
    humidite_0_100: np.ndarray
    lat: float
    lon: float
    source: str = "ERA5 (ECMWF) via Open-Meteo"


def lire_reponse_era5(js: dict) -> Era5:
    if not isinstance(js, dict) or "daily" not in js:
        msg = js.get("reason") if isinstance(js, dict) else js
        raise ErreurDonnees(f"Réponse ERA5 (Open-Meteo) inattendue : {str(msg)[:300]}")
    d = js["daily"]
    dates = np.array(d["time"], dtype="datetime64[D]")

    def serie(nom):
        return np.array([np.nan if x is None else x for x in d.get(nom, [None] * len(dates))],
                        dtype=float)

    return Era5(dates, serie("precipitation_sum"), serie("et0_fao_evapotranspiration"),
                serie("soil_moisture_0_to_100cm_mean"), float(js.get("latitude", np.nan)),
                float(js.get("longitude", np.nan)))


def telecharger_era5(lat: float, lon: float, debut: int, fin: int,
                     utiliser_cache: bool = True) -> Era5:
    params = dict(latitude=f"{lat:.4f}", longitude=f"{lon:.4f}", start_date=f"{debut}-01-01",
                  end_date=f"{fin}-12-31", daily=",".join(VARIABLES), models="era5",
                  timezone="GMT")
    js = get_json(URL_OPEN_METEO, params, "ERA5 (Open-Meteo)", timeout=120,
                  utiliser_cache=utiliser_cache)
    return lire_reponse_era5(js)
