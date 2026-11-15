"""SMAP et ECOSTRESS par NASA AppEEARS (compte NASA Earthdata gratuit requis).

API : https://appeears.earthdatacloud.nasa.gov/api/  (documentation à la même adresse)
Identifiants, au choix (le premier trouvé gagne) :
  - variables d'environnement EARTHDATA_USERNAME et EARTHDATA_PASSWORD ;
  - fichier .env à la racine du projet, mêmes noms (modèle : .env.exemple ; exclu de git) ;
  - fichier ~/.netrc (Windows : %USERPROFILE%\\_netrc) avec une ligne
        machine urs.earthdata.nasa.gov login MON_NOM password MON_MOT_DE_PASSE
Compte : https://urs.earthdata.nasa.gov/users/new

Une demande AppEEARS est une « tâche » traitée sur les serveurs de la NASA (de une minute à
plus d'une heure). Le programme envoie la tâche, attend jusqu'à `attente_s`, puis :
  - si elle est finie, lit le CSV et le garde dans le cache ;
  - sinon, garde le numéro de la tâche dans le cache et lève EnAttente ; au lancement suivant
    il reprend la même tâche au lieu d'en créer une nouvelle.

Produits utilisés :
  SPL4SMGP.008   SMAP L4 (9 km, toutes les 3 h) : humidité du sol racinaire 0-100 cm en
                 percentile de sa propre climatologie (couche Geophysical_Data_sm_rootzone_pctl)
  ECO_L4T_ESI.002  ECOSTRESS L4 (70 m) : indice de stress évaporatif ESI = ET / ET potentielle
"""
from __future__ import annotations

import csv
import io
import json
import netrc
import os
import time
from pathlib import Path

import numpy as np

from .reseau import ErreurDonnees, _requests, ecrire_cache, lire_cache, parametre

URL_APPEEARS = "https://appeears.earthdatacloud.nasa.gov/api/"
HOTE_EARTHDATA = "urs.earthdata.nasa.gov"
ANNEES_RECENTES = 3
SMAP = ("SPL4SMGP.008", "Geophysical_Data_sm_rootzone_pctl")
ECOSTRESS = ("ECO_L4T_ESI.002", "ESI")
DEBUT_ECOSTRESS = 2018


class EnAttente(ErreurDonnees):
    """La tâche AppEEARS tourne encore sur les serveurs de la NASA."""


def identifiants():
    """(nom, mot de passe) Earthdata, ou None si rien n'est configuré."""
    u, p = parametre("EARTHDATA_USERNAME"), parametre("EARTHDATA_PASSWORD")
    if u and p:
        return u, p
    for nom in (".netrc", "_netrc"):
        f = Path.home() / nom
        if f.exists():
            try:
                a = netrc.netrc(str(f)).authenticators(HOTE_EARTHDATA)
            except (netrc.NetrcParseError, OSError):
                a = None
            if a and a[0] and a[2]:
                return a[0], a[2]
    return None


_jeton = {}


def jeton() -> str:
    ids = identifiants()
    if ids is None:
        raise ErreurDonnees("identifiants NASA Earthdata absents (EARTHDATA_USERNAME / "
                            "EARTHDATA_PASSWORD, ou ~/.netrc)")
    if ids[0] in _jeton:
        return _jeton[ids[0]]
    requests = _requests()
    try:
        r = requests.post(URL_APPEEARS + "login", auth=ids, timeout=60,
                          headers={"Content-Length": "0"})
    except Exception as e:
        raise ErreurDonnees(f"AppEEARS injoignable ({type(e).__name__} : {e})") from None
    if r.status_code != 200:
        raise ErreurDonnees(f"connexion AppEEARS refusée (code HTTP {r.status_code} : "
                            f"{r.text[:200]}). Vérifiez le nom et le mot de passe Earthdata.")
    _jeton[ids[0]] = r.json()["token"]
    return _jeton[ids[0]]


