"""Le sol de la parcelle : taille du « seau » et facilité d'infiltration.

Ordre de recherche (vraies bases) :
  1. SSURGO (USDA, États-Unis) via Soil Data Access : réserve d'eau mesurée (muaggatt :
     aws025wta, aws0150wta, en cm) et groupe hydrologique (hydgrpdcd).
  2. SoilGrids 2.0 (ISRIC, monde entier, dont le Québec) : sable, argile, carbone par
     profondeur -> réserve d'eau par la formule de Saxton & Rawls (2006).
  3. Sol saisi à la main (--sol-manuel), si les deux bases ne répondent pas.

Le seau a deux étages : « haut » = 0 à 30 cm, « bas » = 30 à 150 cm.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .reseau import ErreurDonnees, get_json, post_json

URL_SDA = "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest"
URL_SOILGRIDS = "https://rest.isric.org/soilgrids/v2.0/properties/query"
EPAISSEUR_HAUT = 300.0   # mm
EPAISSEUR_BAS = 1200.0   # mm


@dataclass
class Sol:
    taw_haut: float          # mm d'eau utilisable dans 0-30 cm
    taw_bas: float           # mm d'eau utilisable dans 30-150 cm
    groupe_hydro: str        # A, B, C ou D
    source: str
    details: dict = field(default_factory=dict)
    pente: float | None = None   # m/m (SRTM, terrain.py) ; None = tableaux NRCS tels quels (~5 %)

    @property
    def taw_total(self) -> float:
        return self.taw_haut + self.taw_bas


# --------------------------------------------------------------------------------------
# Saxton & Rawls (2006), Soil Sci. Soc. Am. J. 70:1569-1578, tableau 1 (équations 1 et 2)
# --------------------------------------------------------------------------------------
def saxton_rawls(sable_pct: float, argile_pct: float, mo_pct: float) -> dict:
    """Teneurs en eau (m³/m³) au point de flétrissement (1500 kPa) et à la capacité au
    champ (33 kPa), à partir du sable (%), de l'argile (%) et de la matière organique (%)."""
    S, C = sable_pct / 100.0, argile_pct / 100.0
    OM = min(max(mo_pct, 0.0), 8.0)          # équations calibrées jusqu'à ~8 % de MO
    t1500 = (-0.024 * S + 0.487 * C + 0.006 * OM + 0.005 * S * OM - 0.013 * C * OM
             + 0.068 * S * C + 0.031)
    theta1500 = t1500 + (0.14 * t1500 - 0.02)
    t33 = (-0.251 * S + 0.195 * C + 0.011 * OM + 0.006 * S * OM - 0.027 * C * OM
           + 0.452 * S * C + 0.299)
    theta33 = t33 + (1.283 * t33 ** 2 - 0.374 * t33 - 0.015)
    return dict(pf=theta1500, cc=theta33, eau_utile=max(theta33 - theta1500, 0.0))


# --------------------------------------------------------------------------------------
# Texture USDA -> groupe hydrologique (approximation à valider, hors États-Unis)
# --------------------------------------------------------------------------------------
def classe_texture(sable: float, argile: float) -> str:
    limon = 100.0 - sable - argile
    if limon + 1.5 * argile < 15:
        return "sable"
    if limon + 2 * argile < 30:
        return "sable loameux"
    if (7 <= argile < 20 and sable > 52) or (argile < 7 and limon < 50):
        return "loam sableux"
    if 7 <= argile < 27 and 28 <= limon < 50 and sable <= 52:
        return "loam"
    if (limon >= 50 and 12 <= argile < 27) or (50 <= limon < 80 and argile < 12):
        return "loam limoneux"
    if limon >= 80 and argile < 12:
        return "limon"
    if 20 <= argile < 35 and limon < 28 and sable > 45:
        return "loam sablo-argileux"
    if 27 <= argile < 40 and 20 < sable <= 45:
        return "loam argileux"
    if 27 <= argile < 40 and sable <= 20:
        return "loam limono-argileux"
    if argile >= 35 and sable > 45:
        return "argile sableuse"
    if argile >= 40 and limon >= 40:
        return "argile limoneuse"
    return "argile"


