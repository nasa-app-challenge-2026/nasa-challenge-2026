"""Niveau 4 — l'algorithme réagit comme le disent les études.

Chaque test vérifie une affirmation de la littérature, sur deux climats synthétiques
(humide ~1000 mm, sec à été sec ~380 mm). Si un test casse après une modification, la
modification a rendu l'algorithme incohérent avec les études.
"""
import json

import pytest

from water_use.demo import meteo_demo, sol_demo
from water_use.et0 import et0_meteo
from water_use.notes import evaluer_rotation, pression_sur_l_eau
from water_use.rotation import lire_rotation


@pytest.fixture(scope="module")
def climats():
    out = {}
    for nom in ("humide", "sec"):
        m = meteo_demo(nom, 2004, 2024)
        out[nom] = (m, et0_meteo(m)[0])
    return out


def _note(rot, climats, nom, irrigue=False):
    m, et0 = climats[nom]
    return evaluer_rotation(rot, m, sol_demo(), 2005, 2024, irrigue, et0)


def _rotation(tmp_path, nom, cultures, duree, travail="semis_direct"):
    f = tmp_path / f"{nom}.json"
    f.write_text(json.dumps(dict(nom=nom, duree_ans=duree, travail_sol=travail,
                                 cultures=cultures)), encoding="utf-8")
    return lire_rotation(f)


MAIS = {"culture": "mais", "annee": 1, "semis": "05-10", "fin": "10-15"}
SOYA = {"culture": "soya", "annee": 2, "semis": "05-20", "fin": "10-01"}
SEIGLE = {"culture": "seigle_couvert", "annee": 1, "semis": "10-20", "fin": "05-05"}


def test_notes_entre_0_et_1(climats, exemples):
    for f in exemples.glob("*.json"):
        for nom in climats:
            e = _note(lire_rotation(f), climats, nom)
            for v in (e.note, e.A, e.B, e.C, e.D):
                assert 0.0 <= v <= 1.0


def test_tout_est_plus_dur_en_climat_sec(climats, exemples):
    for f in exemples.glob("*.json"):
        rot = lire_rotation(f)
        assert _note(rot, climats, "sec").note < _note(rot, climats, "humide").note, rot.nom


def test_sorgho_ble_d_hiver_bat_le_mais_continu_en_climat_sec(climats, exemples):
    """FAO-33 : le sorgho (Ky 0,9) et le blé d'hiver (cycle qui évite l'été) perdent moins
    que le maïs (Ky 1,25) quand l'eau manque."""
    sorgho = _note(lire_rotation(exemples / "sorgho_ble_hiver.json"), climats, "sec")
    mais = _note(lire_rotation(exemples / "mais_continu.json"), climats, "sec")
    assert sorgho.B > mais.B
    assert sorgho.note > mais.note


def test_le_mais_boit_plus_que_le_sorgho(climats, tmp_path):
    m = _rotation(tmp_path, "m", [dict(MAIS)], 1)
    s = _rotation(tmp_path, "s", [{"culture": "sorgho", "annee": 1, "semis": "05-10",
                                   "fin": "10-15"}], 1)
    for nom in climats:
        assert _note(s, climats, nom).A > _note(m, climats, nom).A


def test_couvert_en_climat_sec_assoiffe_la_culture_suivante(climats, tmp_path):
    """Garba et al. 2022 : en zones sèches, -18 % d'eau dans le sol après un couvert."""
    sans = _rotation(tmp_path, "sans", [MAIS, SOYA], 2)
    avec = _rotation(tmp_path, "avec", [MAIS, SEIGLE, SOYA], 2)
    e_sans, e_avec = _note(sans, climats, "sec"), _note(avec, climats, "sec")
    assert e_avec.D < e_sans.D
    assert e_avec.note < e_sans.note
    assert any("700 mm" in a for a in e_avec.alertes)


def test_couvert_en_climat_humide_garde_la_pluie(climats, tmp_path):
    """Basche & DeLonge 2019 : le couvert améliore l'infiltration ; en climat humide la
    pluie d'hiver remplit quand même le seau avant le semis."""
    sans = _rotation(tmp_path, "sans", [MAIS, SOYA], 2)
    avec = _rotation(tmp_path, "avec", [MAIS, SEIGLE, SOYA], 2)
    e_sans, e_avec = _note(sans, climats, "humide"), _note(avec, climats, "humide")
    assert e_avec.C > e_sans.C
    assert e_avec.D == pytest.approx(e_sans.D, abs=0.05)


def test_compromis_du_couvert_depend_du_climat(climats, tmp_path):
    """Le couvert coûte beaucoup plus de points en climat sec qu'en climat humide."""
    sans = _rotation(tmp_path, "sans", [MAIS, SOYA], 2)
    avec = _rotation(tmp_path, "avec", [MAIS, SEIGLE, SOYA], 2)
    ecart = {nom: _note(avec, climats, nom).note - _note(sans, climats, nom).note
             for nom in climats}
    assert ecart["sec"] < ecart["humide"]


def test_residus_reduisent_les_pertes(climats, tmp_path):
    """FAO-56 (paillis) et NRCS (CR) : garder les résidus réduit évaporation et ruissellement."""
    direct = _rotation(tmp_path, "d", [MAIS, SOYA], 2, "semis_direct")
    labour = _rotation(tmp_path, "l", [MAIS, SOYA], 2, "conventionnel")
    for nom in climats:
        assert _note(direct, climats, nom).C > _note(labour, climats, nom).C


def test_irrigation_mesure_la_dependance(climats, exemples):
    mais = lire_rotation(exemples / "mais_continu.json")
    sorgho = lire_rotation(exemples / "sorgho_ble_hiver.json")
    e_m = _note(mais, climats, "sec", irrigue=True)
    e_s = _note(sorgho, climats, "sec", irrigue=True)
    assert e_m.chiffres["irrigation_mm_an"] > e_s.chiffres["irrigation_mm_an"]


def test_pression_plus_forte_en_climat_sec(climats):
    p = {nom: pression_sur_l_eau(m, et0, 2005, 2024) for nom, (m, et0) in climats.items()}
    assert p["sec"]["pression"] > p["humide"]["pression"]
    assert p["sec"]["classe"] == "semi-aride"
    assert p["humide"]["classe"] == "humide"


def test_pression_avec_nappes_qui_baissent(climats):
    m, et0 = climats["humide"]
    base = pression_sur_l_eau(m, et0, 2005, 2024)["pression"]
    nappes_basses = pression_sur_l_eau(m, et0, 2005, 2024, nappes_percentile=5)["pression"]
    assert nappes_basses > base
