/**
 * From the FarmInput v2 of the contract (what the screens send) to the objects of
 * the algorithm: time settings, farmer profile, parcels.
 */
import { TimeSettings } from '../../../application/rules/timeSettings.js';
import { CROPS, SEED_IDS, SHEETS } from '../../../data/reference/crops.js';
import { ParcelDiagnostic } from '../diagnostic/ParcelDiagnostic.js';
import { FarmerProfile, RESERVE_PREFERRED } from '../planning/FarmerProfile.js';
import { Parcel } from '../planning/Parcel.js';
import { MonthTime } from '../time/MonthTime.js';

/** A harvest given to the month ("2026-10") is placed in the middle of that month. */
const MID_MONTH = 0.5;

/** "2026-10" → absolute month (middle of October 2026). */
export function monthTimeOf(yearMonth) {
  if (!yearMonth) return null;
  const [year, month] = yearMonth.split('-').map(Number);
  return MonthTime.of(year, month - 1 + MID_MONTH);
}

/** "2026-11-13" → absolute month. */
export function dayTimeOf(isoDate) {
  const [year, month, day] = isoDate.split('-').map(Number);
  const days = new Date(Date.UTC(year, month, 0)).getUTCDate();
  return MonthTime.of(year, month - 1 + (day - 1) / days);
}

const knownCrop = (id) => Boolean(SHEETS[id] || CROPS[id]);

/**
 * @param {object} input FarmInput v2
 * @param {(section: object) => object} measuresOf satellite measures of a section (step 8)
 */
export function readFarmInput(input, measuresOf) {
  const { farm } = input;
  const time = new TimeSettings(farm.time);
  const farmer = new FarmerProfile({
    ranking: farm.priorities ?? [],
    livestock: Boolean(farm.livestock),
    missingEquipment: farm.missingEquipment ?? [],
    seeds: farm.seeds?.crops ?? SEED_IDS,
    reserveMode: farm.seeds?.mode ?? RESERVE_PREFERRED,
  });
  const parcels = input.sections.map(
    (s) =>
      new Parcel({
        id: s.id,
        inPlace: knownCrop(s.currentCrop) ? s.currentCrop : null,
        inPlaceHarvest: s.currentCrop ? monthTimeOf(s.currentHarvest) : null,
        past: (s.history ?? [])
          .filter((h) => knownCrop(h.crop))
          .map((h) => ({ year: h.year, cropId: h.crop })),
        currentRotation: (s.currentRotation ?? []).filter((id) => SHEETS[id]),
        rotationPosition: s.rotationPosition ?? 0,
        diseases: s.diseases ?? [],
        diagnostic: new ParcelDiagnostic(measuresOf(s), { irrigated: Boolean(s.irrigated) }),
      }),
  );
  return { time, farmer, parcels };
}