GROUPE_PAR_TEXTURE = {
    "sable": "A", "sable loameux": "A", "loam sableux": "A",
    "loam": "B", "loam limoneux": "B", "limon": "B",
    "loam sablo-argileux": "C",
    "loam argileux": "D", "loam limono-argileux": "D", "argile sableuse": "D",
    "argile limoneuse": "D", "argile": "D",
}


def groupe_depuis_texture(sable: float, argile: float) -> str:
    return GROUPE_PAR_TEXTURE[classe_texture(sable, argile)]


# --------------------------------------------------------------------------------------
# 1. SSURGO via Soil Data Access
# --------------------------------------------------------------------------------------
def requete_ssurgo(lat: float, lon: float) -> str:
    return ("SELECT TOP 1 mu.mukey, mu.muname, ma.aws025wta, ma.aws0150wta, ma.hydgrpdcd "
            "FROM mapunit mu INNER JOIN muaggatt ma ON ma.mukey = mu.mukey "
            "WHERE mu.mukey IN (SELECT * FROM SDA_Get_Mukey_from_intersection_with_WktWgs84("
            f"'point({lon:.6f} {lat:.6f})'))")


def lire_reponse_ssurgo(js) -> Sol | None:
    """Réponse SDA au format JSON+COLUMNNAME : {"Table": [[noms...], [valeurs...]]}."""
    table = (js or {}).get("Table") if isinstance(js, dict) else None
    if not table or len(table) < 2:
        return None
    lignes = dict(zip([c.lower() for c in table[0]], table[1]))

    def nombre(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    aws025, aws0150 = nombre(lignes.get("aws025wta")), nombre(lignes.get("aws0150wta"))
    if aws025 is None or aws0150 is None or aws0150 <= 0:
        return None
    haut = aws025 * 10.0 * (300.0 / 250.0)           # cm -> mm, 0-25 cm ramené à 0-30 cm
    haut = min(haut, aws0150 * 10.0)
    bas = max(aws0150 * 10.0 - haut, 0.0)
    grp = (lignes.get("hydgrpdcd") or "").strip().upper()
    groupe = grp[0] if grp[:1] in ("A", "B", "C", "D") else "B"
    return Sol(haut, bas, groupe, source="SSURGO (USDA Soil Data Access)",
               details=dict(mukey=lignes.get("mukey"), unite=lignes.get("muname"),
                            aws0_25_cm=aws025, aws0_150_cm=aws0150,
                            groupe_brut=grp or "inconnu (B par défaut)"))


def sol_ssurgo(lat: float, lon: float, utiliser_cache: bool = True) -> Sol | None:
    js = post_json(URL_SDA, {"query": requete_ssurgo(lat, lon), "format": "JSON+COLUMNNAME"},
                   "USDA Soil Data Access", utiliser_cache=utiliser_cache)
    return lire_reponse_ssurgo(js)


# --------------------------------------------------------------------------------------
# 2. SoilGrids 2.0
# --------------------------------------------------------------------------------------
PROFONDEURS_SG = ["0-5cm", "5-15cm", "15-30cm", "30-60cm", "60-100cm", "100-200cm"]
# épaisseur (mm) de chaque couche SoilGrids comptée dans l'étage haut / bas
POIDS_HAUT = {"0-5cm": 50, "5-15cm": 100, "15-30cm": 150}
POIDS_BAS = {"30-60cm": 300, "60-100cm": 400, "100-200cm": 500}   # 100-150 cm seulement


def lire_reponse_soilgrids(js: dict) -> Sol:
    try:
        couches = js["properties"]["layers"]
    except (KeyError, TypeError):
        raise ErreurDonnees(f"Réponse SoilGrids inattendue : {str(js)[:300]}")
    valeurs = {}
    for c in couches:
        facteur = float(c.get("unit_measure", {}).get("d_factor", 10) or 10)
        for d in c.get("depths", []):
            v = d.get("values", {}).get("mean")
            valeurs[(c["name"], d["label"])] = None if v is None else v / facteur
    haut = bas = 0.0
    sable_h, argile_h, mo_h, poids_h = 0.0, 0.0, 0.0, 0.0
    detail = {}
    for prof in PROFONDEURS_SG:
        s, a, soc = (valeurs.get(("sand", prof)), valeurs.get(("clay", prof)),
                     valeurs.get(("soc", prof)))
        if s is None or a is None:
            raise ErreurDonnees(
                "SoilGrids n'a pas de texture à ce point (eau, ville ou roche ?). "
                "Vérifiez les coordonnées ou utilisez --sol-manuel.")
        mo = (soc or 0.0) / 10.0 * 1.724                  # g C/kg -> % de matière organique
        eu = saxton_rawls(s, a, mo)["eau_utile"]
        detail[prof] = dict(sable_pct=round(s, 1), argile_pct=round(a, 1), mo_pct=round(mo, 2),
                            eau_utile_mm_par_m=round(eu * 1000, 1))
        if prof in POIDS_HAUT:
            haut += eu * POIDS_HAUT[prof]
            w = POIDS_HAUT[prof]
            sable_h += s * w; argile_h += a * w; mo_h += mo * w; poids_h += w
        else:
            bas += eu * POIDS_BAS[prof]
    s_moy, a_moy = sable_h / poids_h, argile_h / poids_h
    texture = classe_texture(s_moy, a_moy)
    return Sol(haut, bas, GROUPE_PAR_TEXTURE[texture],
               source="SoilGrids 2.0 (ISRIC) + Saxton & Rawls 2006",
               details=dict(couches=detail, texture_0_30cm=texture,
                            groupe_hydro="estimé d'après la texture (approximation)"))


def sol_soilgrids(lat: float, lon: float, utiliser_cache: bool = True) -> Sol:
    params = dict(lon=f"{lon:.5f}", lat=f"{lat:.5f}", property=["sand", "clay", "soc"],
                  depth=PROFONDEURS_SG, value="mean")
    js = get_json(URL_SOILGRIDS, params, "SoilGrids (ISRIC)", timeout=90,
                  utiliser_cache=utiliser_cache)
    return lire_reponse_soilgrids(js)


# --------------------------------------------------------------------------------------
# 3. Sol saisi à la main
# --------------------------------------------------------------------------------------
def sol_manuel(sable: float, argile: float, mo: float, groupe: str | None = None) -> Sol:
    eu = saxton_rawls(sable, argile, mo)["eau_utile"]
    texture = classe_texture(sable, argile)
    return Sol(eu * EPAISSEUR_HAUT, eu * EPAISSEUR_BAS,
               (groupe or GROUPE_PAR_TEXTURE[texture]).upper(),
               source="Sol saisi à la main + Saxton & Rawls 2006",
               details=dict(sable_pct=sable, argile_pct=argile, mo_pct=mo, texture=texture))


def trouver_sol(lat: float, lon: float, manuel: dict | None = None, groupe: str | None = None,
                utiliser_cache: bool = True, journal=print) -> Sol:
    """SSURGO, puis SoilGrids, puis sol manuel. `journal` reçoit les messages d'étape."""
    if manuel:
        return sol_manuel(manuel["sable"], manuel["argile"], manuel["mo"], groupe)
    if 18.0 <= lat <= 72.0 and -180.0 <= lon <= -65.0:   # boîte large des États-Unis
        try:
            s = sol_ssurgo(lat, lon, utiliser_cache)
            if s is not None:
                if groupe:
                    s.groupe_hydro = groupe.upper()
                return s
            journal("  SSURGO : aucune donnée à ce point (hors États-Unis ?) -> SoilGrids")
        except ErreurDonnees as e:
            journal(f"  SSURGO indisponible ({e}) -> SoilGrids")
    try:
        s = sol_soilgrids(lat, lon, utiliser_cache)
    except ErreurDonnees as e:
        raise ErreurDonnees(f"{e} SoilGrids est parfois en maintenance : réessayez plus tard ou "
                            "donnez le sol à la main, ex. --sol-manuel 40,20,3 "
                            "(sable %, argile %, matière organique %).") from None
    if groupe:
        s.groupe_hydro = groupe.upper()
        s.details["groupe_hydro"] = "saisi à la main"
    return s
