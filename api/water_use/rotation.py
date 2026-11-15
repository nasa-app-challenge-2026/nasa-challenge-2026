"""Lecture d'une rotation (fichier JSON) et construction du calendrier jour par jour.

Format d'un fichier rotation :
{
  "nom": "Maïs - Soya avec seigle",
  "duree_ans": 2,
  "travail_sol": "semis_direct",            # facultatif : semis_direct | travail_reduit | conventionnel
  "cultures": [
    {"culture": "mais",  "annee": 1, "semis": "05-10", "fin": "10-15"},
    {"culture": "seigle_couvert", "annee": 1, "semis": "10-20", "fin": "05-01"},
    {"culture": "soya",  "annee": 2, "semis": "05-20", "fin": "10-01"}
  ]
}
- "fin" = récolte (ou destruction du couvert). Si elle tombe avant le semis dans l'année,
  elle est l'année suivante (blé d'hiver, couvert d'hiver).
- "duree_annees" (facultatif, pérennes) : la culture reste N saisons ; "fin" est alors la
  dernière récolte de la dernière année.
- "reprise" (facultatif, cultures d'hiver) : date de reprise de végétation au printemps.

Pour éviter qu'une culture tombe toujours sur les mêmes années de météo, on simule toutes
les « phases » de la rotation (chaque culture commence une fois la première année) et on
fait la moyenne, comme sur une ferme où chaque culture occupe une parcelle chaque année.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .cultures import TRAVAIL_SOL, culture


@dataclass
class Rotation:
    nom: str
    duree_ans: int
    entrees: list
    travail_sol: str = "semis_direct"
    fichier: str = ""

    @property
    def bonne_condition_hydro(self) -> bool:
        """Condition hydrologique « bonne » au sens NRCS (TR-55) : la rotation comprend un
        couvert, une légumineuse serrée ou une plante pérenne (couvert toute l'année plus long,
        herbe ou légumineuse dans la rotation). Choix de l'équipe, à calibrer."""
        for e in self.entrees:
            c = culture(e["culture"])
            if (not c.vente) or c.perenne or c.type_cn in ("legumineuses", "prairie"):
                return True
        return False


def _mmjj(texte: str, champ: str, nom: str) -> tuple:
    try:
        m, j = (int(x) for x in texte.split("-"))
        np.datetime64(f"2001-{m:02d}-{j:02d}")
        return m, j
    except Exception:
        raise ValueError(f"{nom} : « {champ} » doit être au format MM-JJ (reçu « {texte} »)") from None


def lire_rotation(chemin: str | Path) -> Rotation:
    chemin = Path(chemin)
    d = json.loads(chemin.read_text(encoding="utf-8"))
    return rotation_depuis_dict(d, nom_defaut=chemin.stem, fichier=str(chemin))


def rotation_depuis_dict(d: dict, nom_defaut: str = "rotation", fichier: str = "") -> Rotation:
    """Même format et mêmes vérifications qu'un fichier rotation, à partir d'un dict
    (pour brancher l'algorithme sur un pipeline qui a ses chaînes de cultures en mémoire)."""
    nom = d.get("nom", nom_defaut)
    n = int(d.get("duree_ans", 1))
    if n < 1:
        raise ValueError(f"{nom} : duree_ans doit être au moins 1")
    travail = d.get("travail_sol", "semis_direct")
    if travail not in TRAVAIL_SOL:
        raise ValueError(f"{nom} : travail_sol doit être l'un de {list(TRAVAIL_SOL)}")
    entrees = []
    for e in d["cultures"]:
        culture(e["culture"])                       # vérifie que la culture existe
        a = int(e["annee"])
        if not 1 <= a <= n:
            raise ValueError(f"{nom} : {e['culture']} a annee={a}, hors de 1..{n}")
        _mmjj(e["semis"], "semis", nom)
        _mmjj(e["fin"], "fin", nom)
        if "reprise" in e:
            _mmjj(e["reprise"], "reprise", nom)
        entrees.append(dict(e))
    if not entrees:
        raise ValueError(f"{nom} : aucune culture")
    return Rotation(nom, n, entrees, travail, fichier)


@dataclass
class Instance:
    code: str
    vente: bool
    i_semis: int
    i_fin: int            # dernier jour occupé (inclus)
    complete: bool        # semis ET fin dans la période simulée


@dataclass
class Calendrier:
    occupant: np.ndarray          # index dans `instances`, -1 = pas de culture vivante
    kc: np.ndarray
    racines: np.ndarray           # m
    residus: np.ndarray           # part du sol couverte de résidus (jours sans culture vivante)
    instances: list = field(default_factory=list)


def _date(annee: int, mmjj: str):
    m, j = (int(x) for x in mmjj.split("-"))
    if m == 2 and j == 29:
        j = 28
    return np.datetime64(f"{annee:04d}-{m:02d}-{j:02d}")


