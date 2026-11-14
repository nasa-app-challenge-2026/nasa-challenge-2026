/**
 * Step 3, case 1 (a cycle that ends within 10 years): the trend of the last 40
 * years of NASA POWER, without any climate model.
 *
 * The warming is the slope of the yearly mean temperature (e.g. 0.03 °C a year).
 * The 20 most recent years are shifted by that trend up to the middle of the cycle:
 * each year keeps its real late frosts and heat waves. Rain is not shifted: it
 * varies too much from year to year to extend a trend.
 */
import { RECENT_WINDOW } from '../config/climate.js';
import { linearSlope, mean } from '../math/numbers.js';

export class TemperatureTrend {
  /** @param {import('../weather/DailyWeather.js').DailyWeather} weather 40 years at the farm */
  constructor(weather) {
    const years = [];
    const means = [];
    for (const [year, days] of weather.daysByYear()) {
      years.push(year);
      means.push(mean(days.map((i) => weather.dailyMean(i))));
    }
    this.weather = weather;
    /** Warming in °C per year. */
    this.slopePerYear = linearSlope(years, means);
  }

  /**
   * The recent years, as if they happened around `targetYear`.
   * @returns {{ weather: DailyWeather, shiftC: number }}
   */
  extendTo(targetYear, window = RECENT_WINDOW) {
    const middle = (window.first + window.last) / 2;
    const shiftC = this.slopePerYear * (targetYear - middle);
    return { weather: this.weather.between(window.first, window.last).shiftedBy(shiftC), shiftC };
  }
}
