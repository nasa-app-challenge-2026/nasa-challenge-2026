/** Rebuilds the inputs of a plan fixture (field_shift.py v5.1) for the JavaScript planner. */
import { TimeSettings } from '../../../application/rules/timeSettings.js';
import { SHEETS } from '../../../data/reference/crops.js';
import { CycleClimate, CLIMATE_METHOD } from '../../../backend/algorithm/climate/CycleClimate.js';
import { TwinEvidence } from '../../../backend/algorithm/twins/TwinEvidence.js';
import { ParcelDiagnostic } from '../../../backend/algorithm/diagnostic/ParcelDiagnostic.js';
import { FarmerProfile } from '../../../backend/algorithm/planning/FarmerProfile.js';
import { Parcel } from '../../../backend/algorithm/planning/Parcel.js';
import { cropIdOf, diseaseIdOf, idOf } from './reference.js';

const EQUIPMENT = { fourragère: 'fourragere' };

export function climateOf(c) {
  return new CycleClimate({
    degreeDaysPerDay: c.dj_jour,
    lastSpringFrost: c.gel_printemps,
    firstFallFrost: c.gel_automne,
    januaryMinimumC: c.tmin_janvier,
    harvestAdvanceMonths: c.decalage_fin,
    summerRainChangePct: c.delta_pluie_ete_pct,
    method: c.source.startsWith('tendance') ? CLIMATE_METHOD.TREND : CLIMATE_METHOD.MODELS,
    source: c.source,
  });
}

export function dataOf(windows) {
  const cache = new Map();
  return {
    cycleData(first, last) {
      const key = `${first}-${last}`;
      if (!cache.has(key)) {
        const w = windows[key];
        cache.set(key, {
          climate: climateOf(w.climate),
          evidence: new TwinEvidence({
            crops: w.cultures.map(cropIdOf),
            successions: w.precedents.map(([a, b, v]) => [cropIdOf(a), cropIdOf(b), v]),
            sigmaMean: w.sigma_moyen,
          }),
        });
      }
      return cache.get(key);
    },
  };
}

/** The reference reads past crops from the most recent backwards (see delays.test.js). */
function pastOf(p) {
  if (p.recolte_en_place === null) return [];
  const freeYear = 2000 + Math.floor(p.recolte_en_place / 12);
  const sheet = p.culture_en_place ? SHEETS[idOf(p.culture_en_place)] : null;
  let past = [...p.historique];
  if (
    sheet &&
    past.length &&
    !sheet.productionYears &&
    cropIdOf(past[past.length - 1]) === sheet.cropId
  )
    past = past.slice(0, -1);
  return past.reverse().map((name, i) => ({ year: freeYear - 1 - i, cropId: cropIdOf(name) }));
}

export function inputsOf(fx) {
  const m = fx.mesures;
  const measures = {
    slopePct: m.pente_pct,
    heavyRainDays: m.jours_pluie_intense,
    bareSoilDays: m.jours_sol_nu,
    summerStressIndex: m.esi_ete,
    rootZoneDrought: m.smap_secheresse,
    groundwaterTrendCmPerYear: m.grace_tendance_cm_an,
  };
  const irrigated = fx.scenario.irrigation ?? false;
  return {
    time: new TimeSettings({
      cycleYears: fx.scenario.C,
      frequencyMonths: fx.scenario.f,
      horizonYears: fx.scenario.H,
    }),
    farmer: new FarmerProfile({
      ranking: fx.fermier.classement,
      livestock: fx.fermier.betail,
      missingEquipment: fx.fermier.equipement_manquant.map((e) => EQUIPMENT[e] ?? e),
      seeds: fx.reserve.map(cropIdOf),
      reserveMode: fx.scenario.mode ?? 'preferer',
    }),
    data: dataOf(fx.windows),
    today: fx.debut,
    parcels: fx.parcelles.map(
      (p) =>
        new Parcel({
          id: p.nom,
          inPlace: p.culture_en_place ? idOf(p.culture_en_place) : null,
          inPlaceHarvest: p.recolte_en_place,
          past: pastOf(p),
          currentRotation: (p.rotation_commencee ?? []).map(idOf),
          rotationPosition: p.position_actuelle,
          diseases: (p.maladies ?? []).map(diseaseIdOf),
          diagnostic: new ParcelDiagnostic(measures, { irrigated }),
        }),
    ),
  };
}
