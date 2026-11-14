"""Les quatre sous-notes, la note eau et la pression sur l'eau.

Note eau = 0,25 A + 0,25 B + 0,25 C + 0,25 D  (pondération = choix de l'équipe)
  A  Sobriété                : 1 - eau demandée par la rotation / ET0 de l'année
  B  Résistance au manque    : 1 - (0,5 perte moyenne + 0,5 perte d'année sèche)
                               perte = Ky × eau manquante / besoin (FAO-33), ou part des
                               besoins à irriguer si la ferme irrigue ; année sèche = 90e
                               centile des années, sans interpolation : la 2e pire sur 20
                               (la pire sur 10), soit environ 1 an sur 10
  C  Pluie gardée            : 1 - (ruissellement + évaporation du sol nu + eau bue par les
                               couverts) / pluie — même logique que l'« efficacité de stockage
                               de la pluie » des études sur les couverts (Wang et al. 2021)
  D  Eau laissée             : eau dans le sol au semis de chaque culture vendue / taille du seau
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .bilan import erreur_bilan, simuler
from .cultures import culture
from .et0 import et0_meteo
from .rotation import construire_calendrier

POIDS_NOTE = dict(A=0.25, B=0.25, C=0.25, D=0.25)
POIDS_PRESSION = dict(aridite=0.4, pluie_ete=0.2, nappes=0.2, stress_mesure=0.2)
CENTILE_ANNEE_SECHE = 0.90


def _borne(x):
    return float(min(max(x, 0.0), 1.0))


def secheresse_depuis_percentile(p: float) -> float:
    """Percentile (0-100, 50 = normal) -> sécheresse 0-1 : 0 au-dessus de la médiane,
    1 au 10e percentile et en dessous. Sert aux nappes et à l'humidité du sol."""
    return _borne((50.0 - p) / 40.0)


@dataclass
class Evaluation:
    rotation: str
    note: float
    A: float
    B: float
    C: float
    D: float
    chiffres: dict = field(default_factory=dict)
    alertes: list = field(default_factory=list)

    def ligne(self) -> dict:
        return dict(rotation=self.rotation, note_eau=round(self.note, 3),
                    A_sobriete=round(self.A, 3), B_resistance=round(self.B, 3),
                    C_pluie_gardee=round(self.C, 3), D_eau_laissee=round(self.D, 3),
                    **{k: (round(v, 1) if isinstance(v, float) else v)
                       for k, v in self.chiffres.items()})


def evaluer_rotation(rot, meteo, sol, debut: int, fin: int, irrigue: bool = False,
                     et0=None) -> Evaluation:
    """Simule toutes les phases de la rotation sur la météo (qui commence un an avant
    `debut` pour remplir le seau) et calcule les notes sur les années debut..fin."""
    if et0 is None:
        et0, _ = et0_meteo(meteo)
    annees = meteo.annees
    dans = (annees >= debut) & (annees <= fin)
    tmoy = (meteo.tmax + meteo.tmin) / 2
    A_vals, C_vals, D_vals = [], [], []
    pertes_par_annee = {y: [] for y in range(debut, fin + 1)}
    cumuls = dict(demande=0.0, manque=0.0, irrigation=0.0, ruiss=0.0, evap=0.0, couverts=0.0,
                  pluie=0.0,
                  eau_semis=0.0, n_semis=0)
    pire_bilan = 0.0
    for phase in range(rot.duree_ans):
        cal = construire_calendrier(rot, meteo.dates, debut, phase, tmoy)
        r = simuler(meteo, et0, sol, cal, rot.bonne_condition_hydro, irrigue)
        pire_bilan = max(pire_bilan, abs(erreur_bilan(r)))
        couvert = np.array([o >= 0 and not cal.instances[o].vente for o in cal.occupant])
        eau_couverts = np.where(couvert, r.eta, 0.0)
        for y in range(debut, fin + 1):
            m = annees == y
            et0_y, p_y = et0[m].sum(), r.pluie[m].sum()
            A_vals.append(1 - r.etc_pot[m].sum() / et0_y if et0_y > 0 else 1.0)
            if p_y > 0:
                C_vals.append(1 - (r.ruiss[m].sum() + r.evap_sol[m].sum()
                                   + eau_couverts[m].sum()) / p_y)
        cumuls["demande"] += r.etc_pot[dans].sum()
        cumuls["manque"] += r.manque[dans].sum()
        cumuls["irrigation"] += r.irrigation[dans].sum()
        cumuls["ruiss"] += r.ruiss[dans].sum()
        cumuls["evap"] += r.evap_sol[dans].sum()
        cumuls["couverts"] += eau_couverts[dans].sum()
        cumuls["pluie"] += r.pluie[dans].sum()
        for inst in cal.instances:
            if not inst.vente:
                continue
            c = culture(inst.code)
            if 0 <= inst.i_semis < len(annees) and debut <= annees[inst.i_semis] <= fin:
                s = r.stock_haut[inst.i_semis - 1] + r.stock_bas[inst.i_semis - 1] \
                    if inst.i_semis > 0 else sol.taw_total
                D_vals.append(s / sol.taw_total)
                cumuls["eau_semis"] += s
                cumuls["n_semis"] += 1
            if not inst.complete:
                continue
            y_rec = int(annees[inst.i_fin])
            if not debut <= y_rec <= fin:
                continue
            sl = slice(inst.i_semis, inst.i_fin + 1)
            besoin = r.etc_pot[sl].sum()
            if besoin <= 0:
                continue
            if irrigue:
                perte = r.irrigation[sl].sum() / besoin
            else:
                perte = (c.ky or 1.0) * r.manque[sl].sum() / besoin
            pertes_par_annee[y_rec].append(min(perte, 1.0))
    serie = np.array([np.mean(v) for v in pertes_par_annee.values() if v])
    nb_annees = (fin - debut + 1) * rot.duree_ans
    alertes = []
    if len(serie) == 0:
        B = 1.0
        alertes.append("Aucune culture vendue récoltée dans la période : B vaut 1 par défaut.")
        perte_moy = perte_seche = 0.0
    else:
        perte_moy = float(serie.mean())
        perte_seche = float(np.quantile(serie, CENTILE_ANNEE_SECHE, method="higher"))
        B = 1 - (0.5 * perte_moy + 0.5 * perte_seche)
    A, B, C = _borne(np.mean(A_vals)), _borne(B), _borne(np.mean(C_vals) if C_vals else 1.0)
    D = _borne(np.mean(D_vals)) if D_vals else 1.0
    note = POIDS_NOTE["A"] * A + POIDS_NOTE["B"] * B + POIDS_NOTE["C"] * C + POIDS_NOTE["D"] * D
    pluie_an = cumuls["pluie"] / nb_annees
    if pluie_an < 700 and any(not culture(e["culture"]).vente for e in rot.entrees):
        alertes.append("Pluie annuelle sous ~700 mm avec un couvert : en zone sèche, les couverts "
                       "réduisent souvent l'eau et le rendement suivants (Garba et al. 2022). "
                       "À vérifier avec un agronome.")
    if pire_bilan > 0.5:
        alertes.append(f"Bilan d'eau mal fermé ({pire_bilan:.2f} mm) : signalez-le.")
    chiffres = dict(
        demande_mm_an=cumuls["demande"] / nb_annees,
        manque_mm_an=cumuls["manque"] / nb_annees,
        irrigation_mm_an=cumuls["irrigation"] / nb_annees,
        ruissellement_mm_an=cumuls["ruiss"] / nb_annees,
        evaporation_sol_nu_mm_an=cumuls["evap"] / nb_annees,
        eau_bue_par_couverts_mm_an=cumuls["couverts"] / nb_annees,
        pluie_mm_an=pluie_an,
        pluie_gardee_pct=100 * C,
        eau_au_semis_mm=(cumuls["eau_semis"] / cumuls["n_semis"]) if cumuls["n_semis"] else float("nan"),
        perte_rendement_moy_pct=100 * perte_moy,
        perte_rendement_annee_seche_pct=100 * perte_seche,
    )
    return Evaluation(rot.nom, note, A, B, C, D, chiffres, alertes)


