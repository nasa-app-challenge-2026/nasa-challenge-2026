"""Fiche eau de chaque culture.

Chaque valeur porte sa provenance dans `SOURCES` :
  - "verifie"   : relu dans la source citée pendant la préparation de ce code ;
  - "a_verifier": valeur standard de la même source, reprise de mémoire, à contrôler
                  dans FAO-56 (tableaux 11, 12 et 22) avant usage sérieux ;
  - "estime"    : choix de l'équipe faute de valeur publiée (à calibrer).

Signification des champs
  kc_ini, kc_mid, kc_end : coefficient cultural FAO-56 (soif de la culture / soif du gazon de
                           référence) au début, au pic et à la fin de la saison.
  stades                 : part de la saison (semis -> récolte) occupée par les stades
                           initial, développement, mi-saison, fin (somme = 1).
  racines_max            : profondeur maximale des racines (m).
  p                      : part de la réserve d'eau que la plante vide sans stress (FAO-56).
  ky                     : sensibilité du rendement au manque d'eau (FAO-33) ; None = pas de
                           rendement vendu (couvert).
  type_cn                : famille NRCS pour le ruissellement : rangs, cereales, legumineuses,
                           prairie.
  residus                : part du sol couverte de résidus après récolte, en semis direct.
  vente                  : True = culture vendue (compte dans la sous-note B et D).
  hiver                  : culture semée l'automne ; elle dort jusqu'à `reprise` (MM-JJ).
  perenne                : culture pluriannuelle (luzerne, prairie).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Culture:
    code: str
    nom: str
    kc_ini: float
    kc_mid: float
    kc_end: float
    stades: tuple
    racines_max: float
    p: float
    ky: float | None
    type_cn: str
    residus: float
    vente: bool = True
    hiver: bool = False
    reprise: str = "04-01"
    perenne: bool = False
    sources: dict = field(default_factory=dict)


def _c(**k):
    return Culture(**k)


CULTURES = {c.code: c for c in [
    _c(code="mais", nom="Maïs grain", kc_ini=0.30, kc_mid=1.20, kc_end=0.35,
       stades=(0.18, 0.29, 0.32, 0.21), racines_max=1.0, p=0.55, ky=1.25,
       type_cn="rangs", residus=0.80,
       sources=dict(kc_mid="verifie (fiche FAO maïs : 1,05-1,2)", ky="verifie (FAO-33)",
                    racines_max="verifie (fiche FAO maïs)", p="verifie (fiche FAO maïs : 0,55)",
                    kc_ini="a_verifier (FAO-56 t.12)", kc_end="a_verifier (FAO-56 t.12)",
                    stades="a_verifier (FAO-56 t.11)", residus="estime")),
    _c(code="sorgho", nom="Sorgho grain", kc_ini=0.30, kc_mid=1.05, kc_end=0.55,
       stades=(0.16, 0.28, 0.32, 0.24), racines_max=1.4, p=0.55, ky=0.9,
       type_cn="rangs", residus=0.70,
       sources=dict(kc_mid="verifie (fiche FAO sorgho : 1,0-1,15)", ky="verifie (FAO-33)",
                    racines_max="verifie (fiche FAO sorgho)", p="verifie (fiche FAO : 0,55)",
                    kc_end="verifie (fiche FAO : 0,55)", stades="verifie (fiche FAO : 20/35/40/30 j)",
                    kc_ini="a_verifier", residus="estime")),
    _c(code="ble_hiver", nom="Blé d'hiver", kc_ini=0.40, kc_mid=1.15, kc_end=0.25,
       stades=(0.0, 0.30, 0.45, 0.25), racines_max=1.4, p=0.55, ky=1.05,
       type_cn="cereales", residus=0.80, hiver=True, reprise="04-01",
       sources=dict(kc_mid="verifie (fiche FAO blé : 1,15)", ky="verifie (FAO-33 : 1,05)",
                    racines_max="verifie (fiche FAO blé d'hiver : 1,4)", p="verifie (0,55)",
                    kc_ini="a_verifier", kc_end="a_verifier", stades="estime (après la reprise)",
                    reprise="estime (1er avril, à ajuster au climat)", residus="estime")),
    _c(code="ble_printemps", nom="Blé de printemps", kc_ini=0.30, kc_mid=1.15, kc_end=0.25,
       stades=(0.13, 0.21, 0.41, 0.25), racines_max=1.2, p=0.55, ky=1.15,
       type_cn="cereales", residus=0.80,
       sources=dict(kc_mid="verifie (1,15)", ky="verifie (FAO-33 : 1,15)",
                    racines_max="verifie (1,2)", p="verifie (0,55)", kc_ini="verifie (0,3)",
                    kc_end="a_verifier", stades="a_verifier", residus="estime")),
    _c(code="orge", nom="Orge", kc_ini=0.30, kc_mid=1.15, kc_end=0.25,
       stades=(0.13, 0.21, 0.41, 0.25), racines_max=1.2, p=0.55, ky=1.0,
       type_cn="cereales", residus=0.70,
       sources=dict(kc_mid="a_verifier (FAO-56 t.12)", ky="estime (non tabulé dans FAO-33, valeur neutre)",
                    racines_max="a_verifier (FAO-56 t.22 : 1,0-1,5)", p="a_verifier",
                    stades="a_verifier", residus="estime")),
    _c(code="avoine", nom="Avoine", kc_ini=0.30, kc_mid=1.15, kc_end=0.25,
       stades=(0.13, 0.21, 0.41, 0.25), racines_max=1.2, p=0.55, ky=1.0,
       type_cn="cereales", residus=0.70,
       sources=dict(kc_mid="a_verifier (FAO-56 t.12)", ky="estime (non tabulé, valeur neutre)",
                    racines_max="a_verifier", p="a_verifier", stades="a_verifier", residus="estime")),
    _c(code="soya", nom="Soya", kc_ini=0.40, kc_mid=1.15, kc_end=0.50,
       stades=(0.15, 0.22, 0.44, 0.19), racines_max=1.0, p=0.50, ky=0.85,
       type_cn="rangs", residus=0.40,
       sources=dict(kc_mid="verifie (fiche FAO soya : 1,0-1,15)", ky="verifie (FAO-33 : 0,85)",
                    kc_ini="verifie (0,3-0,4)", kc_end="verifie (0,4-0,5)",
                    p="verifie (fiche FAO : 0,55, pris 0,50 par prudence)",
                    racines_max="a_verifier (FAO-56 t.22 : 0,6-1,3)", stades="a_verifier",
                    residus="estime")),
    _c(code="tournesol", nom="Tournesol", kc_ini=0.35, kc_mid=1.05, kc_end=0.35,
       stades=(0.19, 0.27, 0.35, 0.19), racines_max=1.2, p=0.45, ky=0.95,
       type_cn="rangs", residus=0.30,
       sources=dict(ky="verifie (FAO-33 : 0,95)", kc_mid="a_verifier", racines_max="a_verifier",
                    p="a_verifier", stades="a_verifier", residus="estime")),
    _c(code="canola", nom="Canola", kc_ini=0.35, kc_mid=1.05, kc_end=0.35,
       stades=(0.17, 0.25, 0.38, 0.20), racines_max=1.2, p=0.60, ky=1.0,
       type_cn="cereales", residus=0.50,
       sources=dict(kc_mid="a_verifier", ky="estime (non tabulé, valeur neutre)",
                    racines_max="a_verifier", p="a_verifier", stades="a_verifier", residus="estime")),
    _c(code="pois", nom="Pois sec", kc_ini=0.40, kc_mid=1.15, kc_end=0.35,
       stades=(0.20, 0.30, 0.35, 0.15), racines_max=0.8, p=0.35, ky=1.15,
       type_cn="cereales", residus=0.30,
       sources=dict(ky="verifie (FAO-33 : 1,15)", kc_mid="a_verifier", racines_max="a_verifier",
                    p="a_verifier", stades="a_verifier", residus="estime")),
    _c(code="haricot", nom="Haricot sec", kc_ini=0.40, kc_mid=1.15, kc_end=0.35,
       stades=(0.18, 0.27, 0.37, 0.18), racines_max=0.8, p=0.45, ky=1.15,
       type_cn="rangs", residus=0.20,
       sources=dict(ky="verifie (FAO-33 : 1,15)", kc_mid="a_verifier", racines_max="a_verifier",
                    p="a_verifier", stades="a_verifier", residus="estime")),
    _c(code="sarrasin", nom="Sarrasin", kc_ini=0.35, kc_mid=1.00, kc_end=0.35,
       stades=(0.20, 0.30, 0.30, 0.20), racines_max=0.8, p=0.50, ky=1.0,
       type_cn="cereales", residus=0.30,
       sources=dict(tout="estime (pas de fiche FAO ; valeurs génériques de petite culture)")),
    _c(code="luzerne", nom="Luzerne (foin)", kc_ini=0.40, kc_mid=0.95, kc_end=0.90,
       stades=(0.10, 0.20, 0.60, 0.10), racines_max=1.5, p=0.55, ky=1.1,
       type_cn="legumineuses", residus=0.50, perenne=True,
       sources=dict(ky="verifie (FAO-33 : 1,1)", kc_mid="a_verifier (FAO-56 t.12, moyenne des coupes)",
                    racines_max="a_verifier (FAO-56 t.22 : 1,0-2,0, plafonné à 1,5 m)",
                    p="a_verifier", residus="estime")),
    _c(code="prairie", nom="Prairie de fauche", kc_ini=0.40, kc_mid=0.90, kc_end=0.85,
       stades=(0.10, 0.20, 0.60, 0.10), racines_max=1.0, p=0.60, ky=1.0,
       type_cn="prairie", residus=0.60, perenne=True,
       sources=dict(tout="a_verifier (FAO-56 t.12, prairie de fauche) ; ky estime")),
    _c(code="seigle_couvert", nom="Seigle (couvert)", kc_ini=0.40, kc_mid=1.00, kc_end=1.00,
       stades=(0.0, 0.50, 0.50, 0.0), racines_max=1.0, p=0.55, ky=None,
       type_cn="cereales", residus=0.90, vente=False, hiver=True, reprise="04-01",
       sources=dict(tout="estime (céréale d'hiver détruite verte : pas de stade de fin)")),
    _c(code="trefle_couvert", nom="Trèfle (couvert)", kc_ini=0.40, kc_mid=0.95, kc_end=0.95,
       stades=(0.15, 0.35, 0.50, 0.0), racines_max=0.8, p=0.55, ky=None,
       type_cn="legumineuses", residus=0.80, vente=False,
       sources=dict(tout="estime (légumineuse de couverture détruite verte)")),
]}

# Part des résidus qui reste en surface selon le travail du sol (choix de l'équipe, à calibrer).
TRAVAIL_SOL = {"semis_direct": 1.0, "travail_reduit": 0.6, "conventionnel": 0.15}


def culture(code: str) -> Culture:
    try:
        return CULTURES[code]
    except KeyError:
        connues = ", ".join(sorted(CULTURES))
        raise ValueError(f"Culture inconnue « {code} ». Cultures connues : {connues}") from None
