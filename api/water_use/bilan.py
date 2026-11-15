"""Le « seau » : bilan d'eau du sol jour par jour (FAO-56 chapitres 7 et 8, simplifié).

Étages : haut (0-30 cm, toutes les cultures) et bas (30-150 cm, racines profondes).
Chaque jour :
  1. neige : sous 0 °C la pluie s'accumule en neige ; elle fond à 3 mm par °C au-dessus de
     0 °C (facteur degré-jour typique, à calibrer) ;
  2. ruissellement (curve number NRCS selon ce qui couvre le sol) ;
  3. le reste remplit l'étage haut, le trop-plein descend dans l'étage bas, puis draine
     (recharge de nappe, non compté comme perdu) ;
  4. culture présente : soif = Kc × ET0 ; elle boit dans les étages que ses racines atteignent ;
     sous le seuil « eau facile » (p) elle boit moins (coefficient Ks) -> eau manquante ;
     ferme irriguée : on remplit la zone des racines dès que le seuil est franchi ;
  5. sol sans culture vivante : évaporation de la surface (environ la moitié de l'étage haut),
     réduite de 5 % par tranche de 10 % de résidus (FAO-56 ch. 10), nulle sous la neige.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .cultures import culture
from .ruissellement import curve_number, etat_cn, ruissellement

FONTE_MM_PAR_DEGRE = 3.0
NEIGE_COUVRANTE_MM = 5.0
KC_SOL_NU = 1.0


@dataclass
class Resultat:
    pluie: np.ndarray
    etc_pot: np.ndarray
    eta: np.ndarray
    manque: np.ndarray
    irrigation: np.ndarray
    ruiss: np.ndarray
    evap_sol: np.ndarray
    drainage: np.ndarray
    stock_haut: np.ndarray       # fin de journée
    stock_bas: np.ndarray
    neige: np.ndarray
    stock_initial: float


def simuler(meteo, et0: np.ndarray, sol, cal, bonne_condition: bool, irrigue: bool = False,
            stock_initial: float = 1.0) -> Resultat:
    n = len(et0)
    sortie = {k: np.zeros(n) for k in ("etc_pot", "eta", "manque", "irrigation", "ruiss",
                                       "evap_sol", "drainage", "stock_haut", "stock_bas", "neige")}
    taw_h, taw_b = max(sol.taw_haut, 1e-6), max(sol.taw_bas, 1e-6)
    s_h, s_b = taw_h * stock_initial, taw_b * stock_initial
    neige = 0.0
    tmoy = (meteo.tmax + meteo.tmin) / 2
    tew = 0.5 * taw_h                                      # eau évaporable de la surface
    cultures_inst = [culture(i.code) for i in cal.instances]
    cache_cn = {}
    for t in range(n):
        P, T = float(meteo.pluie[t]), float(tmoy[t])
        # 1. neige
        if T <= 0.0:
            neige += P
            liquide = 0.0
        else:
            liquide = P
        fonte = min(neige, FONTE_MM_PAR_DEGRE * T) if T > 0.0 else 0.0
        neige -= fonte
        w = liquide + fonte
        # 2. ruissellement
        o = cal.occupant[t]
        c = cultures_inst[o] if o >= 0 else None
        etat = etat_cn(c.type_cn if c else None, float(cal.residus[t]), bonne_condition)
        cle = (etat, sol.groupe_hydro)
        if cle not in cache_cn:
            cache_cn[cle] = curve_number(etat, sol.groupe_hydro, getattr(sol, "pente", None))
        q = ruissellement(w, cache_cn[cle])
        infil = w - q
        # 3. remplissage
        s_h += infil
        trop = max(s_h - taw_h, 0.0)
        s_h -= trop
        s_b += trop
        drain = max(s_b - taw_b, 0.0)
        s_b -= drain
        # 4-5. évapotranspiration
        etc = eta = manque = irr = evap = 0.0
        sous_neige = neige > NEIGE_COUVRANTE_MM
        if c is not None:
            etc = 0.0 if sous_neige else float(cal.kc[t]) * float(et0[t])
            zr = float(cal.racines[t])
            f_h = min(1.0, zr / 0.30)
            f_b = min(max((zr - 0.30) / 1.20, 0.0), 1.0)
            taw = taw_h * f_h + taw_b * f_b
            acc = s_h * f_h + s_b * f_b
            p = min(max(c.p + 0.04 * (5.0 - etc), 0.1), 0.8)     # FAO-56 tableau 22, note
            dr = taw - acc
            raw = p * taw
            if irrigue and c.vente and dr > raw:
                avant = s_h + s_b
                s_h += (taw_h - s_h) * f_h
                s_b += (taw_b - s_b) * f_b
                irr = (s_h + s_b) - avant
                acc = s_h * f_h + s_b * f_b
                dr = taw - acc
            ks = 1.0 if dr <= raw else max((taw - dr) / max((1 - p) * taw, 1e-9), 0.0)
            eta = min(ks * etc, acc)
            if eta > 0:
                w_h, w_b = s_h * f_h, s_b * f_b
                s_h -= eta * w_h / (w_h + w_b)
                s_b -= eta * w_b / (w_h + w_b)
            manque = etc - eta
        elif not sous_neige:
            kr = min(max((s_h - (taw_h - tew)) / tew, 0.0), 1.0)
            evap = KC_SOL_NU * float(et0[t]) * (1.0 - 0.5 * float(cal.residus[t])) * kr
            evap = min(evap, s_h)
            s_h -= evap
        s_h, s_b = max(s_h, 0.0), max(s_b, 0.0)
        for k, v in (("etc_pot", etc), ("eta", eta), ("manque", manque), ("irrigation", irr),
                     ("ruiss", q), ("evap_sol", evap), ("drainage", drain), ("stock_haut", s_h),
                     ("stock_bas", s_b), ("neige", neige)):
            sortie[k][t] = v
    return Resultat(pluie=meteo.pluie.copy(), stock_initial=(taw_h + taw_b) * stock_initial,
                    **sortie)


def erreur_bilan(r: Resultat) -> float:
    """Pluie + irrigation - (ruissellement + ETa + évaporation + drainage + variation de
    stock + neige restante). Doit valoir ~0 : l'eau ne se crée ni ne se perd."""
    entrees = r.pluie.sum() + r.irrigation.sum()
    sorties = r.ruiss.sum() + r.eta.sum() + r.evap_sol.sum() + r.drainage.sum()
    variation = (r.stock_haut[-1] + r.stock_bas[-1]) - r.stock_initial + r.neige[-1]
    return float(entrees - sorties - variation)
