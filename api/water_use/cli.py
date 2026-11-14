"""Ligne de commande.

  python -m water_use evaluer --lat 45.40 --lon -72.95 --rotations exemples/*.json
  python -m water_use evaluer --demo humide --rotations exemples/*.json     (sans réseau)
  python -m water_use connexions --lat 45.40 --lon -72.95                   (teste les bases)
  python -m water_use valider --lat 45.40 --lon -72.95                      (compare avec ERA5)
  python -m water_use cultures                                              (codes disponibles)
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import sys
import time
from pathlib import Path

import numpy as np

from . import __version__
from .cultures import CULTURES
from .et0 import et0_meteo
from .notes import evaluer_rotation, pression_sur_l_eau, secheresse_depuis_percentile
from .reseau import ErreurDonnees
from .rotation import construire_calendrier, lire_rotation


def _sol_manuel(texte):
    try:
        s, a, mo = (float(x) for x in texte.split(","))
        return dict(sable=s, argile=a, mo=mo)
    except Exception:
        raise argparse.ArgumentTypeError("--sol-manuel attend « sable,argile,mo » en %, ex. 40,20,3")


def _fichiers(motifs):
    out = []
    for m in motifs:
        trouves = sorted(glob.glob(m))
        if not trouves:
            raise SystemExit(f"Aucun fichier rotation ne correspond à « {m} »")
        out += trouves
    return out


def _barre(x, n=10):
    plein = int(round(x * n))
    return "█" * plein + "·" * (n - plein)


def _sources_extra(a, meteo, sol, debut: int, fin: int):
    """Pente (SRTM), nappes (USGS), sol sec (SMAP, sinon MERRA-2), ESI (ECOSTRESS).
    Une valeur donnée à la main l'emporte ; une base qui ne répond pas n'arrête rien.
    Renvoie (entrées de pression_sur_l_eau, sources utilisées, terrain)."""
    from . import earthdata
    from .humidite import secheresse_merra2
    from .nappes import RAYON_KM, nappes_usgs
    from .terrain import terrain_srtm
    reseau = not a.demo and not a.base_seulement
    cache = not a.sans_cache
    attente = 60 * a.attente_earthdata
    entrees = dict(nappes_percentile=None, esi=None, secheresse_sol=None)
    sources, terrain = {}, None

    def essai(nom, f):
        try:
            return f()
        except earthdata.EnAttente as e:
            print(f"  {nom} : {e}")
        except ErreurDonnees as e:
            print(f"  {nom} indisponible ({e})")
        return None

    # pente -> ruissellement
    if a.pente is not None:
        sol.pente = a.pente / 100.0
        sources["pente"] = "saisie à la main"
    elif reseau:
        print("3/6 Relief (SRTM)…")
        terrain = essai("SRTM", lambda: terrain_srtm(a.lat, a.lon, cache))
        if terrain is not None:
            sol.pente = terrain.pente
            sources["pente"] = terrain.source
    # nappes
    if a.nappes_percentile is not None:
        entrees["nappes_percentile"] = a.nappes_percentile
        sources["nappes"] = "saisi à la main"
    elif reseau:
        print("4/6 Nappes (puits USGS, États-Unis)…")
        n = essai("USGS", lambda: nappes_usgs(a.lat, a.lon, debut, fin, cache))
        if n is not None:
            entrees["nappes_percentile"] = n["percentile"]
            sources["nappes"] = f"{n['source']} : percentile {n['percentile']}"
        else:
            sources["nappes"] = (f"aucun puits USGS suivi en continu à moins de {RAYON_KM:.0f} km "
                                 "(hors États-Unis ?)")
    # sol sec et ESI
    if a.smap is not None:
        entrees["secheresse_sol"] = a.smap
        sources["sol_sec"] = "saisi à la main"
    if a.esi is not None:
        entrees["esi"] = a.esi
        sources["esi"] = "saisi à la main"
    if reseau and (a.smap is None or a.esi is None):
        print("5/6 Stress mesuré (SMAP et ECOSTRESS avec un compte Earthdata, sinon MERRA-2)…")
        compte = earthdata.identifiants() is not None
        if a.smap is None and compte:
            s = essai("SMAP", lambda: earthdata.smap_percentile(a.lat, a.lon, fin, attente, cache))
            if s is not None:
                entrees["secheresse_sol"] = round(secheresse_depuis_percentile(s["percentile"]), 3)
                sources["sol_sec"] = f"{s['source']} : percentile {s['percentile']}"
        if a.esi is None and compte:
            e = essai("ECOSTRESS", lambda: earthdata.ecostress_esi(a.lat, a.lon, debut, fin,
                                                                   attente, cache))
            if e is not None:
                entrees["esi"] = e["anomalie"]
                sources["esi"] = f"{e['source']} : anomalie {e['anomalie']:+.2f}"
            else:
                sources["esi"] = ("ECOSTRESS pas encore disponible (tâche AppEEARS en cours ou "
                                  "échouée, voir plus haut) : relancez plus tard")
        if not compte and a.esi is None:
            sources["esi"] = "non mesuré : compte NASA Earthdata absent (voir README)"
    if entrees["secheresse_sol"] is None and not a.demo and a.smap is None:
        m2 = secheresse_merra2(meteo, debut, fin)
        if m2 is not None:
            entrees["secheresse_sol"] = m2["secheresse"]
            sources["sol_sec"] = f"{m2['source']} : percentile {m2['percentile']}"
    return entrees, sources, terrain


def _confiance(a, meteo, et0, sol, rot):
    """Étape 7 du document : rejoue le seau (sans irrigation) avec une rotation et compare
    pluie, ET0 et humidité à ERA5. Renvoie None si ERA5 ne répond pas."""
    from .bilan import simuler
    from .era5 import telecharger_era5
    from .validation import comparer, confiance
    print("6/6 Contrôle avec une source indépendante (ERA5)…")
    try:
        era5 = telecharger_era5(a.lat, a.lon, a.debut, a.fin, utiliser_cache=not a.sans_cache)
    except ErreurDonnees as e:
        print(f"  ERA5 indisponible ({e}) : confiance non évaluée")
        return None
    cal = construire_calendrier(rot, meteo.dates, a.debut, 0, (meteo.tmax + meteo.tmin) / 2)
    r = simuler(meteo, et0, sol, cal, rot.bonne_condition_hydro, irrigue=False)
    res = comparer(meteo, et0, era5, (r.stock_haut + r.stock_bas) / sol.taw_total, a.debut, a.fin)
    return dict(confiance(res), rotation_rejouee=rot.nom, **res)


def commande_evaluer(a):
    rotations = [lire_rotation(f) for f in _fichiers(a.rotations)]
    debut_meteo = a.debut - 1                         # un an pour remplir le seau
    print(f"\nWater Use v{__version__} — {len(rotations)} rotation(s), années {a.debut}-{a.fin}"
          f"{' — ferme IRRIGUÉE' if a.irrigue else ''}")
    t0 = time.time()
    if a.demo:
        from .demo import meteo_demo, sol_demo
        meteo = meteo_demo(a.demo, debut_meteo, a.fin)
        sol = sol_demo()
        print("ATTENTION : mode démo, données synthétiques (aucune vraie base interrogée).")
    else:
        if a.lat is None or a.lon is None:
            raise SystemExit("Donnez --lat et --lon (ou --demo humide|sec pour tester sans réseau).")
        from .meteo import telecharger_power
        from .sol import trouver_sol
        print(f"1/6 Météo NASA POWER ({a.lat}, {a.lon}), {debut_meteo}-{a.fin}…")
        meteo = telecharger_power(a.lat, a.lon, debut_meteo, a.fin, utiliser_cache=not a.sans_cache)
        print("2/6 Sol (SSURGO, sinon SoilGrids)…")
        sol = trouver_sol(a.lat, a.lon, manuel=a.sol_manuel, groupe=a.groupe_hydro,
                          utiliser_cache=not a.sans_cache)
    entrees, sources, terrain = _sources_extra(a, meteo, sol, a.debut, a.fin)
    et0, methode = et0_meteo(meteo)
    conf = (_confiance(a, meteo, et0, sol, rotations[0])
            if not a.demo and not a.base_seulement else None)
    print(f"\nMÉTÉO  {meteo.source} · altitude {meteo.altitude:.0f} m · ET0 : {methode}"
          + (f" · {meteo.jours_bouches} valeurs manquantes bouchées" if meteo.jours_bouches else ""))
    print(f"SOL    {sol.source} · seau {sol.taw_haut:.0f} mm (0-30 cm) + {sol.taw_bas:.0f} mm "
          f"(30-150 cm) · groupe hydrologique {sol.groupe_hydro}"
          + (f" · pente {100 * sol.pente:.1f} %" if sol.pente is not None else ""))
    pr = pression_sur_l_eau(meteo, et0, a.debut, a.fin, **entrees)
    pr["sources"] = sources
    print(f"PRESSION SUR L'EAU {pr['pression']:.2f}  (aridité P/ET0 = {pr['indice_aridite']} : "
          f"{pr['classe']}" + (f" · pluie d'été {pr['variation_pluie_ete_pct']:+.0f} % entre les deux "
                                "moitiés de la période" if "variation_pluie_ete_pct" in pr else "")
          + (f" · non fournies : {', '.join(pr['manquantes'])}" if pr["manquantes"] else "") + ")")
    for nom, src in sources.items():
        print(f"       {nom:<8} {src}")
    resultats = [evaluer_rotation(r, meteo, sol, a.debut, a.fin, a.irrigue, et0) for r in rotations]
    resultats.sort(key=lambda e: -e.note)
    print("\n" + "-" * 104)
    col_manque, col_perte, unite_perte = (("irrig.", "à irriguer", "% besoins") if a.irrigue
                                          else ("manque", "perte an. sèche", "% rendement"))
    print(f"{'Rotation':<38} {'Note':>5}  {'A sobr.':>7} {'B résist.':>9} {'C pluie':>8} "
          f"{'D semis':>8}   {'demande':>8} {col_manque:>7} {col_perte:>15}")
    print(f"{'':<38} {'0-1':>5}  {'':>7} {'':>9} {'gardée':>8} {'':>8}   {'mm/an':>8} "
          f"{'mm/an':>7} {unite_perte:>15}")
    print("-" * 104)
    for e in resultats:
        c = e.chiffres
        manque = c["irrigation_mm_an"] if a.irrigue else c["manque_mm_an"]
        print(f"{e.rotation[:38]:<38} {e.note:>5.2f}  {e.A:>7.2f} {e.B:>9.2f} {e.C:>8.2f} "
              f"{e.D:>8.2f}   {c['demande_mm_an']:>8.0f} {manque:>7.0f} "
              f"{c['perte_rendement_annee_seche_pct']:>15.0f}")
        print(f"{'':<38} {_barre(e.note)}")
    print("-" * 104)
    if a.irrigue:
        print("Ferme irriguée : « irrig. » = irrigation nécessaire ; dernière colonne = part des "
              "besoins à irriguer l'année sèche.")
    for e in resultats:
        for al in e.alertes:
            print(f"⚠ {e.rotation} : {al}")
    if conf is not None:
        if conf["niveau"] == "bonne":
            print(f"\nCONFIANCE bonne : pluie, ET0 et humidité du seau cohérentes avec ERA5 "
                  f"(rotation « {conf['rotation_rejouee']} » rejouée)")
        else:
            print("\nCONFIANCE faible : " + " ; ".join(conf["raisons"]))
            print("   Les notes restent comparables entre elles sur ce champ ; vérifiez la source "
                  "en écart avec une station météo locale.")
    sortie = Path(a.sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    horo = time.strftime("%Y%m%d-%H%M%S")
    lignes = [e.ligne() for e in resultats]
    with open(sortie / f"resultats_{horo}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(lignes[0]))
        w.writeheader()
        w.writerows(lignes)
    (sortie / f"resultats_{horo}.json").write_text(json.dumps(dict(
        lieu=dict(lat=a.lat, lon=a.lon, demo=a.demo), annees=[a.debut, a.fin], irrigue=a.irrigue,
        meteo=dict(source=meteo.source, altitude=meteo.altitude, et0=methode),
        sol=dict(source=sol.source, taw_haut_mm=sol.taw_haut, taw_bas_mm=sol.taw_bas,
                 groupe_hydro=sol.groupe_hydro, details=sol.details),
        terrain=(dict(source=terrain.source, altitude_m=terrain.altitude, pente=terrain.pente,
                      details=terrain.details) if terrain is not None else
                 dict(pente=sol.pente, source=sources.get("pente", "non utilisée"))),
        pression=pr, confiance=conf, rotations=lignes,
        alertes={e.rotation: e.alertes for e in resultats if e.alertes}),
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nRésultats enregistrés dans {sortie}/resultats_{horo}.csv et .json "
          f"({time.time() - t0:.1f} s)\n")


def commande_connexions(a):
    """Interroge chaque vraie base avec une petite requête et affiche ce qu'elle répond."""
    from . import earthdata
    from .era5 import telecharger_era5
    from .meteo import telecharger_power
    from .nappes import RAYON_KM, nappes_usgs
    from .sol import sol_soilgrids, sol_ssurgo
    from .terrain import terrain_srtm
    ok = True
    print(f"\nTest des connexions au point ({a.lat}, {a.lon}), sans cache :\n")
    try:
        m = telecharger_power(a.lat, a.lon, 2023, 2023, utiliser_cache=False)
        print(f"  ✔ NASA POWER  : {len(m.dates)} jours en 2023, pluie {m.pluie.sum():.0f} mm, "
              f"T max moyenne {m.tmax.mean():.1f} °C, altitude {m.altitude:.0f} m")
        if m.humidite_racines is not None:
            print(f"  ✔ MERRA-2     : humidité racinaire moyenne {float(np.nanmean(m.humidite_racines)):.2f} "
                  "(0 = sec, 1 = saturé), servie par NASA POWER")
    except ErreurDonnees as e:
        ok = False
        print(f"  ✘ NASA POWER  : {e}")
    try:
        s = sol_ssurgo(a.lat, a.lon, utiliser_cache=False)
        if s is None:
            print("  – SSURGO      : répond, mais aucune donnée ici (normal hors États-Unis)")
        else:
            print(f"  ✔ SSURGO      : « {s.details.get('unite')} », seau {s.taw_total:.0f} mm "
                  f"sur 150 cm, groupe {s.groupe_hydro}")
    except ErreurDonnees as e:
        print(f"  ✘ SSURGO      : {e}")
    try:
        s = sol_soilgrids(a.lat, a.lon, utiliser_cache=False)
        print(f"  ✔ SoilGrids   : texture 0-30 cm « {s.details['texture_0_30cm']} », seau "
              f"{s.taw_total:.0f} mm sur 150 cm, groupe estimé {s.groupe_hydro}")
    except ErreurDonnees as e:
        print(f"  ✘ SoilGrids   : {e}")
    try:
        t = terrain_srtm(a.lat, a.lon, utiliser_cache=False)
        print(f"  ✔ SRTM        : altitude {t.altitude:.0f} m, pente {100 * t.pente:.1f} % "
              f"(dénivelé {t.details['denivele_m']:.0f} m sur 360 m)")
    except ErreurDonnees as e:
        print(f"  ✘ SRTM        : {e}")
    try:
        n = nappes_usgs(a.lat, a.lon, 2005, 2024, utiliser_cache=False)
        if n is None:
            print(f"  – USGS nappes : aucun puits suivi en continu à moins de {RAYON_KM:.0f} km "
                  "(normal hors États-Unis)")
        else:
            print(f"  ✔ USGS nappes : {len(n['puits'])} puits, nappes au percentile {n['percentile']} "
                  f"(le plus proche à {n['puits'][0]['distance_km']} km)")
    except ErreurDonnees as e:
        print(f"  ✘ USGS nappes : {e}")
    try:
        e5 = telecharger_era5(a.lat, a.lon, 2023, 2023, utiliser_cache=False)
        print(f"  ✔ ERA5        : pluie 2023 {np.nansum(e5.pluie):.0f} mm, ET0 {np.nansum(e5.et0):.0f} mm "
              "(Open-Meteo)")
    except ErreurDonnees as e:
        print(f"  ✘ ERA5        : {e}")
    if earthdata.identifiants() is None:
        print("  – Earthdata   : pas de compte configuré : SMAP et ECOSTRESS ne seront pas lus "
              "(MERRA-2 prend le relais pour le sol ; voir README)")
    else:
        try:
            earthdata.jeton()
            print("  ✔ Earthdata   : connexion AppEEARS acceptée (SMAP et ECOSTRESS disponibles)")
        except ErreurDonnees as e:
            print(f"  ✘ Earthdata   : {e}")
    print("\n" + ("Météo accessible : l'algorithme peut tourner." if ok else
                  "NASA POWER inaccessible : vérifiez votre connexion internet."))


