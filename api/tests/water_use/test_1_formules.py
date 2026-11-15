"""Niveau 1 — chaque formule redonne les chiffres publiés dans sa source."""
import numpy as np
import pytest

from water_use.et0 import et0_hargreaves, et0_penman_monteith, rayonnement_extraterrestre
from water_use.ruissellement import ajuster_pente, curve_number, etat_cn, ruissellement
from water_use.sol import classe_texture, groupe_depuis_texture, saxton_rawls
from water_use.terrain import grille, pente_plan


def test_et0_exemple_18_fao56():
    """FAO-56, exemple 18 (Bruxelles, 6 juillet) : ET0 = 3,9 mm/jour."""
    et0 = et0_penman_monteith(tmax=21.5, tmin=12.3, rs=22.07, u2=2.078, lat=50.8,
                              altitude=100, jour_annee=187, ea=1.409)
    assert float(et0) == pytest.approx(3.9, abs=0.05)


def test_rayonnement_extraterrestre_exemple_fao56():
    """FAO-56 : Ra = 41,09 MJ/m²/jour à 50°48' N le 6 juillet (exemple 18)."""
    assert float(rayonnement_extraterrestre(50.8, 187)) == pytest.approx(41.09, abs=0.1)


def test_hargreaves_meme_ordre_de_grandeur():
    pm = float(et0_penman_monteith(21.5, 12.3, 22.07, 2.078, 50.8, 100, 187, ea=1.409))
    hg = float(et0_hargreaves(21.5, 12.3, 50.8, 187))
    assert abs(hg - pm) / pm < 0.25


def test_et0_nulle_ou_positive_l_hiver():
    et0 = et0_penman_monteith(np.array([-5.0]), np.array([-15.0]), np.array([4.0]),
                              np.array([3.0]), 46.0, 50, 15, rh_moy=np.array([80.0]))
    assert et0[0] >= 0


def test_curve_numbers_tableau_nrcs():
    """TR-55 tableau 2-2b, groupe B."""
    assert curve_number("sol_nu", "B") == 86
    assert curve_number("rangs_residus_bon", "B") == 75
    assert curve_number("cereales_bon", "D") == 87
    assert curve_number("prairie", "A") == 30


def test_ruissellement_formule_scs():
    # CN 75, pluie 50 mm : S = 84,67 ; Ia = 16,93 ; Q = 33,07² / 117,73 = 9,29 mm
    assert ruissellement(50, 75) == pytest.approx(9.29, abs=0.02)
    assert ruissellement(10, 75) == 0.0            # sous l'abstraction initiale
    assert ruissellement(50, 86) > ruissellement(50, 75)   # sol nu ruisselle plus


def test_choix_de_la_ligne_cn():
    assert etat_cn(None, 0.0, False) == "sol_nu"
    assert etat_cn(None, 0.5, False) == "jachere_residus_bon"
    assert etat_cn("rangs", 0.3, True) == "rangs_residus_bon"
    assert etat_cn("legumineuses", 0.0, False) == "legumineuses_mediocre"


def test_saxton_rawls_loam():
    """Loam 40 % sable / 20 % argile / 2,5 % MO : capacité au champ ≈ 0,28,
    flétrissement ≈ 0,14, eau utile ≈ 0,14 m³/m³ (ordre de grandeur de Saxton & Rawls 2006)."""
    r = saxton_rawls(40, 20, 2.5)
    assert r["cc"] == pytest.approx(0.28, abs=0.02)
    assert r["pf"] == pytest.approx(0.14, abs=0.02)
    assert 0.12 < r["eau_utile"] < 0.17


def test_sable_garde_moins_d_eau_que_loam():
    assert saxton_rawls(90, 5, 1)["eau_utile"] < saxton_rawls(40, 20, 2.5)["eau_utile"]


def test_matiere_organique_effet_petit():
    """Minasny & McBratney 2018 : +1 % de carbone ≈ +1 à 2 mm d'eau utile par 100 mm de sol."""
    gain = (saxton_rawls(40, 20, 2.5 + 1.724)["eau_utile"]
            - saxton_rawls(40, 20, 2.5)["eau_utile"]) * 100
    assert 0 < gain < 3


@pytest.mark.parametrize("sable,argile,attendu", [
    (92, 3, "sable"), (40, 20, "loam"), (20, 15, "loam limoneux"), (30, 45, "argile"),
    (60, 25, "loam sablo-argileux"), (30, 32, "loam argileux")])
def test_classes_de_texture_usda(sable, argile, attendu):
    assert classe_texture(sable, argile) == attendu


def test_groupe_hydro_depuis_texture():
    assert groupe_depuis_texture(92, 3) == "A"
    assert groupe_depuis_texture(30, 45) == "D"


def test_pente_cn_inchange_a_5_pourcent():
    """Williams (1995) / SWAT éq. 2:1.1.4 : les tableaux NRCS valent pour ~5 % de pente."""
    assert ajuster_pente(75, 0.05) == pytest.approx(75, abs=0.01)
    assert ajuster_pente(75, None) == 75
    assert curve_number("rangs_residus_bon", "B", 0.05) == pytest.approx(75, abs=0.01)


def test_pente_cn_plat_et_fort():
    # CN3 = 75 · exp(0,00673 · 25) = 88,7 ; à pente nulle : 75 − (88,7 − 75) / 3 = 70,4
    assert ajuster_pente(75, 0.0) == pytest.approx(70.4, abs=0.1)
    assert ajuster_pente(75, 0.15) > 75
    assert ajuster_pente(75, 0.01) < ajuster_pente(75, 0.03) < ajuster_pente(75, 0.10)


def test_pente_d_un_plan():
    pts, dec = grille(45.0, -73.0)
    z = [100 + 0.03 * e - 0.04 * n for e, n in dec]          # 3 % vers l'est, 4 % vers le nord
    pente, bruit = pente_plan(dec, z)
    assert pente == pytest.approx(0.05, abs=1e-9) and bruit < 1e-9
    assert len(pts) == 25