def pression_sur_l_eau(meteo, et0, debut: int, fin: int, nappes_percentile=None, esi=None,
                       secheresse_sol=None) -> dict:
    """Pression sur l'eau de la ferme (0 = l'eau ne manque pas, 1 = très sèche).
    nappes_percentile : niveau récent des nappes en percentile (puits USGS, ou GRACE à la main) ;
    esi : anomalie standardisée de l'ESI (ECOSTRESS), négatif = stress ;
    secheresse_sol : 0-1 (SMAP, sinon MERRA-2 ; voir humidite.py).
    Les composantes absentes sont retirées et les poids restants renormalisés."""
    annees = meteo.annees
    m = (annees >= debut) & (annees <= fin)
    ia = meteo.pluie[m].sum() / max(et0[m].sum(), 1e-9)          # indice d'aridité P/ET0
    comp = {"aridite": _borne((1.0 - ia) / 0.8)}
    mois = meteo.mois
    ete = (mois >= 6) & (mois <= 8) if meteo.lat >= 0 else ((mois == 12) | (mois <= 2))
    par_an = np.array([meteo.pluie[(annees == y) & ete].sum() for y in range(debut, fin + 1)])
    detail = dict(indice_aridite=round(float(ia), 3), classe=_classe_aridite(ia))
    if len(par_an) >= 6:
        moitie = len(par_an) // 2
        avant, apres = par_an[:moitie].mean(), par_an[moitie:].mean()
        delta = 100 * (apres / avant - 1) if avant > 0 else 0.0
        comp["pluie_ete"] = _borne(-delta / 20.0)
        detail["variation_pluie_ete_pct"] = round(float(delta), 1)
    if nappes_percentile is not None:
        comp["nappes"] = secheresse_depuis_percentile(nappes_percentile)
    stress = []
    if esi is not None:
        stress.append(_borne(-esi / 2.0))
    if secheresse_sol is not None:
        stress.append(_borne(secheresse_sol))
    if stress:
        comp["stress_mesure"] = float(np.mean(stress))
    total = sum(POIDS_PRESSION[k] for k in comp)
    valeur = sum(POIDS_PRESSION[k] * v for k, v in comp.items()) / total
    manquantes = [k for k in POIDS_PRESSION if k not in comp]
    return dict(pression=round(valeur, 3), composantes={k: round(v, 3) for k, v in comp.items()},
                manquantes=manquantes, **detail)


def _classe_aridite(ia: float) -> str:
    if ia < 0.03:
        return "hyper-aride"
    if ia < 0.2:
        return "aride"
    if ia < 0.5:
        return "semi-aride"
    if ia < 0.65:
        return "subhumide sec"
    return "humide"
