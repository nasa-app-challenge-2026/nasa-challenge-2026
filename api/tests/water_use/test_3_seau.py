"""Niveau 3 — le seau ne crée ni ne perd d'eau, et reste entre vide et plein."""
import numpy as np
import pytest

from water_use.bilan import erreur_bilan, simuler
from water_use.demo import meteo_demo, sol_demo
from water_use.et0 import et0_meteo
from water_use.rotation import construire_calendrier, lire_rotation


@pytest.fixture(scope="module", params=["humide", "sec"])
def climat(request):
    m = meteo_demo(request.param, 2004, 2012)
    return m, et0_meteo(m)[0]


@pytest.mark.parametrize("irrigue", [False, True])
def test_bilan_ferme_pour_toutes_les_rotations(climat, exemples, irrigue):
    meteo, et0 = climat
    sol = sol_demo()
    tmoy = (meteo.tmax + meteo.tmin) / 2
    for f in sorted(exemples.glob("*.json")):
        rot = lire_rotation(f)
        for phase in range(rot.duree_ans):
            cal = construire_calendrier(rot, meteo.dates, 2005, phase, tmoy)
            r = simuler(meteo, et0, sol, cal, rot.bonne_condition_hydro, irrigue)
            assert abs(erreur_bilan(r)) < 1e-6, f"{rot.nom}, phase {phase}"
            assert (r.stock_haut >= -1e-9).all() and (r.stock_haut <= sol.taw_haut + 1e-6).all()
            assert (r.stock_bas >= -1e-9).all() and (r.stock_bas <= sol.taw_bas + 1e-6).all()
            assert (r.eta <= r.etc_pot + 1e-9).all()


def test_irrigation_supprime_le_manque(climat, exemples):
    meteo, et0 = climat
    rot = lire_rotation(exemples / "mais_continu.json")
    cal = construire_calendrier(rot, meteo.dates, 2005, 0, (meteo.tmax + meteo.tmin) / 2)
    sec = simuler(meteo, et0, sol_demo(), cal, False, irrigue=False)
    irr = simuler(meteo, et0, sol_demo(), cal, False, irrigue=True)
    assert irr.manque.sum() <= sec.manque.sum()
    if sec.manque.sum() > 50:
        assert irr.irrigation.sum() > 0


def test_calendrier_detecte_un_chevauchement(tmp_path):
    f = tmp_path / "mauvaise.json"
    f.write_text('{"nom":"x","duree_ans":1,"cultures":['
                 '{"culture":"mais","annee":1,"semis":"05-10","fin":"10-15"},'
                 '{"culture":"soya","annee":1,"semis":"09-01","fin":"10-30"}]}', encoding="utf-8")
    rot = lire_rotation(f)
    m = meteo_demo("humide", 2004, 2006)
    with pytest.raises(ValueError, match="chevauche"):
        construire_calendrier(rot, m.dates, 2005, 0, (m.tmax + m.tmin) / 2)


def test_rotation_invalide(tmp_path):
    f = tmp_path / "x.json"
    f.write_text('{"duree_ans":1,"cultures":[{"culture":"banane","annee":1,"semis":"05-01","fin":"09-01"}]}',
                 encoding="utf-8")
    with pytest.raises(ValueError, match="Culture inconnue"):
        lire_rotation(f)


def test_kc_suit_la_courbe_fao(exemples):
    m = meteo_demo("humide", 2004, 2006)
    rot = lire_rotation(exemples / "mais_continu.json")
    cal = construire_calendrier(rot, m.dates, 2005, 0, (m.tmax + m.tmin) / 2)
    kc_mais = cal.kc[cal.occupant >= 0]
    assert kc_mais.min() == pytest.approx(0.30, abs=0.01)
    assert kc_mais.max() == pytest.approx(1.20, abs=0.01)
    assert np.all(cal.racines[cal.occupant >= 0] <= 1.0 + 1e-9)
