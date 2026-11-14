"""Niveau 5 — connexion aux VRAIES bases (internet requis).

Désactivés par défaut. Pour les lancer :
    macOS / Linux :  WATER_USE_RESEAU=1 python -m pytest tests/test_5_vraies_bases.py -v
    Windows (PowerShell) :  $env:WATER_USE_RESEAU="1"; python -m pytest tests/test_5_vraies_bases.py -v

Points : un champ près de Saint-Hyacinthe, Montérégie (Québec) et Ames, Iowa (États-Unis, pour SSURGO).
"""
import numpy as np
import pytest

from water_use import earthdata
from water_use.era5 import telecharger_era5
from water_use.et0 import et0_meteo
from water_use.meteo import telecharger_power
from water_use.nappes import nappes_usgs
from water_use.notes import evaluer_rotation, pression_sur_l_eau
from water_use.rotation import lire_rotation
from water_use.sol import sol_soilgrids, sol_ssurgo, trouver_sol
from water_use.terrain import terrain_srtm

pytestmark = pytest.mark.reseau
QUEBEC = (45.55, -72.98)   # champ au sud-ouest de Saint-Hyacinthe (le centre-ville n'a pas de sol dans SoilGrids)
IOWA = (42.03, -93.65)


def test_nasa_power_une_annee_au_quebec():
    m = telecharger_power(*QUEBEC, 2023, 2023, utiliser_cache=False)
    assert len(m.dates) == 365
    assert 600 < m.pluie.sum() < 1600             # Montérégie : ~1000 mm/an
    assert m.tmin.min() < -10                     # hiver québécois
    assert m.tmax.max() > 25
    et0, methode = et0_meteo(m)
    assert 450 < et0.sum() < 900                  # ET0 annuelle d'un climat tempéré humide
    assert methode.startswith("Penman-Monteith")


def test_soilgrids_repond_au_quebec():
    s = sol_soilgrids(*QUEBEC, utiliser_cache=False)
    assert 10 < s.taw_haut < 90 and 40 < s.taw_bas < 350
    assert s.groupe_hydro in "ABCD"


def test_ssurgo_repond_en_iowa():
    s = sol_ssurgo(*IOWA, utiliser_cache=False)
    assert s is not None, "SSURGO n'a rien renvoyé pour Ames, Iowa"
    assert 80 < s.taw_total < 400
    assert s.groupe_hydro in "ABCD"


def test_ssurgo_vide_au_quebec():
    assert sol_ssurgo(*QUEBEC, utiliser_cache=False) is None


def test_power_donne_l_humidite_merra2():
    m = telecharger_power(*QUEBEC, 2023, 2023, utiliser_cache=False)
    assert m.humidite_racines is not None
    assert 0.1 < float(np.nanmean(m.humidite_racines)) < 1.0


def test_srtm_repond_au_quebec():
    t = terrain_srtm(*QUEBEC, utiliser_cache=False)
    assert 0 < t.altitude < 200                   # plaine du Saint-Laurent
    assert t.pente < 0.05


def test_usgs_nappes_en_iowa():
    n = nappes_usgs(*IOWA, 2005, 2024, utiliser_cache=False)
    assert n is not None, "aucun puits USGS suivi en continu trouvé près d'Ames"
    assert 0 <= n["percentile"] <= 100 and n["puits"][0]["distance_km"] <= 50


def test_usgs_rien_au_quebec():
    assert nappes_usgs(*QUEBEC, 2005, 2024, utiliser_cache=False) is None


def test_era5_au_quebec():
    e = telecharger_era5(*QUEBEC, 2023, 2023, utiliser_cache=False)
    assert len(e.dates) == 365
    assert 600 < np.nansum(e.pluie) < 1600
    assert 0.1 < np.nanmean(e.humidite_0_100) < 0.6


@pytest.mark.skipif(earthdata.identifiants() is None, reason="pas de compte NASA Earthdata configuré")
def test_smap_avec_compte_earthdata():
    try:
        s = earthdata.smap_percentile(*IOWA, 2024, attente_s=600)
    except earthdata.EnAttente as e:
        pytest.skip(f"tâche AppEEARS encore dans la file de la NASA ({e})")
    assert 0 <= s["percentile"] <= 100


def test_evaluation_complete_au_quebec(exemples):
    m = telecharger_power(*QUEBEC, 2014, 2023)
    sol = trouver_sol(*QUEBEC)
    et0, _ = et0_meteo(m)
    pr = pression_sur_l_eau(m, et0, 2015, 2023)
    assert pr["classe"] == "humide"
    for f in exemples.glob("*.json"):
        e = evaluer_rotation(lire_rotation(f), m, sol, 2015, 2023, et0=et0)
        assert 0 <= e.note <= 1
