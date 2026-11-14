/** Builds the climate calendar of a cycle (CycleClimate) from a daily weather series. */
import { DAYS_PER_MONTH, MONTHS_PER_YEAR } from '../config/calendar.js';
import {
  FIRST_FALL_DAY_OF_YEAR,
  FROST_C,
  HARVEST_ADVANCE_MONTHS_PER_C,
  JANUARY,
  SUMMER,
} from '../config/climate.js';
import { mean, meanOfFinite } from '../math/numbers.js';
import { CycleClimate } from './CycleClimate.js';
import { dailyDegreeDays } from './IndicatorTable.js';

/** Mean day of the year → decimal month (null when no year had a frost). */
const dayToMonth = (day) => (day === null ? null : (day - 1) / DAYS_PER_MONTH);

function frostDays(weather) {
  const lastSpring = [];
  const firstFall = [];
  for (const days of weather.daysByYear().values()) {
    let spring = NaN;
    let fall = NaN;
    for (const i of days) {
      if (weather.tmin[i] > FROST_C) continue;
      const day = weather.dayOfYear[i];
      if (day < FIRST_FALL_DAY_OF_YEAR) spring = Number.isNaN(spring) ? day : Math.max(spring, day);
      else fall = Number.isNaN(fall) ? day : Math.min(fall, day);
    }
    lastSpring.push(spring);
    firstFall.push(fall);
  }
  return { lastSpring: meanOfFinite(lastSpring), firstFall: meanOfFinite(firstFall) };
}

/** Mean, over the years, of the June–August rain. */
export function meanSummerRain(weather) {
  const totals = [];
  for (const days of weather.daysByYear().values()) {
    let total = 0;
    for (const i of days) {
      const m = weather.month[i];
      if (m >= SUMMER.firstMonth && m <= SUMMER.lastMonth) total += weather.rain[i];
    }
    totals.push(total);
  }
  return mean(totals);
}

/** Mean daily temperature over the whole series. */
export function meanTemperature(weather) {
  let total = 0;
  for (let i = 0; i < weather.length; i++) total += weather.dailyMean(i);
  return total / weather.length;
}

export const CycleClimateBuilder = {
  /**
   * @param {import('../weather/DailyWeather.js').DailyWeather} weather the cycle's weather
   * @param {{ warmingC: number, method: string, source: string,
   *           summerRainChangePct?: number, models?: string[] }} meta
   */
  fromWeather(weather, { warmingC, method, source, summerRainChangePct = 0, models = [] }) {
    const perMonth = Array.from({ length: MONTHS_PER_YEAR }, () => []);
    const january = [];
    for (let i = 0; i < weather.length; i++) {
      perMonth[weather.month[i] - 1].push(dailyDegreeDays(weather.tmax[i], weather.tmin[i]));
      if (weather.month[i] === JANUARY) january.push(weather.tmin[i]);
    }
    const frost = frostDays(weather);
    return new CycleClimate({
      degreeDaysPerDay: perMonth.map(mean),
      lastSpringFrost: dayToMonth(frost.lastSpring),
      firstFallFrost: dayToMonth(frost.firstFall),
      januaryMinimumC: mean(january),
      harvestAdvanceMonths: HARVEST_ADVANCE_MONTHS_PER_C * warmingC,
      warmingC,
      summerRainChangePct,
      method,
      source,
      models,
    });
  },

  /** One calendar per cycle: the mean of the climate models (case 2). */
  average(climates, { method, source }) {
    const avg = (get) => mean(climates.map(get));
    const avgOrNull = (get) => meanOfFinite(climates.map((c) => get(c) ?? NaN));
    return new CycleClimate({
      degreeDaysPerDay: Array.from({ length: MONTHS_PER_YEAR }, (_, k) =>
        avg((c) => c.degreeDaysPerDay[k]),
      ),
      lastSpringFrost: avgOrNull((c) => c.lastSpringFrost),
      firstFallFrost: avgOrNull((c) => c.firstFallFrost),
      januaryMinimumC: avg((c) => c.januaryMinimumC),
      harvestAdvanceMonths: avg((c) => c.harvestAdvanceMonths),
      warmingC: avg((c) => c.warmingC),
      summerRainChangePct: avg((c) => c.summerRainChangePct),
      method,
      source,
      models: climates.flatMap((c) => c.models),
    });
  },
};