def commande_valider(a):
    """Compare la pluie, l'ET0 et l'humidité du seau avec ERA5 (source indépendante)."""
    from .bilan import simuler
    from .era5 import telecharger_era5
    from .meteo import telecharger_power
    from .sol import trouver_sol
    from .terrain import terrain_srtm
    from .validation import comparer
    rot = lire_rotation(_fichiers([a.rotation])[0])
    cache = not a.sans_cache
    print(f"\nValidation au point ({a.lat}, {a.lon}), {a.debut}-{a.fin}, rotation « {rot.nom} »")
    print("1/3 Météo NASA POWER…")
    meteo = telecharger_power(a.lat, a.lon, a.debut - 1, a.fin, utiliser_cache=cache)
    print("2/3 Sol et relief…")
    sol = trouver_sol(a.lat, a.lon, manuel=a.sol_manuel, groupe=a.groupe_hydro, utiliser_cache=cache)
    try:
        sol.pente = terrain_srtm(a.lat, a.lon, cache).pente
    except ErreurDonnees as e:
        print(f"  SRTM indisponible ({e}) : pente non utilisée")
    print("3/3 ERA5 (Open-Meteo)…")
    era5 = telecharger_era5(a.lat, a.lon, a.debut, a.fin, utiliser_cache=cache)
    et0, _ = et0_meteo(meteo)
    cal = construire_calendrier(rot, meteo.dates, a.debut, 0, (meteo.tmax + meteo.tmin) / 2)
    r = simuler(meteo, et0, sol, cal, rot.bonne_condition_hydro)
    remplissage = (r.stock_haut + r.stock_bas) / sol.taw_total
    res = comparer(meteo, et0, era5, remplissage, a.debut, a.fin)
    p, e, h = res["pluie"], res["et0"], res["humidite"]
    print(f"\n{'':<26} {'NASA POWER / calcul':>20} {'ERA5':>8} {'écart':>8} {'r annuel':>9}")
    print(f"{'Pluie (mm/an)':<26} {p['power_mm_an']:>20.0f} {p['era5_mm_an']:>8.0f} "
          f"{p['ecart_pct']:>+7.0f}% {_ou_tiret(p['r_annuel']):>9}")
    print(f"{'ET0 (mm/an)':<26} {e['calculee_mm_an']:>20.0f} {e['era5_mm_an']:>8.0f} "
          f"{e['ecart_pct']:>+7.0f}% {_ou_tiret(e['r_annuel']):>9}")
    print(f"\nHumidité en saison de culture ({h['n_jours']} jours) : seau simulé vs ERA5 0-100 cm")
    print(f"  corrélation brute {_ou_tiret(h['r_seau_era5'])} · corrélation des anomalies "
          f"{_ou_tiret(h['r_anomalies_seau_era5'])}"
          + (f" · repère MERRA-2 vs ERA5 {_ou_tiret(h['r_anomalies_merra2_era5'])}"
             if "r_anomalies_merra2_era5" in h else ""))
    print()
    for v in res["verdicts"]:
        print(v)
    sortie = Path(a.sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    f = sortie / f"validation_{time.strftime('%Y%m%d-%H%M%S')}.json"
    f.write_text(json.dumps(dict(lieu=dict(lat=a.lat, lon=a.lon), annees=[a.debut, a.fin],
                                 rotation=rot.nom, **res), ensure_ascii=False, indent=2),
                 encoding="utf-8")
    print(f"\nDétails enregistrés dans {f}\n")


def _ou_tiret(x):
    return "—" if x is None else f"{x:.2f}"


def commande_cultures(_a):
    print(f"\n{'code':<16} {'nom':<22} {'Kc pic':>6} {'Ky':>5} {'racines':>8}  type")
    for c in CULTURES.values():
        ky = f"{c.ky:.2f}" if c.ky is not None else "  —"
        typ = ("couvert" if not c.vente else "vendue") + (", hiver" if c.hiver else "") + \
              (", pérenne" if c.perenne else "")
        print(f"{c.code:<16} {c.nom:<22} {c.kc_mid:>6.2f} {ky:>5} {c.racines_max:>7.1f}m  {typ}")
    print("\nProvenance de chaque valeur : water_use/cultures.py (champ sources).\n")


def main(argv=None):
    for flux in (sys.stdout, sys.stderr):          # accents et symboles sous Windows
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    p = argparse.ArgumentParser(prog="python -m water_use",
                                description="Field Shift — note eau des rotations")
    sous = p.add_subparsers(dest="commande", required=True)
    e = sous.add_parser("evaluer", help="note eau d'une ou plusieurs rotations")
    e.add_argument("--lat", type=float)
    e.add_argument("--lon", type=float)
    e.add_argument("--rotations", nargs="+", required=True, help="fichiers JSON (motifs acceptés)")
    e.add_argument("--debut", type=int, default=2005)
    e.add_argument("--fin", type=int, default=2024)
    e.add_argument("--irrigue", action="store_true", help="la ferme irrigue")
    e.add_argument("--sol-manuel", type=_sol_manuel, help="sable,argile,mo en %%, ex. 40,20,3")
    e.add_argument("--groupe-hydro", choices=list("ABCD"), help="impose le groupe hydrologique")
    e.add_argument("--nappes-percentile", "--grace-percentile", type=float,
                   help="impose le percentile des nappes (0-100) ; sinon puits USGS")
    e.add_argument("--esi", type=float, help="impose l'anomalie ESI (négatif = stress) ; "
                                               "sinon ECOSTRESS avec un compte Earthdata")
    e.add_argument("--smap", type=float, help="impose la sécheresse du sol entre 0 et 1 ; "
                                                "sinon SMAP (Earthdata) ou MERRA-2")
    e.add_argument("--pente", type=float, help="impose la pente en %% ; sinon SRTM")
    e.add_argument("--base-seulement", action="store_true",
                   help="n'interroge que NASA POWER et le sol (ni SRTM, ni USGS, ni SMAP, ni ECOSTRESS)")
    e.add_argument("--attente-earthdata", type=float, default=5,
                   help="minutes d'attente des tâches AppEEARS (SMAP, ECOSTRESS), défaut 5")
    e.add_argument("--demo", choices=["humide", "sec"], help="données synthétiques, sans réseau")
    e.add_argument("--sans-cache", action="store_true", help="ignore les données déjà téléchargées")
    e.add_argument("--sortie", default="resultats")
    e.set_defaults(f=commande_evaluer)
    c = sous.add_parser("connexions", help="teste l'accès aux vraies bases")
    c.add_argument("--lat", type=float, required=True)
    c.add_argument("--lon", type=float, required=True)
    c.set_defaults(f=commande_connexions)
    v = sous.add_parser("valider", help="compare pluie, ET0 et humidité du seau avec ERA5")
    v.add_argument("--lat", type=float, required=True)
    v.add_argument("--lon", type=float, required=True)
    v.add_argument("--debut", type=int, default=2005)
    v.add_argument("--fin", type=int, default=2024)
    v.add_argument("--rotation", default="exemples/mais_soya.json", help="fichier rotation à simuler")
    v.add_argument("--sol-manuel", type=_sol_manuel, help="sable,argile,mo en %%, ex. 40,20,3")
    v.add_argument("--groupe-hydro", choices=list("ABCD"))
    v.add_argument("--sans-cache", action="store_true")
    v.add_argument("--sortie", default="resultats")
    v.set_defaults(f=commande_valider)
    sous.add_parser("cultures", help="liste des cultures").set_defaults(f=commande_cultures)
    a = p.parse_args(argv)
    if getattr(a, "debut", 0) and a.debut > a.fin:
        raise SystemExit("--debut doit être avant --fin")
    try:
        a.f(a)
    except (ErreurDonnees, ValueError) as err:
        print(f"\nErreur : {err}", file=sys.stderr)
        sys.exit(1)
