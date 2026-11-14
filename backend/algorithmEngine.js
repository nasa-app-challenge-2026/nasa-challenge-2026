/**
 * The engine of the app: the Field Shift algorithm (backend/algorithm/), run in the
 * browser. It fetches the real NASA POWER weather of the farm (40 years, once per
 * place) and falls back to the fictitious series when NASA POWER cannot be reached.
 *
 * Interface (backend/contract/types.js): { name, planFarm(FarmInput) → Promise<FarmPlan> }.
 */
import { fetchNasaPowerDaily } from '../data/access/nasaPower.js';
import { FieldShiftAlgorithm } from './algorithm/FieldShiftAlgorithm.js';
import { DailyWeather } from './algorithm/weather/DailyWeather.js';
import { demoFarmWeather, DEMO_WEATHER_YEARS } from './algorithm/sources/DemoFarmWeather.js';

/** NASA POWER years used: from 1985 (start of the 40-year trend) to the last full year of data. */
export const WEATHER_YEARS = DEMO_WEATHER_YEARS;

const REAL_WEATHER = {
  real: true,
  label: 'NASA POWER, météo quotidienne 1985–2024 au point de la ferme',
};
const DEMO_WEATHER = { real: false, label: 'Météo fictive (NASA POWER n’a pas pu être joint)' };
const LOCATION_PRECISION = 100;

/** Today as "YYYY-MM-DD", in local time. */
const isoToday = (date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;

/**
 * @param {{ fetchWeather?: typeof fetchNasaPowerDaily, now?: () => Date, useRealWeather?: boolean }} [options]
 * @returns {import('./contract/types.js').Engine}
 */
export function createAlgorithmEngine({
  fetchWeather = fetchNasaPowerDaily,
  now = () => new Date(),
  useRealWeather = true,
} = {}) {
  const algorithms = new Map();

  async function farmWeather({ lat, lon }) {
    if (!useRealWeather) return { weather: demoFarmWeather(), source: DEMO_WEATHER };
    try {
      const series = await fetchWeather(lat, lon, {
        firstYear: WEATHER_YEARS.first,
        lastYear: WEATHER_YEARS.last,
      });
      return { weather: DailyWeather.fromSeries(series), source: REAL_WEATHER };
    } catch {
      return { weather: demoFarmWeather(), source: DEMO_WEATHER };
    }
  }

  async function algorithmFor(location, currentYear) {
    const key =
      [location.lat, location.lon].map((v) => Math.round(v * LOCATION_PRECISION)).join(':') +
      `:${currentYear}`;
    if (!algorithms.has(key)) {
      const pending = farmWeather(location).then(
        ({ weather, source }) =>
          new FieldShiftAlgorithm({
            farmWeather: weather,
            weatherSource: source,
            location,
            currentYear,
          }),
      );
      algorithms.set(key, pending);
      // A demo fallback is not kept: NASA POWER is tried again next time.
      pending.then((a) => !a.weatherSource.real && algorithms.delete(key));
    }
    return algorithms.get(key);
  }

  return {
    name: 'field-shift',
    async planFarm(input) {
      const today = input.today ?? isoToday(now());
      const algorithm = await algorithmFor(input.farm.location, Number(today.slice(0, 4)));
      return algorithm.planFarm(input, today);
    },
  };
}
