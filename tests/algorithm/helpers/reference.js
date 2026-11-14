/**
 * Helpers to read the golden fixtures exported from field_shift.py v5.1
 * (tests/algorithm/fixtures/export_reference.py) and to rebuild their inputs.
 */
import { readFileSync } from 'node:fs';
import { CROPS, CROP_SHEETS } from '../../../data/reference/crops.js';
import { SOIL_DISEASES } from '../../../data/reference/returnDelays.js';
import { DailyWeather } from '../../../backend/algorithm/weather/DailyWeather.js';

export const fixture = (name) =>
  JSON.parse(readFileSync(new URL(`../fixtures/${name}`, import.meta.url), 'utf8'));

/** "Infinity" (JSON-safe) → Infinity. */
export const num = (v) => (v === 'Infinity' ? Infinity : v === '-Infinity' ? -Infinity : v);

/** Python names → ids of this repo. */
const plain = (s) => s.replace(/’/g, "'");
const NAME_TO_ID = new Map([
  ...CROP_SHEETS.map((s) => [plain(s.name), s.id]),
  ...Object.values(CROPS).map((c) => [plain(c.name), c.id]),
  ['Soya 2e culture', 'soya-2e'],
]);
// A name that is both a sheet and a crop (Maïs, Soya…) maps to the same id.
export const idOf = (name) => {
  const id = NAME_TO_ID.get(plain(name));
  if (!id) throw new Error(`Nom inconnu : ${name}`);
  return id;
};
/** A crop (not a sheet): Luzerne ×2 is a sheet, Luzerne the crop. */
export const cropIdOf = (name) => {
  const id = idOf(name);
  return CROP_SHEETS.find((s) => s.id === id)?.cropId ?? id;
};
const DISEASE_BY_NAME = new Map(
  Object.entries(SOIL_DISEASES).map(([id, d]) => [plain(d.name), id]),
);
export const diseaseIdOf = (name) => DISEASE_BY_NAME.get(plain(name));

// --- Deterministic synthetic weather (same numbers as export_reference.py) --------------
const MODULUS = 2147483647;
const MULTIPLIER = 48271;
const MONTHLY_MEAN_C = [-10, -8, -2, 6.5, 13.5, 19, 21.5, 20.5, 15.5, 8.5, 2, -6];

class ParkMiller {
  constructor(seed) {
    this.state = seed % MODULUS || 1;
  }
  next() {
    this.state = (this.state * MULTIPLIER) % MODULUS;
    return this.state / MODULUS;
  }
}

export function syntheticWeather(firstYear, lastYear, seed, trend = 0.04, offset = 0.0) {
  const rng = new ParkMiller(seed);
  const cal = DailyWeather.calendar(firstYear, lastYear);
  const anomaly = {};
  for (let y = firstYear; y <= lastYear; y++) anomaly[y] = (rng.next() - 0.5) * 2.4;
  const tmax = [];
  const tmin = [];
  const rain = [];
  for (let i = 0; i < cal.year.length; i++) {
    const year = cal.year[i];
    const mean =
      MONTHLY_MEAN_C[cal.month[i] - 1] +
      offset +
      trend * (year - 2014.5) +
      anomaly[year] +
      (rng.next() - 0.5) * 12.0;
    tmax.push(mean + 6.0);
    tmin.push(mean - 6.0);
    const wet = rng.next();
    const amount = rng.next();
    rain.push(wet < 0.6 ? 0.0 : amount * 25.0);
  }
  return new DailyWeather({ ...cal, tmax, tmin, rain });
}

export function syntheticModel(name, { seed, warming_factor: factor, rain_ratio: ratio }) {
  const base = syntheticWeather(1985, 2014, seed);
  const bias = 1.0;
  const historical = base.shiftedBy(bias);
  return {
    name,
    simulate(first, last) {
      const delta = factor * 0.04 * ((first + last) / 2 - 1999.5);
      return {
        historical,
        future: historical.with({
          tmax: historical.tmax.map((v) => v + delta),
          tmin: historical.tmin.map((v) => v + delta),
          rain: historical.rain.map((v) => v * ratio),
        }),
      };
    },
  };
}

/** Relative closeness for numbers computed with different summation orders. */
export function close(actual, expected, relative = 1e-9, absolute = 1e-9) {
  if (expected === null || expected === undefined) return actual === null || actual === undefined;
  if (!Number.isFinite(expected)) return actual === expected;
  return Math.abs(actual - expected) <= Math.max(absolute, relative * Math.abs(expected));
}
