"""Comparer ce que le programme calcule avec des données indépendantes (commande « valider »).

  1. Pluie : NASA POWER (utilisée par le seau) vs ERA5 : écart des moyennes annuelles et
     corrélation des totaux annuels (les années sèches tombent-elles les mêmes ?).
  2. ET0 : notre Penman-Monteith FAO-56 sur la météo POWER vs l'ET0 FAO-56 d'ERA5.
  3. Humidité du sol : remplissage du seau simulé vs humidité ERA5 0-100 cm, en saison de
     culture. On compare les ANOMALIES (écart à la moyenne du même mois), comme pour la
     validation de SMAP : sinon la simple baisse de l'humidité au fil de l'été donne une
     bonne corrélation à n'importe quel modèle. MERRA-2 (GWETROOT) vs ERA5 sert de repère :
     deux modèles de grands centres ne s'accordent pas parfaitement non plus.

Repères (choix de l'équipe, à discuter) : écart de pluie ou d'ET0 sous 15 %, corrélation des
anomalies d'humidité au-dessus de 0,5.
"""
from __future__ import annotations

import numpy as np

from .earthdata import mois_saison

ECART_MAX_PCT = 15.0
R_MIN = 0.5


def _aligner(dates_a, a, dates_b, b):
    communs, ia, ib = np.intersect1d(dates_a, dates_b, return_indices=True)
    return communs, np.asarray(a, float)[ia], np.asarray(b, float)[ib]


def _annuels(dates, v, debut, fin):
    annees = dates.astype("datetime64[Y]").astype(int) + 1970
    out = []
    for y in range(debut, fin + 1):
        m = annees == y
        ok = np.isfinite(v[m])
        out.append(v[m][ok].sum() if m.sum() and ok.mean() > 0.9 else np.nan)
    return np.array(out)


def _r(a, b) -> float | None:
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 5 or np.std(a[ok]) == 0 or np.std(b[ok]) == 0:
        return None
    return float(np.corrcoef(a[ok], b[ok])[0, 1])


def _anomalies(dates, v):
    """Écart à la moyenne du même mois sur toutes les années."""
    mois = dates.astype("datetime64[M]").astype(int) % 12 + 1
    out = np.full(len(v), np.nan)
    for m in range(1, 13):
        sel = (mois == m) & np.isfinite(v)
        if sel.any():
            out[sel] = v[sel] - v[sel].mean()
    return out


def _ecart_pct(a, b):
    return float(100 * (a / b - 1)) if b else float("nan")


def comparer(meteo, et0, era5, remplissage, debut: int, fin: int) -> dict:
    """`remplissage` : part du seau pleine chaque jour (alignée sur meteo.dates)."""
    # 1. pluie
    d, p_power, p_era5 = _aligner(meteo.dates, meteo.pluie, era5.dates, era5.pluie)
    an_power, an_era5 = _annuels(d, p_power, debut, fin), _annuels(d, p_era5, debut, fin)
    pluie = dict(power_mm_an=round(float(np.nanmean(an_power)), 0),
                 era5_mm_an=round(float(np.nanmean(an_era5)), 0),
                 ecart_pct=round(_ecart_pct(np.nanmean(an_power), np.nanmean(an_era5)), 1),
                 r_annuel=_arrondi(_r(an_power, an_era5)))
    # 2. ET0
    d, e_calc, e_era5 = _aligner(meteo.dates, et0, era5.dates, era5.et0)
    an_calc, an_e5 = _annuels(d, e_calc, debut, fin), _annuels(d, e_era5, debut, fin)
    et0_res = dict(calculee_mm_an=round(float(np.nanmean(an_calc)), 0),
                   era5_mm_an=round(float(np.nanmean(an_e5)), 0),
                   ecart_pct=round(_ecart_pct(np.nanmean(an_calc), np.nanmean(an_e5)), 1),
                   r_annuel=_arrondi(_r(an_calc, an_e5)))
    # 3. humidité, saison de culture des années debut..fin
    d, seau, sm_era5 = _aligner(meteo.dates, remplissage, era5.dates, era5.humidite_0_100)
    annees = d.astype("datetime64[Y]").astype(int) + 1970
    mois = d.astype("datetime64[M]").astype(int) % 12 + 1
    saison = np.isin(mois, mois_saison(meteo.lat)) & (annees >= debut) & (annees <= fin)
    an_seau, an_sm = _anomalies(d[saison], seau[saison]), _anomalies(d[saison], sm_era5[saison])
    humidite = dict(n_jours=int(saison.sum()),
                    r_seau_era5=_arrondi(_r(seau[saison], sm_era5[saison])),
                    r_anomalies_seau_era5=_arrondi(_r(an_seau, an_sm)))
    if meteo.humidite_racines is not None:
        _, merra, _ = _aligner(meteo.dates, meteo.humidite_racines, era5.dates, era5.humidite_0_100)
        humidite["r_anomalies_merra2_era5"] = _arrondi(
            _r(_anomalies(d[saison], merra[saison]), an_sm))
    return dict(pluie=pluie, et0=et0_res, humidite=humidite, verdicts=_verdicts(pluie, et0_res, humidite))


def confiance(res: dict) -> dict:
    """Étape 7 du document : la note est affichée avec une confiance « faible » dès qu'un
    repère n'est pas tenu (écart de pluie ou d'ET0 au-delà de 15 %, seau qui ne suit pas les
    sécheresses), avec la raison, plutôt que cachée."""
    raisons = [v[2:] for v in res["verdicts"] if v.startswith("⚠")]
    return dict(niveau="faible" if raisons else "bonne", raisons=raisons)


def _arrondi(x):
    return None if x is None else round(x, 2)


def _verdicts(pluie, et0, humidite) -> list[str]:
    out = []
    ok = lambda b: "✔" if b else "⚠"
    e = pluie["ecart_pct"]
    out.append(f"{ok(abs(e) <= ECART_MAX_PCT)} Pluie : POWER {e:+.0f} % par rapport à ERA5"
               + ("" if abs(e) <= ECART_MAX_PCT else
                  " : les sous-notes C et D dépendent de la pluie, comparez avec une station locale"
                  " (CoCoRaHS, Environnement Canada)"))
    e = et0["ecart_pct"]
    out.append(f"{ok(abs(e) <= ECART_MAX_PCT)} ET0 : notre calcul {e:+.0f} % par rapport à ERA5"
               + ("" if abs(e) <= ECART_MAX_PCT else " : la sous-note A et la demande en eau en dépendent"))
    r = humidite["r_anomalies_seau_era5"]
    if r is None:
        out.append("– Humidité : pas assez de jours communs pour comparer")
    else:
        repere = humidite.get("r_anomalies_merra2_era5")
        out.append(f"{ok(r >= R_MIN)} Humidité : le seau suit les sécheresses d'ERA5 avec r = {r:.2f}"
                   + (f" (MERRA-2 vs ERA5 : r = {repere:.2f})" if repere is not None else ""))
    return out
