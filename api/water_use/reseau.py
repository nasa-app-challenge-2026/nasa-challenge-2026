"""Accès réseau commun : requêtes HTTP avec cache disque et messages d'erreur lisibles.

Le cache évite de redemander les mêmes données (NASA POWER bloque les requêtes répétées
pour un même point) et permet de relancer les calculs sans connexion une fois les données
téléchargées. Dossier par défaut : .cache_donnees/ à la racine du projet ; on peut le changer
avec la variable d'environnement WATER_USE_CACHE.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

DOSSIER_CACHE = Path(os.environ.get(
    "WATER_USE_CACHE", Path(__file__).resolve().parent.parent / ".cache_donnees"))


FICHIER_ENV = Path(__file__).resolve().parent.parent / ".env"


class ErreurDonnees(RuntimeError):
    """Une source de données n'a pas répondu ou a répondu quelque chose d'inattendu."""


def parametre(nom: str) -> str | None:
    """Valeur d'une variable d'environnement, sinon de la ligne « NOM=valeur » du fichier
    .env à la racine du projet (identifiants Earthdata, clé USGS ; voir .env.exemple)."""
    v = os.environ.get(nom)
    if v:
        return v
    try:
        lignes = FICHIER_ENV.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return None
    for ligne in lignes:
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, valeur = ligne.split("=", 1)
        if cle.strip() == nom:
            valeur = valeur.strip()
            if len(valeur) >= 2 and valeur[0] == valeur[-1] and valeur[0] in "\"'":
                valeur = valeur[1:-1]
            return valeur or None
    return None


def _requests():
    try:
        import requests
    except ImportError as e:  # pragma: no cover
        raise ErreurDonnees("Le module « requests » manque : lancez  pip install -r requirements.txt") from e
    return requests


def _chemin_cache(cle: str) -> Path:
    return DOSSIER_CACHE / (hashlib.sha256(cle.encode()).hexdigest()[:24] + ".json")


def lire_cache(cle: str):
    f = _chemin_cache(cle)
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return None


def ecrire_cache(cle: str, contenu) -> None:
    DOSSIER_CACHE.mkdir(parents=True, exist_ok=True)
    _chemin_cache(cle).write_text(json.dumps(contenu), encoding="utf-8")


def get_json(url: str, params: dict, nom_source: str, timeout: float = 90, essais: int = 3,
             utiliser_cache: bool = True):
    """GET qui renvoie du JSON, avec cache et 3 essais espacés."""
    cle = url + "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items(), key=lambda kv: kv[0])
                               for v in (v if isinstance(v, (list, tuple)) else [v]))
    if utiliser_cache:
        deja = lire_cache(cle)
        if deja is not None:
            return deja
    requests = _requests()
    derniere = None
    for i in range(essais):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                contenu = r.json()
                ecrire_cache(cle, contenu)
                return contenu
            derniere = f"code HTTP {r.status_code} : {r.text[:300]}"
            if r.status_code in (400, 404, 422):
                break                      # requête invalide : inutile de réessayer
        except Exception as e:             # réseau coupé, délai dépassé, JSON invalide
            derniere = f"{type(e).__name__} : {e}"
        time.sleep(2 * (i + 1))
    raise ErreurDonnees(f"{nom_source} n'a pas répondu correctement ({derniere}).")


def post_json(url: str, corps: dict, nom_source: str, timeout: float = 60, essais: int = 3,
              utiliser_cache: bool = True):
    """POST JSON -> JSON, avec cache et 3 essais."""
    cle = url + "|" + json.dumps(corps, sort_keys=True)
    if utiliser_cache:
        deja = lire_cache(cle)
        if deja is not None:
            return deja
    requests = _requests()
    derniere = None
    for i in range(essais):
        try:
            r = requests.post(url, json=corps, timeout=timeout,
                              headers={"Accept": "application/json"})
            if r.status_code == 200:
                contenu = r.json() if r.text.strip() else {}
                ecrire_cache(cle, contenu)
                return contenu
            derniere = f"code HTTP {r.status_code} : {r.text[:300]}"
            if r.status_code in (400, 404, 422):
                break
        except Exception as e:
            derniere = f"{type(e).__name__} : {e}"
        time.sleep(2 * (i + 1))
    raise ErreurDonnees(f"{nom_source} n'a pas répondu correctement ({derniere}).")