def _appel(methode: str, chemin: str, **k):
    requests = _requests()
    k.setdefault("timeout", 120)
    k.setdefault("headers", {})["Authorization"] = f"Bearer {jeton()}"
    derniere = None
    for i in range(3):
        try:
            r = requests.request(methode, URL_APPEEARS + chemin, **k)
            if r.status_code in (200, 201, 202):
                return r
            derniere = f"code HTTP {r.status_code} : {r.text[:300]}"
            if r.status_code in (400, 401, 403, 404, 422):
                break
        except Exception as e:
            derniere = f"{type(e).__name__} : {e}"
        time.sleep(3 * (i + 1))
    raise ErreurDonnees(f"AppEEARS n'a pas répondu correctement ({derniere}).")


def lire_csv_appeears(texte: str, couche: str) -> list[tuple[str, float]]:
    """CSV de points AppEEARS -> [(AAAA-MM-JJ, valeur)], valeurs manquantes retirées.
    La colonne de la valeur se termine par le nom de la couche (ex.
    « SPL4SMGP_008_Geophysical_Data_sm_rootzone_pctl »)."""
    lecteur = csv.DictReader(io.StringIO(texte))
    champs = lecteur.fieldnames or []
    col_date = next((c for c in champs if c.strip().lower() == "date"), None)
    col_val = next((c for c in champs if c.endswith("_" + couche) or c == couche), None)
    if col_date is None or col_val is None:
        raise ErreurDonnees(f"CSV AppEEARS sans colonne Date ou {couche} : {champs[:12]}")
    sortie = []
    for ligne in lecteur:
        try:
            v = float(ligne[col_val])
        except (TypeError, ValueError):
            continue
        if not np.isfinite(v) or v <= -9999 or v >= 32767:
            continue
        sortie.append((ligne[col_date][:10], v))
    return sortie


def tache_point(nom: str, produit: str, couche: str, dates: list, lat: float, lon: float,
                attente_s: float = 300, utiliser_cache: bool = True, journal=print):
    """Échantillonne `produit`/`couche` au point pour les plages `dates` (format AppEEARS)."""
    params = dict(dates=dates, layers=[dict(product=produit, layer=couche)],
                  coordinates=[dict(latitude=round(lat, 5), longitude=round(lon, 5),
                                    id="parcelle")])
    cle = "appeears|" + json.dumps(params, sort_keys=True)
    if utiliser_cache:
        deja = lire_cache(cle)
        if deja is not None:
            return [tuple(x) for x in deja]
    tache = lire_cache(cle + "|tache")
    if tache is None:
        r = _appel("POST", "task", json=dict(task_type="point", task_name=nom, params=params))
        tache = r.json()["task_id"]
        ecrire_cache(cle + "|tache", tache)
        journal(f"  AppEEARS : tâche {tache} envoyée ({produit})")
    fin_attente = time.time() + attente_s
    while True:
        etat = _appel("GET", f"task/{tache}").json().get("status")
        if etat == "done":
            break
        if etat == "error":
            ecrire_cache(cle + "|tache", None)
            raise ErreurDonnees(f"la tâche AppEEARS {tache} a échoué côté NASA ; elle sera "
                                "renvoyée au prochain lancement.")
        if time.time() > fin_attente:
            raise EnAttente(f"tâche AppEEARS {tache} encore en cours ({etat}) : relancez la "
                            "commande plus tard, elle reprendra là où elle en est.")
        time.sleep(15)
    fichiers = _appel("GET", f"bundle/{tache}").json().get("files", [])
    marque = produit.replace(".", "-")
    csvs = [f for f in fichiers if f.get("file_type") == "csv" and marque in f.get("file_name", "")]
    if not csvs:
        raise ErreurDonnees(f"la tâche AppEEARS {tache} n'a pas produit de CSV {marque}.")
    texte = _appel("GET", f"bundle/{tache}/{csvs[0]['file_id']}", allow_redirects=True).text
    valeurs = lire_csv_appeears(texte, couche)
    ecrire_cache(cle, valeurs)
    ecrire_cache(cle + "|tache", None)
    return valeurs


def mois_saison(lat: float) -> list[int]:
    """Saison de culture : mai-septembre au nord, novembre-mars au sud."""
    return [5, 6, 7, 8, 9] if lat >= 0 else [11, 12, 1, 2, 3]


