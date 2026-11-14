/**
 * Step 3, case 2 (a cycle that ends later): the delta method.
 *
 * For each month, a climate model gives the change between its simulation of
 * 1985–2014 and the future window (+2.5 °C in July, −8 % of rain…). That change is
 * applied to the real NASA POWER weather of 1985–2014: temperatures are shifted,
 * rain is multiplied by a bounded ratio. A model that sees the farm 1 °C too warm
 * in the past and in the future has its error cancelled.
 */
import { MONTHS_PER_YEAR } from '../config/calendar.js';
import { RAIN_RATIO_BOUNDS } from '../config/climate.js';
import { clamp, mean } from '../math/numbers.js';

function monthlyMeans(weather, column) {
  const perMonth = Array.from({ length: MONTHS_PER_YEAR }, () => []);
  for (let i = 0; i < weather.length; i++) perMonth[weather.month[i] - 1].push(weather[column][i]);
  return perMonth.map(mean);
}

export const DeltaMethod = {
  /**
   * @param {DailyWeather} observed   NASA POWER, 1985–2014
   * @param {DailyWeather} historical the model on 1985–2014
   * @param {DailyWeather} future     the model on the future window
   * @returns {DailyWeather} the observed weather moved to the future window
   */
  apply(observed, historical, future) {
    const shift = (column) => {
      const past = monthlyMeans(historical, column);
      const next = monthlyMeans(future, column);
      return observed[column].map((v, i) => {
        const m = observed.month[i] - 1;
        return v + (next[m] - past[m]);
      });
    };
    const pastRain = monthlyMeans(historical, 'rain');
    const nextRain = monthlyMeans(future, 'rain');
    const ratio = pastRain.map((p, m) =>
      clamp(nextRain[m] / p, RAIN_RATIO_BOUNDS.min, RAIN_RATIO_BOUNDS.max),
    );
    return observed.with({
      tmax: shift('tmax'),
      tmin: shift('tmin'),
      rain: observed.rain.map((v, i) => v * ratio[observed.month[i] - 1]),
    });
  },
};
