/**
 * FICTITIOUS NASA POWER series (1985–2024), used when the real API cannot be
 * reached (offline, tests). Same recipe as field_shift.py (meteo_power_fictive):
 * Montérégie monthly temperatures, a warming trend, a deviation per year, warm and
 * cold spells of a few days, random rain. Reproducible: same seed, same weather.
 */
import { SeededRandom } from '../math/SeededRandom.js';
import { DailyWeather } from '../weather/DailyWeather.js';

export const DEMO_WEATHER_YEARS = { first: 1985, last: 2024 };

/** Fictitious mean monthly temperatures of 2005–2024 in Montérégie (°C). */
const MONTHLY_MEAN_C = [-10, -8, -2, 6.5, 13.5, 19, 21.5, 20.5, 15.5, 8.5, 2, -6];
/** Day of the year in the middle of each month. */
const MID_MONTH_DAY = [15, 46, 74, 105, 135, 166, 196, 227, 258, 288, 319, 349];
const DAYS_PER_YEAR = 365;
const RECIPE = {
  offsetC: 0.5,
  trendCPerYear: 0.04,
  trendCentreYear: 2014.5,
  yearDeviationSd: 0.8,
  spellPersistence: 0.7,
  spellSd: 3.5,
  dailyRangeC: 6,
  rainShape: 0.6,
  rainScaleMm: 4.7,
  seed: 1,
};

/** Mean temperature of a day of the year, interpolated between the middles of the months. */
function seasonalMean(dayOfYear) {
  const xs = [
    ...MID_MONTH_DAY.map((d) => d - DAYS_PER_YEAR),
    ...MID_MONTH_DAY,
    ...MID_MONTH_DAY.map((d) => d + DAYS_PER_YEAR),
  ];
  const ys = [...MONTHLY_MEAN_C, ...MONTHLY_MEAN_C, ...MONTHLY_MEAN_C];
  const i = xs.findIndex((x) => x > dayOfYear);
  const t = (dayOfYear - xs[i - 1]) / (xs[i] - xs[i - 1]);
  return ys[i - 1] + t * (ys[i] - ys[i - 1]);
}

export function demoFarmWeather({ first, last } = DEMO_WEATHER_YEARS, recipe = RECIPE) {
  const rng = new SeededRandom(recipe.seed);
  const cal = DailyWeather.calendar(first, last);
  const yearDeviation = new Map();
  for (let y = first; y <= last; y++) yearDeviation.set(y, rng.normal(0, recipe.yearDeviationSd));
  const shockSd = recipe.spellSd * Math.sqrt(1 - recipe.spellPersistence ** 2);
  let spell = 0;
  const tmax = [];
  const tmin = [];
  const rain = [];
  for (let i = 0; i < cal.year.length; i++) {
    if (i > 0) spell = recipe.spellPersistence * spell + rng.normal(0, shockSd);
    const mean =
      seasonalMean(cal.dayOfYear[i]) +
      recipe.offsetC +
      recipe.trendCPerYear * (cal.year[i] - recipe.trendCentreYear) +
      yearDeviation.get(cal.year[i]) +
      spell;
    tmax.push(mean + recipe.dailyRangeC);
    tmin.push(mean - recipe.dailyRangeC);
    rain.push(rng.gamma(recipe.rainShape, recipe.rainScaleMm));
  }
  return new DailyWeather({ ...cal, tmax, tmin, rain });
}
