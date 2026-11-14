"""Niveau des nappes : puits suivis en continu par l'USGS (National Water Information System).

Source : API Water Data de l'USGS (https://api.waterdata.usgs.gov/ogcapi/v0, sans clé ; une clé
api.data.gov gratuite, USGS_API_KEY dans l'environnement ou le fichier .env, relève la limite
de requêtes).
États-Unis seulement : ailleurs (Québec), la composante « nappes » reste vide, sauf si on
la donne à la main (--nappes-percentile).

Méthode, la même que les cartes « Groundwater Watch » de l'USGS :
  1. puits mesurés chaque jour (moyenne journalière, statistique 00003) de la profondeur de
     l'eau sous la surface (paramètre 72019), à moins de RAYON_KM, avec au moins
     ANNEES_MIN années de mesures et des mesures dans les ANNEES_RECENTES dernières années ;
  2. pour chaque puits : moyenne de chaque mois, puis percentile de chaque mois récent
     parmi le même mois de toutes les années (100 = nappe la plus haute jamais vue,
     0 = la plus basse) ; on fait la moyenne des mois récents ;
  3. percentile des nappes = médiane des puits (au plus N_PUITS, les plus proches).
Rayon, durée minimale et fenêtre récente sont des choix de l'équipe, à calibrer.
"""
from __future__ import annotations

import math
from collections import defaultdict

from .reseau import ErreurDonnees, get_json, parametre

URL_USGS = "https://api.waterdata.usgs.gov/ogcapi/v0/collections"
CODE_PROFONDEUR = "72019"        # profondeur de l'eau sous la surface du sol (pieds)
STAT_MOYENNE = "00003"
RAYON_KM = 50.0
ANNEES_MIN = 10
ANNEES_RECENTES = 3
N_PUITS = 5
MOIS_MIN_HISTOIRE = 8            # années minimum pour juger un mois


def dans_les_etats_unis(lat: float, lon: float) -> bool:
    """Boîtes larges : 48 États, Alaska, Hawaï, Porto Rico. L'API dit ensuite s'il y a des puits."""
    return ((24.0 <= lat <= 49.6 and -125.0 <= lon <= -66.5) or
            (51.0 <= lat <= 71.6 and -170.0 <= lon <= -129.0) or
            (18.8 <= lat <= 22.4 and -160.5 <= lon <= -154.5) or
            (17.8 <= lat <= 18.6 and -67.5 <= lon <= -65.2))


def distance_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def _get(collection: str, params: dict, utiliser_cache: bool):
    """GET paginé sur une collection OGC de l'USGS ; renvoie toutes les « features »."""
    params = dict(params, f="json")
    cle = parametre("USGS_API_KEY")
    if cle:
        params["api_key"] = cle
    url = f"{URL_USGS}/{collection}/items"
    features = []
    for _ in range(20):                                   # 20 pages au plus
        js = get_json(url, params, "USGS Water Data", timeout=90, utiliser_cache=utiliser_cache)
        if not isinstance(js, dict) or "features" not in js:
            raise ErreurDonnees(f"Réponse USGS inattendue : {str(js)[:300]}")
        features += js["features"]
        suivant = next((l["href"] for l in js.get("links", []) if l.get("rel") == "next"), None)
        if not suivant:
            break
        url, params = suivant, {}
    return features


