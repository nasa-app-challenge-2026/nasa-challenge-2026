"""Niveau 2b — toute la chaîne de la ligne de commande avec des réponses d'API simulées
(mêmes formats que NASA POWER, SoilGrids, Soil Data Access, OpenTopoData, USGS et
Open-Meteo), sans réseau."""
import json

import numpy as np
import pytest

import water_use.earthdata as earthdata_mod
import water_use.era5 as era5_mod
import water_use.meteo as meteo_mod
import water_use.nappes as nappes_mod
import water_use.sol as sol_mod
import water_use.terrain as terrain_mod
from water_use.cli import main
from water_use.demo import meteo_demo


def _reponse_power_depuis_demo(debut, fin):
    m = meteo_demo("humide", debut, fin)
    cles = [str(d).replace("-", "") for d in m.dates]
    serie = lambda a: dict(zip(cles, [round(float(x), 3) for x in a]))
    # humidité racinaire synthétique : suit la pluie des 30 derniers jours
    humid = np.clip(0.3 + np.convolve(m.pluie, np.ones(30) / 30, mode="same") / 10, 0, 1)
    return {"type": "Feature", "geometry": {"coordinates": [-72.96, 45.63, 40.0]},
            "properties": {"parameter": {
                "T2M_MAX": serie(m.tmax), "T2M_MIN": serie(m.tmin), "RH2M": serie(m.rh),
                "WS2M": serie(m.u2), "ALLSKY_SFC_SW_DWN": serie(m.rs),
                "PRECTOTCORR": serie(m.pluie), "GWETROOT": serie(humid)}},
            "header": {"fill_value": -999},
            "parameters": {"ALLSKY_SFC_SW_DWN": {"units": "MJ/m^2/day"}}}


def _reponse_era5(debut, fin):
    """Même pluie que la NASA POWER simulée, +5 % ; humidité qui suit la pluie."""
    m = meteo_demo("humide", debut - 1, fin).sous_periode(debut, fin)
    humid = np.clip(0.25 + np.convolve(m.pluie, np.ones(20) / 20, "same") / 20, 0, 0.5)
    return {"latitude": 45.6, "longitude": -73.0, "daily": {
        "time": [str(d) for d in m.dates], "precipitation_sum": list(m.pluie * 1.05),
        "et0_fao_evapotranspiration": [1.6] * len(m.dates),
        "soil_moisture_0_to_100cm_mean": list(humid)}}


SOILGRIDS = {"properties": {"layers": [
    {"name": n, "unit_measure": {"d_factor": 10},
     "depths": [{"label": d, "values": {"mean": v}} for d in sol_mod.PROFONDEURS_SG]}
    for n, v in (("sand", 300), ("clay", 300), ("soc", 200))]}}


