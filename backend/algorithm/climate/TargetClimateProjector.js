/**
 * Step 3: the climate the farm will have during a cycle, as day-by-day weather.
 *
 * The last year of the cycle decides:
 *   - it ends within 10 years of today → case 1, NASA POWER trend (TemperatureTrend);
 *   - later → case 2, 3 to 5 NEX-GDDP-CMIP6 models applied to NASA POWER by the
 *     delta method, on a 20-year window centred on the cycle. Each model gives its
 *     own target climate (the twins are searched model by model, step 4); the
 *     calendar of step 9b is the mean of the models.
 */
import {
  CLIMATE_WINDOW_AFTER_YEARS,
  CLIMATE_WINDOW_BEFORE_YEARS,
  MODEL_BASELINE,
  RECENT_WINDOW,
  SHORT_TERM_HORIZON_YEARS,
} from '../config/climate.js';
import { percentChange, roundHalfToEven } from '../math/numbers.js';
import { CLIMATE_METHOD } from './CycleClimate.js';
import { CycleClimateBuilder, meanSummerRain, meanTemperature } from './CycleClimateBuilder.js';
import { DeltaMethod } from './DeltaMethod.js';
import { IndicatorTable } from './IndicatorTable.js';
import { TemperatureTrend } from './TemperatureTrend.js';

export const TREND_SOURCE = 'tendance NASA POWER';

/**
 * A climate model (NEX-GDDP-CMIP6, converted to °C and mm/day):
 * @typedef {{ name: string,
 *   simulate: (firstYear: number, lastYear: number) =>
 *     { historical: DailyWeather, future: DailyWeather } }} ClimateModel
 */

export class TargetClimateProjector {
  /**
   * @param {object} p
   * @param {DailyWeather} p.farmWeather NASA POWER at the farm, 1985 to the last full year
   * @param {number} p.currentYear       the year the app is used
   * @param {ClimateModel[]} [p.models]  needed for cycles beyond the short term
   */
  constructor({ farmWeather, currentYear, models = [] }) {
    this.farmWeather = farmWeather;
    this.currentYear = currentYear;
    this.models = models;
    this.trend = new TemperatureTrend(farmWeather);
    this.cache = new Map();
  }

  /** Case 1 or case 2 for the cycle `firstYear`–`lastYear`. */
  usesTrend(lastYear) {
    return lastYear <= this.currentYear + SHORT_TERM_HORIZON_YEARS;
  }

  /**
   * @returns {{ targets: { source: string, indicators: IndicatorTable }[],
   *             climate: import('./CycleClimate.js').CycleClimate }}
   */
  project(firstYear, lastYear) {
    const key = `${firstYear}-${lastYear}`;
    if (!this.cache.has(key))
      this.cache.set(
        key,
        this.usesTrend(lastYear)
          ? this.#fromTrend(firstYear, lastYear)
          : this.#fromModels(firstYear, lastYear),
      );
    return this.cache.get(key);
  }

  #fromTrend(firstYear, lastYear) {
    const { weather, shiftC } = this.trend.extendTo((firstYear + lastYear) / 2);
    return {
      targets: [{ source: 'NASA POWER', indicators: IndicatorTable.fromWeather(weather) }],
      climate: CycleClimateBuilder.fromWeather(weather, {
        warmingC: shiftC,
        method: CLIMATE_METHOD.TREND,
        source: TREND_SOURCE,
      }),
    };
  }

  #fromModels(firstYear, lastYear) {
    if (!this.models.length)
      throw new Error(
        `Cycle ${firstYear}-${lastYear} au-delà de ${SHORT_TERM_HORIZON_YEARS} ans : il faut des modèles climatiques`,
      );
    const observed = this.farmWeather.between(MODEL_BASELINE.first, MODEL_BASELINE.last);
    const recent = this.farmWeather.between(RECENT_WINDOW.first, RECENT_WINDOW.last);
    const recentTemperature = meanTemperature(recent);
    const recentSummerRain = meanSummerRain(recent);
    const centre = roundHalfToEven((firstYear + lastYear) / 2);
    const targets = [];
    const climates = [];
    for (const model of this.models) {
      const { historical, future } = model.simulate(
        centre - CLIMATE_WINDOW_BEFORE_YEARS,
        centre + CLIMATE_WINDOW_AFTER_YEARS,
      );
      const weather = DeltaMethod.apply(observed, historical, future);
      targets.push({ source: model.name, indicators: IndicatorTable.fromWeather(weather) });
      climates.push(
        CycleClimateBuilder.fromWeather(weather, {
          warmingC: meanTemperature(weather) - recentTemperature,
          method: CLIMATE_METHOD.MODELS,
          source: model.name,
          summerRainChangePct: percentChange(meanSummerRain(weather), recentSummerRain),
          models: [model.name],
        }),
      );
    }
    const source = `NEX-GDDP-CMIP6 (deltas, moyenne de ${climates.length} modèles)`;
    return {
      targets,
      climate: CycleClimateBuilder.average(climates, { method: CLIMATE_METHOD.MODELS, source }),
    };
  }
}