def choisir_puits(features, lat: float, lon: float, fin: int) -> list[dict]:
    """Garde les séries journalières moyennes assez longues et récentes, proches d'abord."""
    retenus = {}
    for f in features:
        p = f.get("properties", {})
        if p.get("computation_period_identifier") != "Daily" or p.get("statistic_id") != STAT_MOYENNE:
            continue
        geo = f.get("geometry") or {}
        coords = geo.get("coordinates")
        if not coords or not p.get("begin") or not p.get("end"):
            continue
        debut_mesures, fin_mesures = int(p["begin"][:4]), int(p["end"][:4])
        if fin_mesures < fin - ANNEES_RECENTES + 1 or min(fin_mesures, fin) - debut_mesures + 1 < ANNEES_MIN:
            continue
        d = distance_km(lat, lon, coords[1], coords[0])
        if d > RAYON_KM:
            continue
        ident = p["monitoring_location_id"]
        if ident not in retenus or d < retenus[ident]["distance_km"]:
            retenus[ident] = dict(id=ident, distance_km=round(d, 1),
                                  debut=debut_mesures, fin=fin_mesures)
    return sorted(retenus.values(), key=lambda w: w["distance_km"])[:N_PUITS]


def percentile_recent(mesures, fin: int) -> float | None:
    """`mesures` : liste (AAAA-MM-JJ, profondeur). Percentile moyen des mois récents
    (fin − ANNEES_RECENTES + 1 .. fin), chacun comparé au même mois des autres années."""
    par_mois = defaultdict(list)
    for date, v in mesures:
        try:
            a, m = int(date[:4]), int(date[5:7])
            par_mois[(a, m)].append(float(v))
        except (TypeError, ValueError):
            continue
    moyenne = {k: sum(v) / len(v) for k, v in par_mois.items() if k[0] <= fin}
    pcts = []
    for (a, m), prof in moyenne.items():
        if a < fin - ANNEES_RECENTES + 1:
            continue
        histoire = [p for (aa, mm), p in moyenne.items() if mm == m]
        if len(histoire) < MOIS_MIN_HISTOIRE:
            continue
        # profondeur plus grande = nappe plus basse ; percentile du NIVEAU de la nappe
        plus_bas = sum(1 for h in histoire if h > prof)
        egaux = sum(1 for h in histoire if h == prof)
        pcts.append(100.0 * (plus_bas + 0.5 * egaux) / len(histoire))
    return sum(pcts) / len(pcts) if pcts else None


def nappes_usgs(lat: float, lon: float, debut: int, fin: int, utiliser_cache: bool = True):
    """Percentile des nappes autour du point, ou None s'il n'y a pas de puits utilisable."""
    if not dans_les_etats_unis(lat, lon):
        return None
    dlat = RAYON_KM / 111.32
    dlon = RAYON_KM / (111.32 * max(math.cos(math.radians(lat)), 0.1))
    bbox = f"{lon - dlon:.4f},{lat - dlat:.4f},{lon + dlon:.4f},{lat + dlat:.4f}"
    meta = _get("time-series-metadata", dict(bbox=bbox, parameter_code=CODE_PROFONDEUR,
                                             limit=1000), utiliser_cache)
    puits = choisir_puits(meta, lat, lon, fin)
    if not puits:
        return None
    debut_hist = min(debut, fin - 19)                     # au moins 20 ans d'historique
    resultats = []
    for w in puits:
        feats = _get("daily", dict(monitoring_location_id=w["id"], parameter_code=CODE_PROFONDEUR,
                                   statistic_id=STAT_MOYENNE, properties="time,value",
                                   skipGeometry="true", datetime=f"{debut_hist}-01-01/{fin}-12-31",
                                   limit=10000), utiliser_cache)
        mesures = [(f["properties"].get("time", ""), f["properties"].get("value")) for f in feats]
        p = percentile_recent(mesures, fin)
        if p is not None:
            resultats.append(dict(w, percentile=round(p, 1), jours_mesures=len(mesures)))
    if not resultats:
        return None
    valeurs = sorted(r["percentile"] for r in resultats)
    n = len(valeurs)
    mediane = valeurs[n // 2] if n % 2 else (valeurs[n // 2 - 1] + valeurs[n // 2]) / 2
    return dict(percentile=round(mediane, 1), puits=resultats,
                source=f"USGS NWIS ({n} puits à moins de {RAYON_KM:.0f} km, "
                       f"{ANNEES_RECENTES} dernières années vs historique)")