def _srtm(params):
    """Plan incliné de 2 % vers l'est."""
    pts = [tuple(map(float, p.split(","))) for p in params["locations"].split("|")]
    lon0 = pts[len(pts) // 2][1]
    m_par_deg = 111320 * np.cos(np.radians(pts[0][0]))
    return {"status": "OK", "results": [
        {"elevation": 50 + 0.02 * (lon - lon0) * m_par_deg, "location": {"lat": la, "lng": lon}}
        for la, lon in pts]}


@pytest.fixture
def api_simulees(monkeypatch):
    appels = []

    def faux_get(url, params, nom, **k):
        appels.append(nom)
        if "power" in url:
            return _reponse_power_depuis_demo(int(params["start"][:4]), int(params["end"][:4]))
        if "opentopodata" in url:
            return _srtm(params)
        if "waterdata.usgs" in url:
            return {"type": "FeatureCollection", "features": [], "links": []}
        if "open-meteo" in url:
            return _reponse_era5(int(params["start_date"][:4]), int(params["end_date"][:4]))
        return SOILGRIDS

    def faux_post(url, corps, nom, **k):
        appels.append(nom)
        assert corps["format"] == "JSON+COLUMNNAME"
        return {}                                   # hors États-Unis : SSURGO vide

    for mod in (meteo_mod, sol_mod, terrain_mod, nappes_mod, era5_mod):
        monkeypatch.setattr(mod, "get_json", faux_get)
    monkeypatch.setattr(sol_mod, "post_json", faux_post)
    monkeypatch.setattr(earthdata_mod, "identifiants", lambda: None)   # pas de compte Earthdata
    return appels


def _resultat(dossier):
    fichiers = list(dossier.glob("resultats_*.json"))
    assert len(fichiers) == 1
    return json.loads(fichiers[0].read_text(encoding="utf-8"))


def test_ligne_de_commande_complete(api_simulees, exemples, tmp_path, capsys):
    main(["evaluer", "--lat", "45.63", "--lon", "-72.96", "--debut", "2015", "--fin", "2024",
          "--rotations", str(exemples / "*.json"), "--sortie", str(tmp_path)])
    sortie = capsys.readouterr().out
    assert "NASA POWER" in sortie and "SoilGrids" in sortie and "SRTM" in sortie
    assert api_simulees == ["NASA POWER", "USDA Soil Data Access", "SoilGrids (ISRIC)",
                            "SRTM (OpenTopoData)", "USGS Water Data", "ERA5 (Open-Meteo)"]
    assert "CONFIANCE" in sortie
    res = _resultat(tmp_path)
    assert len(res["rotations"]) == 6
    assert res["sol"]["groupe_hydro"] == "D"          # 30 % sable / 30 % argile = loam argileux
    assert res["terrain"]["pente"] == pytest.approx(0.02, abs=0.001)
    assert all(0 <= r["note_eau"] <= 1 for r in res["rotations"])
    sources = res["pression"]["sources"]
    assert "MERRA-2" in sources["sol_sec"]           # pas de compte Earthdata -> repli MERRA-2
    assert "aucun puits" in sources["nappes"]
    assert "Earthdata" in sources["esi"]
    assert "stress_mesure" in res["pression"]["composantes"]
    assert "nappes" in res["pression"]["manquantes"]
    assert res["confiance"]["niveau"] in ("bonne", "faible")
    assert res["confiance"]["pluie"]["ecart_pct"] == pytest.approx(100 * (1 / 1.05 - 1), abs=0.5)


def test_sol_manuel_court_circuite_les_bases(api_simulees, exemples, tmp_path):
    main(["evaluer", "--lat", "45.63", "--lon", "-72.96", "--debut", "2020", "--fin", "2024",
          "--sol-manuel", "60,10,2", "--base-seulement",
          "--rotations", str(exemples / "mais_soya.json"), "--sortie", str(tmp_path)])
    assert api_simulees == ["NASA POWER"]


def test_valeurs_a_la_main_l_emportent(api_simulees, exemples, tmp_path):
    main(["evaluer", "--lat", "45.63", "--lon", "-72.96", "--debut", "2015", "--fin", "2024",
          "--sol-manuel", "40,20,3", "--pente", "8", "--nappes-percentile", "10", "--smap", "0.9",
          "--esi", "-1", "--rotations", str(exemples / "mais_soya.json"), "--sortie", str(tmp_path)])
    assert api_simulees == ["NASA POWER", "ERA5 (Open-Meteo)"]   # ERA5 = contrôle de confiance
    res = _resultat(tmp_path)
    assert res["terrain"]["pente"] == pytest.approx(0.08)
    assert res["pression"]["manquantes"] == []
    assert set(res["pression"]["sources"].values()) == {"saisie à la main", "saisi à la main"}


def test_la_pente_change_les_notes(api_simulees, exemples, tmp_path):
    notes = {}
    for pente in ("0.5", "15"):
        d = tmp_path / pente
        main(["evaluer", "--lat", "45.63", "--lon", "-72.96", "--debut", "2015", "--fin", "2024",
              "--sol-manuel", "40,20,3", "--base-seulement", "--pente", pente,
              "--rotations", str(exemples / "mais_soya.json"), "--sortie", str(d)])
        notes[pente] = _resultat(d)["rotations"][0]
    assert notes["15"]["ruissellement_mm_an"] > notes["0.5"]["ruissellement_mm_an"]
    assert notes["15"]["C_pluie_gardee"] < notes["0.5"]["C_pluie_gardee"]


def test_commande_valider(api_simulees, exemples, tmp_path, monkeypatch, capsys):
    def faux_era5(lat, lon, debut, fin, utiliser_cache=True):
        m = meteo_demo("humide", debut - 1, fin).sous_periode(debut, fin)   # même tirage que POWER
        return era5_mod.Era5(m.dates, m.pluie * 1.05, np.full(len(m.dates), 1.6),
                             np.clip(0.25 + np.convolve(m.pluie, np.ones(20) / 20, "same") / 20, 0, 0.5),
                             lat, lon)
    monkeypatch.setattr(era5_mod, "telecharger_era5", faux_era5)
    main(["valider", "--lat", "45.63", "--lon", "-72.96", "--debut", "2015", "--fin", "2024",
          "--rotation", str(exemples / "mais_soya.json"), "--sortie", str(tmp_path)])
    sortie = capsys.readouterr().out
    assert "Pluie" in sortie and "ET0" in sortie and "Humidité" in sortie
    res = json.loads(next(tmp_path.glob("validation_*.json")).read_text(encoding="utf-8"))
    assert res["pluie"]["ecart_pct"] == pytest.approx(100 * (1 / 1.05 - 1), abs=0.5)
    assert res["pluie"]["r_annuel"] == pytest.approx(1.0, abs=1e-3)
    assert res["humidite"]["r_anomalies_seau_era5"] > 0.3


def test_annee_incomplete_refusee():
    with pytest.raises(meteo_mod.ErreurDonnees, match="pas encore complète"):
        meteo_mod.telecharger_power(45.6, -72.9, 2020, 2099)
