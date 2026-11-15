"""Niveau 2c — lecture des nouvelles bases (SRTM, USGS, SMAP/ECOSTRESS par AppEEARS, ERA5,
MERRA-2 par NASA POWER), avec des réponses au format documenté de chaque API, sans réseau."""
from pathlib import Path

import numpy as np
import pytest

from water_use import earthdata
from water_use.era5 import lire_reponse_era5
from water_use.humidite import percentile_climatologique, secheresse_merra2
from water_use.meteo import lire_reponse_power
from water_use.nappes import choisir_puits, dans_les_etats_unis, percentile_recent
from water_use.notes import secheresse_depuis_percentile
from water_use.reseau import ErreurDonnees
from water_use.terrain import grille, lire_reponse_opentopo


# ---------------- SRTM (OpenTopoData)
def test_lecture_srtm():
    _, dec = grille(45.63, -72.96)
    js = {"status": "OK", "results": [{"elevation": 30 + 0.01 * n, "dataset": "srtm30m"}
                                      for e, n in dec]}
    t = lire_reponse_opentopo(js, dec)
    assert t.pente == pytest.approx(0.01, abs=1e-6)
    assert t.altitude == pytest.approx(30.0)
    assert t.details["pente_pct"] == 1.0


def test_srtm_sans_donnee_ou_erreur():
    _, dec = grille(70.0, 10.0)
    with pytest.raises(ErreurDonnees, match="--pente"):
        lire_reponse_opentopo({"status": "OK", "results": [{"elevation": None}] * 25}, dec)
    with pytest.raises(ErreurDonnees):
        lire_reponse_opentopo({"status": "INVALID_REQUEST", "error": "trop de points"}, dec)


# ---------------- USGS
def _meta(ident, lon, lat, debut, fin, periode="Daily", stat="00003"):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"monitoring_location_id": ident, "computation_period_identifier": periode,
                           "statistic_id": stat, "begin": f"{debut}-01-01T00:00:00",
                           "end": f"{fin}-06-01T00:00:00", "parameter_code": "72019"}}


def test_choix_des_puits():
    feats = [_meta("USGS-proche", -93.70, 42.05, 2005, 2026),
             _meta("USGS-loin", -92.50, 42.03, 2000, 2026),          # ~95 km
             _meta("USGS-court", -93.66, 42.04, 2020, 2026),         # 5 ans seulement
             _meta("USGS-arrete", -93.64, 42.02, 1990, 2015),        # plus mesuré
             _meta("USGS-points", -93.65, 42.03, 2000, 2026, periode="Points"),
             _meta("USGS-proche", -93.70, 42.05, 2005, 2026, stat="00001")]
    puits = choisir_puits(feats, 42.03, -93.65, 2024)
    assert [p["id"] for p in puits] == ["USGS-proche"]
    assert puits[0]["distance_km"] < 6


def test_percentile_des_nappes():
    # 20 ans, profondeur stable, puis 3 dernières années : nappe plus basse (plus profonde)
    mesures = []
    for a in range(2005, 2025):
        for m in range(1, 13):
            prof = 10.0 + 0.01 * (a - 2005) if a < 2022 else 15.0
            mesures.append((f"{a}-{m:02d}-15", prof))
    assert percentile_recent(mesures, 2024) < 15
    hautes = [(d, 5.0 if d >= "2022" else v) for d, v in mesures]
    assert percentile_recent(hautes, 2024) > 85
    assert percentile_recent(mesures[-60:], 2024) is None    # 5 ans d'histoire : pas jugé


def test_hors_etats_unis_et_conversion():
    assert dans_les_etats_unis(42.03, -93.65)
    assert not dans_les_etats_unis(48.85, 2.35)              # Paris
    assert not dans_les_etats_unis(52.13, -106.67)           # Saskatoon
    assert not dans_les_etats_unis(19.43, -99.13)            # Mexico
    # le sud du Québec tombe dans la boîte large : l'API répond qu'aucun puits n'est à 50 km
    assert secheresse_depuis_percentile(50) == 0.0
    assert secheresse_depuis_percentile(10) == 1.0
    assert secheresse_depuis_percentile(30) == pytest.approx(0.5)


