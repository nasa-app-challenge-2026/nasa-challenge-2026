/**
 * Step 2: a climate summed up in 5 numbers per year, the ones that matter for crops.
 *
 *   djc10          growing degree-days base 10 °C, April to October   enough heat to mature?
 *   pluieEte       rain from June to August (mm)                       enough water when it counts?
 *   saisonSansGel  days between the last spring and first fall frost   frost-free season
 *   joursChauds    days above 30 °C                                    heat stress?
 *   tminJanvier    mean January minimum (°C)                           do winter crops survive?
 *
 * Used on the target climate of the farm (step 3) and on the observed climate of
 * every place of the grid (step 4).
 */
import {
  DEGREE_DAY_BASE_C,
  DEGREE_DAY_CAP_C,
  FIRST_FALL_DAY_OF_YEAR,
  FROST_C,
  GROWING_SEASON,
  HOT_DAY_C,
  JANUARY,
  NO_FALL_FROST_DAY,
  NO_SPRING_FROST_DAY,
  SUMMER,
} from '../config/climate.js';
import { clamp, columnMeans, mean } from '../math/numbers.js';

export const INDICATORS = ['djc10', 'pluieEte', 'saisonSansGel', 'joursChauds', 'tminJanvier'];

const inMonths = (month, { firstMonth, lastMonth }) => month >= firstMonth && month <= lastMonth;

/** Growing degree-days of one day (temperatures capped between 10 and 30 °C). */
export function dailyDegreeDays(tmax, tmin) {
  const cap = (t) => clamp(t, DEGREE_DAY_BASE_C, DEGREE_DAY_CAP_C);
  return (cap(tmax) + cap(tmin)) / 2 - DEGREE_DAY_BASE_C;
}

/** Days between the last spring frost and the first fall frost of one year. */
function frostFreeSeason(weather, days) {
  let lastSpring = NO_SPRING_FROST_DAY;
  let firstFall = NO_FALL_FROST_DAY;
  for (const i of days) {
    if (weather.tmin[i] > FROST_C) continue;
    const day = weather.dayOfYear[i];
    if (day < FIRST_FALL_DAY_OF_YEAR) lastSpring = Math.max(lastSpring, day);
    else firstFall = Math.min(firstFall, day);
  }
  return firstFall - lastSpring - 1;
}

function indicatorsOfYear(weather, days) {
  let degreeDays = 0;
  let summerRain = 0;
  let hotDays = 0;
  const januaryMinima = [];
  for (const i of days) {
    const month = weather.month[i];
    if (inMonths(month, GROWING_SEASON))
      degreeDays += dailyDegreeDays(weather.tmax[i], weather.tmin[i]);
    if (inMonths(month, SUMMER)) summerRain += weather.rain[i];
    if (weather.tmax[i] > HOT_DAY_C) hotDays++;
    if (month === JANUARY) januaryMinima.push(weather.tmin[i]);
  }
  return [degreeDays, summerRain, frostFreeSeason(weather, days), hotDays, mean(januaryMinima)];
}

export class IndicatorTable {
  /** @param {number[]} years @param {number[][]} rows one row of 5 indicators per year */
  constructor(years, rows) {
    this.years = years;
    this.rows = rows;
    Object.freeze(this);
  }

  /** Step 2 on a daily weather series. */
  static fromWeather(weather) {
    const years = [];
    const rows = [];
    for (const [year, days] of weather.daysByYear()) {
      years.push(year);
      rows.push(indicatorsOfYear(weather, days));
    }
    return new IndicatorTable(years, rows);
  }

  /** The rows of the years `first` to `last`. */
  between(first, last) {
    const keep = this.years.map((y) => y >= first && y <= last);
    return new IndicatorTable(
      this.years.filter((_, i) => keep[i]),
      this.rows.filter((_, i) => keep[i]),
    );
  }

  /** Mean of each indicator over the years. */
  means() {
    return columnMeans(this.rows);
  }
}