def _plages_saison(lat: float) -> list[tuple[str, str]]:
    return [("05-01", "09-30")] if lat >= 0 else [("01-01", "03-31"), ("11-01", "12-31")]


# --------------------------------------------------------------------------------------
# SMAP L4 : sécheresse du sol racinaire
# --------------------------------------------------------------------------------------
def dates_smap(lat: float, fin: int) -> list[dict]:
    """Les 1er, 11 et 21 de chaque mois de la saison des ANNEES_RECENTES dernières années
    (SMAP L4 a 8 images par jour ; échantillonner garde la tâche courte, et l'humidité
    racinaire varie lentement)."""
    out = []
    for a in range(fin - ANNEES_RECENTES + 1, fin + 1):
        for m in mois_saison(lat):
            for j in (1, 11, 21):
                d = f"{m:02d}-{j:02d}-{a}"
                out.append(dict(startDate=d, endDate=d))
    return out


def smap_percentile(lat: float, lon: float, fin: int, attente_s: float = 300,
                    utiliser_cache: bool = True, journal=print) -> dict:
    vals = tache_point("water-use-smap", *SMAP, dates_smap(lat, fin), lat, lon, attente_s,
                       utiliser_cache, journal)
    vals = [v for _, v in vals if 0 <= v <= 100]
    if not vals:
        raise ErreurDonnees("SMAP n'a pas de valeur à ce point (eau, glace ou ville ?).")
    return dict(percentile=round(float(np.mean(vals)), 1), n=len(vals),
                source=f"SMAP L4 {SMAP[0]} (percentile racinaire, saisons {fin - ANNEES_RECENTES + 1}-{fin})")


# --------------------------------------------------------------------------------------
# ECOSTRESS : anomalie de l'indice de stress évaporatif
# --------------------------------------------------------------------------------------
def anomalie_par_saison(valeurs, lat: float, annees_recentes: int, fin: int,
                        min_obs: int = 5, min_saisons: int = 4):
    """Moyenne de l'ESI par saison de culture, puis anomalie standardisée des saisons
    récentes : (moyenne récente − moyenne de toutes les saisons) / écart type.
    Négatif = plus de stress que d'habitude (Anderson et al. 2011)."""
    mois = mois_saison(lat)
    par_an = {}
    for date, v in valeurs:
        a, m = int(date[:4]), int(date[5:7])
        if lat < 0 and m >= 11:
            a += 1                    # hémisphère sud : novembre-décembre comptent avec la saison suivante
        if m in mois and 0.0 <= v <= 1.0 and a <= fin:
            par_an.setdefault(a, []).append(v)
    moy = {a: float(np.mean(v)) for a, v in par_an.items() if len(v) >= min_obs}
    if len(moy) < min_saisons:
        return None, moy
    tout = np.array(list(moy.values()))
    recentes = [moy[a] for a in moy if a > fin - annees_recentes]
    if not recentes or tout.std(ddof=1) <= 0:
        return None, moy
    return float((np.mean(recentes) - tout.mean()) / tout.std(ddof=1)), moy


def ecostress_esi(lat: float, lon: float, debut: int, fin: int, attente_s: float = 300,
                  utiliser_cache: bool = True, journal=print) -> dict:
    a0 = max(DEBUT_ECOSTRESS, debut)
    dates = [dict(startDate=d0, endDate=d1, recurring=True, yearRange=[a0, fin])
             for d0, d1 in _plages_saison(lat)]
    vals = tache_point("water-use-ecostress", *ECOSTRESS, dates, lat, lon, attente_s,
                       utiliser_cache, journal)
    anomalie, par_an = anomalie_par_saison(vals, lat, ANNEES_RECENTES, fin)
    if anomalie is None:
        raise ErreurDonnees(f"ECOSTRESS : trop peu d'images sans nuage ({len(vals)} valeurs, "
                            f"{len(par_an)} saisons utilisables sur au moins 4).")
    return dict(anomalie=round(anomalie, 2), esi_par_saison={a: round(v, 3) for a, v in par_an.items()},
                source=f"ECOSTRESS {ECOSTRESS[0]} (ESI, saisons {min(par_an)}-{max(par_an)})")
