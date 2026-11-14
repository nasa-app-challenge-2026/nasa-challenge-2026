/**
 * Three FICTITIOUS climate models standing in for NEX-GDDP-CMIP6 (field_shift.py,
 * _modele_fictif): each sees the farm 1 °C too warm (an error the delta method
 * cancels), warms by `factor` × 0.04 °C a year since 1985–2014 and changes the rain.
 * The real files (AWS, no account) are hundreds of MB per model: they belong to a
 * server, not to the browser.
 */
import { MODEL_BASELINE } from '../config/climate.js';

const BIAS_C = 1;
const BASE_WARMING_C_PER_YEAR = 0.04;
const BASELINE_CENTRE = (MODEL_BASELINE.first + MODEL_BASELINE.last) / 2;

export const DEMO_MODELS = [
  { name: 'modèle A (fictif)', warmingFactor: 0.8, rainRatio: 1.05 },
  { name: 'modèle B (fictif)', warmingFactor: 1.0, rainRatio: 1.0 },
  { name: 'modèle C (fictif)', warmingFactor: 1.3, rainRatio: 0.92 },
];

/** @param {import('../weather/DailyWeather.js').DailyWeather} farmWeather */
export function demoClimateModels(farmWeather, models = DEMO_MODELS) {
  const historical = farmWeather
    .between(MODEL_BASELINE.first, MODEL_BASELINE.last)
    .shiftedBy(BIAS_C);
  return models.map(({ name, warmingFactor, rainRatio }) => ({
    name,
    simulate(firstYear, lastYear) {
      const warming =
        warmingFactor * BASE_WARMING_C_PER_YEAR * ((firstYear + lastYear) / 2 - BASELINE_CENTRE);
      const future = historical.shiftedBy(warming);
      return {
        historical,
        future: future.with({ rain: historical.rain.map((v) => v * rainRatio) }),
      };
    },
  }));
}
