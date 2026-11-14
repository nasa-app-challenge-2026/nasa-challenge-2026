"""Niveau 2 — les réponses des vraies bases sont bien lues (réponses d'exemple au format
documenté de chaque API ; aucun accès réseau)."""
import numpy as np
import pytest

from water_use.meteo import lire_reponse_power
from water_use.reseau import ErreurDonnees
from water_use.sol import lire_reponse_soilgrids, lire_reponse_ssurgo, requete_ssurgo


def _power(unite_rs="MJ/m^2/day", rs=20.0):
    jours = ["20230101", "20230102", "20230103"]
    p = lambda v: {j: v for j in jours}
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-72.95, 45.4, 37.5]},
        "properties": {"parameter": {
            "T2M_MAX": p(2.0), "T2M_MIN": {"20230101": -8.0, "20230102": -999.0, "20230103": -6.0},
            "RH2M": p(80.0), "WS2M": p(3.0), "ALLSKY_SFC_SW_DWN": p(rs),
            "PRECTOTCORR": {"20230101": 1.5, "20230102": -999.0, "20230103": 0.0}}},
        "header": {"fill_value": -999.0},
        "parameters": {"ALLSKY_SFC_SW_DWN": {"units": unite_rs}},
    }


def test_lecture_power():
    m = lire_reponse_power(_power(), 45.4, -72.95)
    assert len(m.dates) == 3 and str(m.dates[0]) == "2023-01-01"
    assert m.altitude == 37.5
    assert np.isfinite(m.tmin).all()             # le -999 a été bouché
    assert m.pluie[1] == 0.0                     # pluie manquante -> 0
    assert m.jours_bouches == 2


def test_power_conversion_kwh_en_mj():
    m = lire_reponse_power(_power("kW-hr/m^2/day", rs=5.0), 45.4, -72.95)
    assert m.rs[0] == pytest.approx(18.0)


def test_power_reponse_erreur():
    with pytest.raises(ErreurDonnees):
        lire_reponse_power({"messages": ["mauvaise requête"]}, 0, 0)


def _soilgrids(sable=400, argile=200, soc=150):
    profs = ["0-5cm", "5-15cm", "15-30cm", "30-60cm", "60-100cm", "100-200cm"]
    couche = lambda nom, v: {"name": nom, "unit_measure": {"d_factor": 10},
                             "depths": [{"label": d, "values": {"mean": v}} for d in profs]}
    return {"properties": {"layers": [couche("sand", sable), couche("clay", argile),
                                      couche("soc", soc)]}}


def test_lecture_soilgrids():
    s = lire_reponse_soilgrids(_soilgrids())
    assert s.details["texture_0_30cm"] == "loam"
    assert s.groupe_hydro == "B"
    assert 35 < s.taw_haut < 55                 # ~0,15 m³/m³ × 300 mm
    assert 140 < s.taw_bas < 210


def test_soilgrids_point_sans_donnees():
    js = _soilgrids()
    js["properties"]["layers"][0]["depths"][0]["values"]["mean"] = None
    with pytest.raises(ErreurDonnees):
        lire_reponse_soilgrids(js)


def test_lecture_ssurgo():
    js = {"Table": [["mukey", "muname", "aws025wta", "aws0150wta", "hydgrpdcd"],
                    ["411278", "Clarion loam, 2 to 6 percent slopes", "4.5", "25.1", "B"]]}
    s = lire_reponse_ssurgo(js)
    assert s.taw_haut == pytest.approx(54.0)    # 4,5 cm sur 0-25 cm -> 54 mm sur 0-30 cm
    assert s.taw_total == pytest.approx(251.0)
    assert s.groupe_hydro == "B"


def test_ssurgo_vide_ou_groupe_double():
    assert lire_reponse_ssurgo({}) is None
    js = {"Table": [["mukey", "muname", "aws025wta", "aws0150wta", "hydgrpdcd"],
                    ["1", "x", "3", "20", "C/D"]]}
    assert lire_reponse_ssurgo(js).groupe_hydro == "C"


def test_requete_ssurgo_longitude_avant_latitude():
    assert "point(-93.650000 42.030000)" in requete_ssurgo(42.03, -93.65)