# ---------------- AppEEARS (SMAP, ECOSTRESS)
CSV_SMAP = """ID,Latitude,Longitude,Date,SPL4SMGP_008_Line_Y_9km,SPL4SMGP_008_Sample_X_9km,SPL4SMGP_008_Geophysical_Data_sm_rootzone_pctl
parcelle,45.63,-72.96,2024-05-01,123,456,35.5
parcelle,45.63,-72.96,2024-05-01,123,456,-9999.0
parcelle,45.63,-72.96,2024-05-11,123,456,
parcelle,45.63,-72.96,2024-05-21,123,456,40.5
"""


def test_lecture_csv_appeears():
    v = earthdata.lire_csv_appeears(CSV_SMAP, "Geophysical_Data_sm_rootzone_pctl")
    assert v == [("2024-05-01", 35.5), ("2024-05-21", 40.5)]
    with pytest.raises(ErreurDonnees):
        earthdata.lire_csv_appeears("ID,Date,autre\n1,2024-01-01,3\n", "ESI")


class _Reponse:
    def __init__(self, corps):
        self.corps = corps
        self.text = corps if isinstance(corps, str) else ""

    def json(self):
        return self.corps


def test_tache_appeears_trouve_le_csv_d_ecostress(monkeypatch, tmp_path):
    """AppEEARS nomme le CSV avec des tirets, tiret bas compris (« ECO-L4T-ESI-002 ») : noms
    relevés sur une vraie tâche le 15 novembre 2026."""
    from water_use import reseau
    monkeypatch.setattr(reseau, "DOSSIER_CACHE", tmp_path)
    csv_esi = ("ID,Latitude,Longitude,Date,MODIS_Tile,ECO_L4T_ESI_002_ESI\n"
               "parcelle,45.55,-72.98,2024-07-01,h12v04,0.62\n")
    reponses = {
        ("POST", "task"): {"task_id": "t1"},
        ("GET", "task/t1"): {"status": "done"},
        ("GET", "bundle/t1"): {"files": [
            {"file_type": "txt", "file_name": "water-use-ecostress-granule-list.txt", "file_id": "g"},
            {"file_type": "csv", "file_name": "water-use-ecostress-ECO-L4T-ESI-002-results.csv",
             "file_id": "f1"},
        ]},
        ("GET", "bundle/t1/f1"): csv_esi,
    }
    monkeypatch.setattr(earthdata, "_appel", lambda methode, chemin, **k: _Reponse(
        reponses[(methode, chemin)]))
    valeurs = earthdata.tache_point("water-use-ecostress", *earthdata.ECOSTRESS, [], 45.55, -72.98,
                                    attente_s=0, utiliser_cache=False, journal=lambda *_: None)
    assert valeurs == [("2024-07-01", 0.62)]


def test_dates_smap_courtes():
    d = earthdata.dates_smap(45.6, 2024)
    assert len(d) == 3 * 5 * 3                               # 3 ans × 5 mois × 3 jours
    assert d[0] == {"startDate": "05-01-2022", "endDate": "05-01-2022"}


def test_anomalie_esi():
    vals = []
    for a in range(2018, 2025):
        esi = 0.7 if a < 2022 else 0.5                       # 3 dernières saisons plus sèches
        vals += [(f"{a}-07-{j:02d}", esi + 0.01 * (j % 3)) for j in range(1, 20)]
    anomalie, par_an = earthdata.anomalie_par_saison(vals, 45.0, 3, 2024)
    assert anomalie < -0.8 and len(par_an) == 7
    trop_peu, _ = earthdata.anomalie_par_saison(vals[:40], 45.0, 3, 2024)
    assert trop_peu is None


def test_anomalie_esi_du_vrai_fichier_earthdata():
    """Le CSV qu'AppEEARS (NASA Earthdata) a rendu le 15 novembre 2026 pour la tâche
    « water-use-ecostress » au point 45,55 ; -72,98 (Saint-Hyacinthe), saisons 2018 à 2024 :
    61 valeurs lues ; 2019 et 2024 ont moins de 5 images et ne comptent pas ; les trois
    dernières saisons sont un peu plus stressées que d'habitude."""
    fichier = Path(__file__).parent / "donnees" / "appeears-ecostress-esi-saint-hyacinthe.csv"
    valeurs = earthdata.lire_csv_appeears(fichier.read_text(encoding="utf-8"), earthdata.ECOSTRESS[1])
    assert len(valeurs) == 61
    assert valeurs[0] == ("2018-07-30", 0.4276828)
    anomalie, par_an = earthdata.anomalie_par_saison(valeurs, 45.55, earthdata.ANNEES_RECENTES, 2024)
    assert sorted(par_an) == [2018, 2020, 2021, 2022, 2023]
    assert anomalie == pytest.approx(-0.23, abs=0.005)