def _kc_saison(c, n_jours: int, debut_frac=None):
    """Kc et profondeur des racines sur une saison de n_jours (courbe en trapèze FAO-56)."""
    fr = np.array(c.stades if debut_frac is None else debut_frac, dtype=float)
    fr = fr / fr.sum()
    bornes = np.cumsum(fr) * n_jours
    t = np.arange(n_jours) + 0.5
    kc = np.empty(n_jours)
    b1, b2, b3 = bornes[0], bornes[1], bornes[2]
    kc[t <= b1] = c.kc_ini
    dev = (t > b1) & (t <= b2)
    kc[dev] = c.kc_ini + (c.kc_mid - c.kc_ini) * (t[dev] - b1) / max(b2 - b1, 1e-9)
    kc[(t > b2) & (t <= b3)] = c.kc_mid
    fin = t > b3
    kc[fin] = c.kc_mid + (c.kc_end - c.kc_mid) * (t[fin] - b3) / max(n_jours - b3, 1e-9)
    rac = 0.15 + (c.racines_max - 0.15) * np.clip(t / max(b2, 1.0), 0, 1)
    return kc, rac


def construire_calendrier(rot: Rotation, dates: np.ndarray, annee_ref: int, phase: int,
                          tmoy: np.ndarray) -> Calendrier:
    """Calendrier de la rotation sur `dates` ; l'année `annee_ref` est l'année `phase + 1`
    de la rotation."""
    n = len(dates)
    occ = np.full(n, -1, dtype=int)
    kc = np.zeros(n)
    rac = np.zeros(n)
    instances = []
    annees = dates.astype("datetime64[Y]").astype(int) + 1970
    facteur = TRAVAIL_SOL[rot.travail_sol]
    for y in range(int(annees.min()), int(annees.max()) + 1):
        k = ((y - annee_ref) + phase) % rot.duree_ans + 1
        for e in rot.entrees:
            if int(e["annee"]) != k:
                continue
            c = culture(e["culture"])
            d0 = _date(y, e["semis"])
            duree = int(e.get("duree_annees", 1))
            y_fin = y + duree - 1
            d1 = _date(y_fin, e["fin"])
            if d1 <= d0:
                d1 = _date(y_fin + 1, e["fin"])
            i0 = int((d0 - dates[0]).astype(int))
            i1 = int((d1 - dates[0]).astype(int))
            if i1 < 0 or i0 >= n:
                continue
            idx = len(instances)
            lo, hi = max(i0, 0), min(i1, n - 1)
            if (occ[lo:hi + 1] >= 0).any():
                autre = instances[occ[lo:hi + 1][occ[lo:hi + 1] >= 0][0]].code
                raise ValueError(
                    f"{rot.nom} : {c.code} (semé le {d0}) chevauche {autre}. "
                    "Vérifiez les dates de semis et de fin.")
            L = i1 - i0 + 1
            if c.perenne and duree > 1:
                k_s, r_s = _kc_saison(c, min(L, 120))
                k_all = np.full(L, c.kc_mid)
                k_all[:len(k_s)] = k_s
                r_all = np.full(L, c.racines_max)
                r_all[:len(r_s)] = r_s
                # dormance hivernale : hors des 60 premiers jours, Kc_ini quand T moyenne < 5 °C
                for j in range(60, L):
                    ii = i0 + j
                    if 0 <= ii < n and tmoy[ii] < 5.0:
                        k_all[j] = c.kc_ini
            elif c.hiver:
                dr = _date(y + 1, e.get("reprise", c.reprise))
                ir = int((dr - dates[0]).astype(int))
                avant = max(min(ir - i0, L), 0)
                apres = L - avant
                k_all = np.empty(L)
                r_all = np.empty(L)
                k_all[:avant] = c.kc_ini
                r_all[:avant] = np.minimum(0.15 + 0.15 * np.arange(avant) / 60.0, 0.30)
                if apres > 0:
                    st = list(c.stades)
                    k2, r2 = _kc_saison(c, apres, debut_frac=[1e-6] + st[1:])
                    k_all[avant:] = k2
                    r_all[avant:] = np.maximum(0.30, 0.30 + (r2 - 0.15) * (c.racines_max - 0.30)
                                               / max(c.racines_max - 0.15, 1e-9))
            else:
                k_all, r_all = _kc_saison(c, L)
            sl = slice(lo, hi + 1)
            occ[sl] = idx
            kc[sl] = k_all[lo - i0: hi - i0 + 1]
            rac[sl] = r_all[lo - i0: hi - i0 + 1]
            instances.append(Instance(c.code, c.vente, i0, i1, complete=(i0 >= 0 and i1 <= n - 1)))
    # résidus des jours sans culture vivante : ceux de la dernière culture terminée
    residus = np.zeros(n)
    dernier = 0.30                                     # avant la 1re récolte : valeur neutre
    ordre = sorted(range(len(instances)), key=lambda i: instances[i].i_fin)
    fins = {min(instances[i].i_fin, n - 1): culture(instances[i].code).residus * facteur
            for i in ordre}
    for t in range(n):
        residus[t] = dernier
        if t in fins:
            dernier = fins[t]
    return Calendrier(occ, kc, rac, residus, instances)
