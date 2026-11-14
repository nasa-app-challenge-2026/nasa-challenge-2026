"""Export golden fixtures from the reference implementation field_shift.py (v5.1).

The JavaScript port (backend/algorithm/) is tested against these files: same inputs,
same outputs (tests/algorithm/reference.test.js).

    python export_reference.py <path/to/field_shift.py> <output_dir>

Needs numpy, scipy, xarray and pandas (the dependencies of field_shift.py).

One deliberate change is applied to the reference before exporting: the maturity of a
summer crop is computed from the month of the year it is sown (`semis % 12`) instead of
being cached from the first absolute sowing date seen with that month. The JavaScript
port does the same, so its results do not depend on the order of the calls. The script
checks that this change leaves the demo plans unchanged (same chains, same decisions).
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

# ---------------------------------------------------------------------------------------------
# Loading the reference
# ---------------------------------------------------------------------------------------------


def load_reference(path):
    spec = importlib.util.spec_from_file_location("field_shift", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["field_shift"] = module
    spec.loader.exec_module(module)
    return module


def canonical_maturity(fs):
    """Maturity computed from the month of the year the crop is sown (see the docstring)."""

    def maturite(self, semis, dj, pas=0.05):
        cache = self.__dict__.setdefault("_cache_canonique", {})
        debut = semis % 12
        cle = (debut, dj)
        if cle not in cache:
            total, t, offset = 0.0, debut, None
            while total < dj:
                total += self.dj_jour[int(math.floor(t)) % 12] * 30.4 * pas
                t += pas
                if t - debut > 12:
                    break
            else:
                offset = t - debut
            cache[cle] = offset
        offset = cache[cle]
        return None if offset is None else semis + offset

    return maturite


# ---------------------------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------------------------


def clean(value):
    """JSON-safe copy: tuples -> lists, numpy -> Python, inf -> "Infinity", nan -> None."""
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        items = sorted(value) if isinstance(value, (set, frozenset)) else value
        return [clean(v) for v in items]
    if isinstance(value, (np.floating, float)):
        v = float(value)
        if math.isnan(v):
            return None
        if math.isinf(v):
            return "Infinity" if v > 0 else "-Infinity"
        return v
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, np.ndarray):
        return clean(value.tolist())
    return value


def write(out_dir, name, data):
    path = Path(out_dir) / name
    path.write_text(json.dumps(clean(data), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"  {path.name}  ({path.stat().st_size // 1024} KB)")


# ---------------------------------------------------------------------------------------------
# Deterministic synthetic weather, reproduced exactly by tests/algorithm/syntheticWeather.js
# ---------------------------------------------------------------------------------------------
MODULUS = 2147483647
MULTIPLIER = 48271


class ParkMiller:
    """Minimal standard generator: integer arithmetic, identical in Python and JavaScript."""

    def __init__(self, seed):
        self.state = seed % MODULUS or 1

    def next(self):
        self.state = (self.state * MULTIPLIER) % MODULUS
        return self.state / MODULUS


MONTHLY_MEAN_C = [-10, -8, -2, 6.5, 13.5, 19, 21.5, 20.5, 15.5, 8.5, 2, -6]


def synthetic_weather(first_year, last_year, seed, trend_c_per_year=0.04, offset_c=0.0):
    """Daily tmax / tmin (°C) and rain (mm/day). Every number comes from ParkMiller."""
    rng = ParkMiller(seed)
    time = pd.date_range(f"{first_year}-01-01", f"{last_year}-12-31", freq="D")
    tmax, tmin, rain = [], [], []
    anomaly = {}
    for year in range(first_year, last_year + 1):
        anomaly[year] = (rng.next() - 0.5) * 2.4
    for day in time:
        mean = (MONTHLY_MEAN_C[day.month - 1] + offset_c
                + trend_c_per_year * (day.year - 2014.5) + anomaly[day.year]
                + (rng.next() - 0.5) * 12.0)
        tmax.append(mean + 6.0)
        tmin.append(mean - 6.0)
        wet = rng.next()
        amount = rng.next()
        rain.append(0.0 if wet < 0.6 else amount * 25.0)
    return xr.Dataset(dict(tmax=("time", np.array(tmax)), tmin=("time", np.array(tmin)),
                           pluie=("time", np.array(rain))), coords=dict(time=time))


def synthetic_model(seed, warming_factor, rain_ratio, bias_c=1.0):
    """A fictitious climate model built on synthetic weather (same shape as _modele_fictif)."""
    base = synthetic_weather(1985, 2014, seed)

    def model(start, end):
        hist = base.assign(tmax=base.tmax + bias_c, tmin=base.tmin + bias_c)
        delta = warming_factor * 0.04 * ((start + end) / 2 - 1999.5)
        return hist, hist.assign(tmax=hist.tmax + delta, tmin=hist.tmin + delta,
                                 pluie=hist.pluie * rain_ratio)

    return model


# ---------------------------------------------------------------------------------------------
# Climate fixtures (steps 2 and 3)
# ---------------------------------------------------------------------------------------------


def climate_dict(c):
    return dict(dj_jour=list(c.dj_jour), gel_printemps=c.gel_printemps, gel_automne=c.gel_automne,
                tmin_janvier=c.tmin_janvier, decalage_fin=c.decalage_fin, source=c.source,
                delta_pluie_ete_pct=c.delta_pluie_ete_pct)


def export_climate(fs, out_dir):
    weather = synthetic_weather(1985, 2024, seed=20261113)
    table, years = fs.indicateurs_tableau(weather)
    shifted, shift, slope = fs.meteo_prolongee(weather, 2028.5)
    models = {"modèle X": synthetic_model(7, 0.8, 1.05), "modèle Y": synthetic_model(11, 1.3, 0.92)}
    short_targets, short_climate = fs.climat_du_cycle(2027, 2030, weather, 2026, models)
    long_targets, long_climate = fs.climat_du_cycle(2037, 2040, weather, 2026, models)
    obs = weather.sel(time=slice("1985-01-01", "2014-12-31"))
    hist, fut = models["modèle X"](2028, 2047)
    delta = fs.appliquer_delta(obs, hist, fut)
    delta_table, _ = fs.indicateurs_tableau(delta)
    write(out_dir, "climate.json", dict(
        weather=dict(first_year=1985, last_year=2024, seed=20261113),
        models={"modèle X": dict(seed=7, warming_factor=0.8, rain_ratio=1.05),
                "modèle Y": dict(seed=11, warming_factor=1.3, rain_ratio=0.92)},
        yearly_indicators=dict(years=years, table=table),
        extended=dict(target_year=2028.5, shift=shift, slope=slope,
                      first_rows=fs.indicateurs_tableau(shifted)[0][:3]),
        delta_x_2028_2047=dict(table_first_rows=delta_table[:3], table_mean=delta_table.mean(0)),
        cycle_2027_2030=dict(targets={k: v.mean(0) for k, v in short_targets.items()},
                             target_rows={k: v.shape[0] for k, v in short_targets.items()},
                             climate=climate_dict(short_climate)),
        cycle_2037_2040=dict(targets={k: v.mean(0) for k, v in long_targets.items()},
                             target_rows={k: v.shape[0] for k, v in long_targets.items()},
                             climate=climate_dict(long_climate)),
    ))


# ---------------------------------------------------------------------------------------------
# Twin fixtures (step 4) and steps 5 to 8
# ---------------------------------------------------------------------------------------------


def uniform_matrix(rng, shape, scale, offset):
    out = np.empty(shape)
    for index in np.ndindex(*shape):
        out[index] = offset + (rng.next() - 0.5) * scale
    return out


def export_twins(fs, out_dir):
    rng = ParkMiller(424242)
    years, cells, k = 14, 12, 5
    scale = np.array([300.0, 120.0, 30.0, 12.0, 6.0])
    centre = np.array([1500.0, 280.0, 150.0, 10.0, -14.0])
    present = np.empty((years, cells, k))
    for c in range(cells):
        cell_offset = np.array([(c - 6) * 60.0, (c % 3) * 15.0, (c - 6) * 3.0, c * 0.8, (c - 6) * 0.7])
        for y in range(years):
            for i in range(k):
                present[y, c, i] = centre[i] + cell_offset[i] + (rng.next() - 0.5) * scale[i]
    future = np.empty((20, k))
    for y in range(20):
        for i in range(k):
            future[y, i] = centre[i] + np.array([120.0, 5.0, 8.0, 3.0, 1.5])[i] + (rng.next() - 0.5) * scale[i]
    mask = np.array([c != 4 for c in range(cells)])
    sigma = fs.sigma_dissimilarite(future, present)
    idx, sig = fs.meilleurs_jumeaux(future, present, mask, n=5)
    write(out_dir, "twins.json", dict(present=present, future=future, mask=mask, sigma=sigma,
                                      best=dict(n=5, cells=idx, sigma=sig)))


def export_steps_5_to_8(fs, out_dir):
    soils = [
        (dict(argile=30, sable=25, soc=25, ph=6.5), dict(argile=30, sable=25, soc=25, ph=6.5)),
        (dict(argile=30, sable=25, soc=25, ph=6.5), dict(argile=38, sable=13, soc=37.5, ph=7.1)),
        (dict(argile=12, sable=60, soc=10, ph=5.8), dict(argile=35, sable=20, soc=30, ph=7.4)),
    ]
    sequences = [
        ["Maïs", "Soya", "Maïs", "Soya", "Maïs", "Soya", "Maïs", "Soya"],
        ["Soya", "Maïs", "Soya", "Maïs", "Soya", "Maïs", "Soya", "Maïs"],
        ["Maïs", "Maïs", "Maïs", "Maïs"],
        ["Luzerne", "Luzerne", "Luzerne", "Maïs", "Soya", "Luzerne", "Luzerne", "Luzerne"],
        ["Maïs", "Soya", "Blé d'automne", "Maïs", "Soya", "Blé d'automne", "Maïs", "Soya"],
        ["Maïs", "Soya", "Orge", "Canola", "Blé d'automne", "Sarrasin", "Foin", "Maïs"],
        ["Blé d'automne", "Soya", "Maïs", "Blé d'automne", "Soya", "Orge", "Blé d'automne", "Soya"],
        ["Maïs", "Soya", "Maïs", "Orge", "Maïs", "Soya", "Maïs", "Soya"],
    ]
    ndvi = [(0.9, 0.85, 0.7, 0.6), (0.8, 0.85, 0.7, 0.6), (0.7, 0.85, 0.7, 0.6),
            (0.65, 0.85, 0.7, 0.6), (0.5, 0.85, 0.7, 0.6), (0.2, 0.85, 0.7, 0.6),
            (0.6, 0.85, 0.7, 0.7)]
    rng = ParkMiller(777)
    rows = []
    for culture, precedent, count, base in [("Maïs", "Maïs", 25, 0.40), ("Maïs", "Soya", 30, 0.25),
                                             ("Maïs", "Orge", 12, 0.30), ("Soya", "Soya", 22, 0.5),
                                             ("Soya", "Maïs", 24, 0.35)]:
        for _ in range(count):
            rows.append(dict(culture=culture, precedent=precedent, ecart=base + (rng.next() - 0.5) * 0.2))
    df = pd.DataFrame(rows)
    pairs = [("Soya", "Maïs"), ("Orge", "Maïs"), ("Maïs", "Soya"), ("Blé d'automne", "Maïs")]
    fields = [dict(sequence=s, superficie=10 + 3 * i, sigma=0.4 * i) for i, s in enumerate(sequences)]
    jumeaux, top = fs.construire_jumeaux(fields, df)
    measures = [
        dict(pente_pct=6, jours_pluie_intense=6, jours_sol_nu=120, esi_ete=0.6, smap_secheresse=0.4,
             grace_tendance_cm_an=-1),
        dict(pente_pct=12, jours_pluie_intense=10, jours_sol_nu=200, esi_ete=0.3, smap_secheresse=0.9,
             grace_tendance_cm_an=-3),
        dict(pente_pct=0.5, jours_pluie_intense=1, jours_sol_nu=20, esi_ete=0.95, smap_secheresse=0.0,
             grace_tendance_cm_an=1),
    ]
    diagnostics = [dict(measures=m, rain=r, irrigation=irr,
                        result=fs.diagnostic_parcelle(m, r, irr))
                   for m in measures for r in (0.0, -4.0, -25.0, 10.0) for irr in (False, True)]
    write(out_dir, "steps-5-to-8.json", dict(
        soil=[dict(a=a, b=b, distance=fs.distance_sol(a, b)) for a, b in soils],
        canonical=[dict(sequence=s, result=fs.canonique(s)) for s in sequences],
        ndvi_gap=[dict(args=list(a), result=fs.ecart_ndvi(*a)) for a in ndvi],
        precrop=dict(rows=rows, results=[dict(a=a, b=b, value=fs.valeur_precedent(df, a, b))
                                         for a, b in pairs]),
        twin_evidence=dict(fields=fields, cultures=sorted(jumeaux.cultures),
                           precedents=[[a, b, v] for (a, b), v in sorted(jumeaux.precedents.items())],
                           sigma_moyen=jumeaux.sigma_moyen, top=[[r, w] for r, w in top]),
        diagnostics=diagnostics,
    ))


# ---------------------------------------------------------------------------------------------
# Return delays (part B) and weights (step 1)
# ---------------------------------------------------------------------------------------------


def occ_list(occs):
    return [[o.culture, o.debut, o.fin, o.source] for o in occs]


def export_delays(fs, out_dir):
    Occ = fs.Occ
    cases = [
        dict(name="maïs-soya", C=2, occs=[Occ("Maïs", 2027, 2027), Occ("Soya", 2028, 2028)],
             historique=None, maladies=[]),
        dict(name="soya-soya-historique", C=4,
             occs=[Occ("Soya", 2027, 2027), Occ("Maïs", 2028, 2028), Occ("Soya", 2029, 2029),
                   Occ("Maïs", 2030, 2030)],
             historique=[Occ("Maïs", 2024, 2024), Occ("Soya", 2025, 2025), Occ("Maïs", 2026, 2026)],
             maladies=[]),
        dict(name="fabacées", C=4,
             occs=[Occ("Maïs", 2028, 2028), Occ("Soya", 2029, 2029), Occ("Luzerne", 2030, 2031)],
             historique=[Occ("Luzerne", 2025, 2027)], maladies=[]),
        dict(name="hernie-canola", C=5,
             occs=[Occ("Canola", 2027, 2027), Occ("Blé d'automne", 2028, 2028), Occ("Orge", 2029, 2029),
                   Occ("Soya", 2030, 2030), Occ("Maïs", 2031, 2031)],
             historique=None, maladies=["hernie des crucifères"]),
        dict(name="vigilance-moisissure", C=4,
             occs=[Occ("Soya", 2027, 2027), Occ("Maïs", 2028, 2028), Occ("Canola", 2029, 2029),
                   Occ("Blé d'automne", 2030, 2030)],
             historique=[Occ("Pomme de terre", 2025, 2025)], maladies=[]),
        dict(name="double-culture", C=3,
             occs=[Occ("Blé d'automne", 2028, 2028), Occ("Soya", 2028, 2028), Occ("Maïs", 2029, 2029),
                   Occ("Orge", 2030, 2030)],
             historique=None, maladies=[]),
    ]
    out = []
    for case in cases:
        verdict = fs.verifier(case["occs"], case["C"], case["historique"], case["maladies"])
        partial = fs.verifier(case["occs"][:2], case["C"], case["historique"], case["maladies"],
                              fermer=False, complet=False)
        out.append(dict(name=case["name"], C=case["C"], occs=occ_list(case["occs"]),
                        historique=None if case["historique"] is None else occ_list(case["historique"]),
                        maladies=case["maladies"], ok=verdict.ok, violations=verdict.violations,
                        vigilances=verdict.vigilances, note_ravageurs=verdict.note_ravageurs,
                        partial=dict(ok=partial.ok, violations=partial.violations),
                        partial_note=fs.note_ravageurs(case["occs"][:2], case["C"], case["historique"],
                                                       case["maladies"], fermer=False)))
    impossible = []
    for C in (2, 3, 4, 5, 6):
        for maladies in ([], ["hernie des crucifères"], ["moisissure blanche"]):
            res = fs.impossibles(C, ["Maïs", "Soya", "Canola", "Luzerne ×2", "Luzerne ×3", "Foin ×3", "Pois"],
                                 {"Luzerne ×2": 2, "Luzerne ×3": 3, "Foin ×3": 3}, maladies)
            impossible.append(dict(C=C, maladies=maladies, result=res))
    history = []
    for parcelle in [
        fs.Parcelle("P1", 20, "Maïs", fs.mois(2026, 9.6), ["Maïs", "Soya"], ["Maïs", "Soya"], 0),
        fs.Parcelle("P2", 12, "Luzerne ×3", fs.mois(2027, 8.75), ["Luzerne", "Luzerne"],
                    ["Luzerne ×3", "Maïs", "Soya"], 0),
        fs.Parcelle("P3", 5, "Soya", fs.mois(2026, 8.5), ["Maïs", "Maïs", "Soya"], None, 0),
        fs.Parcelle("P4", 5, "Blé d'automne", fs.mois(2026, 6.65), ["Pomme de terre", "Maïs", "Maïs"],
                    None, 0),
    ]:
        libre = parcelle.recolte_en_place
        history.append(dict(nom=parcelle.nom, culture_en_place=parcelle.culture_en_place, libre=libre,
                            historique=parcelle.historique,
                            result=occ_list(fs.historique_parcelle(parcelle, libre))))
    delays = {name: {k: v for k, v in d.items() if k in ("famille", "ff", "sare", "minimum", "recommande",
                                                           "maladies", "perenne")}
              for name, d in fs.DELAIS.items()}
    weights = []
    for classement in (["erosion", "rendement", "azote", "reserve", "matiere_org", "marche"],
                       ["rendement", "eau", "fourrage", "azote", "erosion"],
                       list(fs.CRITERES), ["marche"]):
        base = fs.poids_depuis_classement(classement)
        adjusted = fs._poids_ajustes(classement, dict(risque_erosion=0.76, risque_eau=0.41), False)
        weights.append(dict(classement=classement, base=base, adjusted=adjusted))
    write(out_dir, "delays.json", dict(
        cases=out, impossible=impossible, history=history, delays=delays, weights=weights,
        history_depth=[dict(cultures=c, maladies=m, depth=fs.profondeur_historique(c, m))
                       for c, m in [(["Maïs", "Soya"], []), (list(fs.TABLE), []),
                                    (["Maïs", "Canola"], ["hernie des crucifères"])]],
    ))


# ---------------------------------------------------------------------------------------------
# Plans (steps 9b and 10)
# ---------------------------------------------------------------------------------------------


def chain_list(chaine):
    return [list(e) for e in chaine] if chaine else None


def run_plans(fs, scenario):
    """Plan every parcel of a scenario; records what donnees_cycle returned for each window."""
    windows = {}

    def donnees_cycle(a0, a1):
        climat, jumeaux = fs.donnees_cycle(a0, a1)
        windows[f"{a0}-{a1}"] = dict(climate=climate_dict(climat), cultures=sorted(jumeaux.cultures),
                                     precedents=[[a, b, v] for (a, b), v in jumeaux.precedents.items()],
                                     sigma_moyen=jumeaux.sigma_moyen)
        return climat, jumeaux

    fermier = dict(classement=scenario.get("classement", fs.FERMIER["classement"]),
                   betail=scenario.get("betail", False),
                   equipement_manquant=scenario.get("equipement_manquant", []))
    reserve = set(scenario.get("reserve", fs.RESERVE))
    irrigation = scenario.get("irrigation", False)
    diag = fs.diagnostic_du_cycle(fs.MESURES_PARCELLE, irrigation=irrigation)
    reglages = fs.Reglages(duree_cycle_ans=scenario["C"], frequence_mois=scenario["f"],
                           horizon_ans=scenario["H"], debut=fs.mois(2026, 10.4),
                           mode_reserve=scenario.get("mode", "preferer"))
    parcels = []
    for p in scenario.get("parcelles", fs.PARCELLES):
        try:
            plan = fs.planifier_parcelle(p, reglages, donnees_cycle, fermier, diag, reserve)
            cycles = []
            for c in plan:
                ctx = c["ctx"]
                cycles.append(dict(
                    cycle=c["cycle"], annees=c["annees"], decision=c["decision"],
                    chaine=chain_list(c["chaine"]), note=c["note"], criteres=c["criteres"],
                    lacunes=c["details"]["lacunes"], achats=c["details"]["achats"],
                    intercalaires=[[n, s, r] for n, s, r, *_ in c["details"]["intercalaires"]],
                    vigilances=c["details"]["vigilances"], diagnostic=c["diagnostic"],
                    reference=chain_list(c["reference"]), note_reference=c["note_reference"],
                    alertes_reference=c["alertes_reference"], impossibles=c["impossibles"],
                    alternatives=[[[n for n, *_ in ch], note] for ch, note in c["alternatives"]],
                    robustesse=c.get("robustesse"), non_faisable_plus_tard=c.get("non_faisable_plus_tard"),
                    texte=fs.texte_chaine(c["chaine"], c["details"]["intercalaires"]),
                    ctx=dict(p0=ctx["p0"], recolte_entree=ctx["recolte_entree"],
                             vente_entree=ctx["vente_entree"], culture_entree=ctx["culture_entree"],
                             candidates=ctx["candidates"], poids=ctx["poids"],
                             historique_occ=occ_list(ctx["historique_occ"]),
                             couverts_auto=ctx["couverts_auto"])))
            parcels.append(dict(nom=p.nom, cycles=cycles, error=None))
        except RuntimeError as err:
            parcels.append(dict(nom=p.nom, cycles=None, error=str(err)))
    return dict(parcels=parcels, windows=windows)


def parcel_dict(p):
    return dict(nom=p.nom, superficie_ha=p.superficie_ha, culture_en_place=p.culture_en_place,
                recolte_en_place=p.recolte_en_place, historique=p.historique,
                rotation_commencee=p.rotation_commencee, position_actuelle=p.position_actuelle,
                maladies=p.maladies)


def scenarios(fs):
    P = fs.Parcelle
    libre = P("P3", 8, None, None, [], None, 0)
    malade = P("P1", 20, "Maïs", fs.mois(2026, 9.6), ["Maïs", "Soya"], ["Maïs", "Soya"], 0,
               maladies=["pourriture brune de la tige"])
    ble = P("P4", 6, "Blé d'automne", fs.mois(2026, 6.65), ["Maïs", "Soya"],
            ["Blé d'automne", "Maïs", "Soya"], 0)
    return [
        dict(name="demo-4-12-12", C=4, f=12, H=12),
        dict(name="demo-4-6-8", C=4, f=6, H=8),
        dict(name="demo-3-12-9", C=3, f=12, H=9),
        dict(name="demo-5-12-10", C=5, f=12, H=10),
        dict(name="demo-2-12-6", C=2, f=12, H=6),
        dict(name="demo-3-4-3", C=3, f=4, H=3),
        dict(name="variant-uniquement", C=4, f=12, H=8, mode="uniquement",
             reserve=["Soya", "Blé d'automne", "Maïs", "Orge"]),
        dict(name="variant-betail-maladie-irrigation", C=5, f=12, H=10, betail=True, irrigation=True,
             classement=["fourrage", "eau", "rendement", "ravageurs"], parcelles=[malade, ble]),
        dict(name="variant-sans-fourragere-libre", C=3, f=12, H=6, equipement_manquant=["fourragère"],
             parcelles=[libre, ble]),
    ]


def export_plans(fs, out_dir):
    original = fs.ClimatCycle.maturite
    for scenario in scenarios(fs):
        fs.ClimatCycle.maturite = original
        before = run_plans(fs, scenario)
        fs.ClimatCycle.maturite = canonical_maturity(fs)
        after = run_plans(fs, scenario)
        # Harvests may move by one maturity step (0.05 month) and notes by a fraction of a
        # point; the chains and the decisions must stay the same.
        same = all(
            (a["cycles"] is None) == (b["cycles"] is None) and (a["cycles"] is None or all(
                x["decision"] == y["decision"] and [n for n, *_ in x["chaine"]] == [n for n, *_ in y["chaine"]]
                and abs(x["note"] - y["note"]) < 0.5
                for x, y in zip(a["cycles"], b["cycles"])))
            for a, b in zip(before["parcels"], after["parcels"]))
        print(f"  {scenario['name']}: same chains and decisions with the canonical maturity -> {same}")
        parcelles = scenario.get("parcelles", fs.PARCELLES)
        write(out_dir, f"plan-{scenario['name']}.json", dict(
            scenario={k: v for k, v in scenario.items() if k != "parcelles"},
            parcelles=[parcel_dict(p) for p in parcelles],
            fermier=dict(classement=scenario.get("classement", fs.FERMIER["classement"]),
                         betail=scenario.get("betail", False),
                         equipement_manquant=scenario.get("equipement_manquant", [])),
            reserve=sorted(scenario.get("reserve", fs.RESERVE)),
            mesures=fs.MESURES_PARCELLE, debut=fs.mois(2026, 10.4), annee_actuelle=fs.ANNEE_ACTUELLE,
            canonical_matches_original=same, **after))
    fs.ClimatCycle.maturite = original


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    fs = load_reference(sys.argv[1])
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    print("Fixtures written to", out_dir)
    export_climate(fs, out_dir)
    export_twins(fs, out_dir)
    export_steps_5_to_8(fs, out_dir)
    export_delays(fs, out_dir)
    export_plans(fs, out_dir)


if __name__ == "__main__":
    main()