def test_identifiants_earthdata(monkeypatch, tmp_path):
    from water_use import reseau
    monkeypatch.setattr(reseau, "FICHIER_ENV", tmp_path / ".env")     # ignore le vrai .env
    monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
    monkeypatch.delenv("EARTHDATA_PASSWORD", raising=False)
    (tmp_path / ".env").write_text('# commentaire\nEARTHDATA_USERNAME=moi_env\n'
                                   'EARTHDATA_PASSWORD="N@s a=1"\n', encoding="utf-8")
    assert earthdata.identifiants() == ("moi_env", "N@s a=1")        # guillemets, @, = et espace
    monkeypatch.setenv("EARTHDATA_USERNAME", "moi")
    monkeypatch.setenv("EARTHDATA_PASSWORD", "secret")
    assert earthdata.identifiants() == ("moi", "secret")
    monkeypatch.delenv("EARTHDATA_USERNAME")
    monkeypatch.delenv("EARTHDATA_PASSWORD")
    (tmp_path / ".env").unlink()
    monkeypatch.setattr(earthdata.Path, "home", lambda: tmp_path)
    assert earthdata.identifiants() is None
    (tmp_path / ".netrc").write_text("machine urs.earthdata.nasa.gov login moi2 password s2\n")
    assert earthdata.identifiants() == ("moi2", "s2")


# ---------------- MERRA-2 (NASA POWER GWETROOT)
def _dates(debut, fin):
    return np.arange(np.datetime64(f"{debut}-01-01"), np.datetime64(f"{fin + 1}-01-01"))


def test_percentile_merra2():
    d = _dates(2005, 2024)
    annees = d.astype("datetime64[Y]").astype(int) + 1970
    rng = np.random.default_rng(1)
    humid = 0.6 + 0.02 * rng.standard_normal(len(d))
    sec = np.where(annees >= 2022, humid - 0.1, humid)       # 3 dernières années plus sèches
    assert percentile_climatologique(d, humid, 45.0, 2005, 2024) == pytest.approx(50, abs=8)
    assert percentile_climatologique(d, sec, 45.0, 2005, 2024) < 20
    assert percentile_climatologique(d[-800:], sec[-800:], 45.0, 2005, 2024) is None


def test_power_lit_gwetroot():
    jours = ["20230701", "20230702"]
    p = lambda v: {j: v for j in jours}
    js = {"properties": {"parameter": {
        "T2M_MAX": p(25.0), "T2M_MIN": p(12.0), "RH2M": p(70.0), "WS2M": p(2.0),
        "ALLSKY_SFC_SW_DWN": p(22.0), "PRECTOTCORR": p(1.0),
        "GWETROOT": {"20230701": 0.61, "20230702": -999.0}}},
        "header": {"fill_value": -999.0}, "geometry": {"coordinates": [0, 0, 10]}}
    m = lire_reponse_power(js, 45.0, -73.0)
    assert m.humidite_racines[0] == pytest.approx(0.61) and np.isnan(m.humidite_racines[1])
    assert m.jours_bouches == 0                              # GWETROOT n'est pas bouché
    del js["properties"]["parameter"]["GWETROOT"]
    m2 = lire_reponse_power(js, 45.0, -73.0)
    assert m2.humidite_racines is None and secheresse_merra2(m2, 2005, 2024) is None


# ---------------- ERA5 (Open-Meteo)
def test_lecture_era5():
    js = {"latitude": 45.75, "longitude": -73.0, "daily": {
        "time": ["2023-07-01", "2023-07-02"], "precipitation_sum": [0.8, None],
        "et0_fao_evapotranspiration": [3.86, 2.48], "soil_moisture_0_to_100cm_mean": [0.281, 0.291]}}
    e = lire_reponse_era5(js)
    assert str(e.dates[0]) == "2023-07-01" and e.pluie[0] == 0.8 and np.isnan(e.pluie[1])
    assert e.humidite_0_100[1] == pytest.approx(0.291)
    with pytest.raises(ErreurDonnees):
        lire_reponse_era5({"error": True, "reason": "Parameter 'daily' is invalid"})
