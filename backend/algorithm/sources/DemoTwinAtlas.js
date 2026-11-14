/**
 * A FICTITIOUS grid of observed climates around the farm (2011–2024), so that the
 * real twin search (step 4) runs in the demo. Real cells would come from NASA
 * POWER for every cultivated 0.5° cell of eastern North America, computed once on
 * a server.
 *
 * Each cell starts from the farm's own observed indicators, moved by typical
 * gradients of eastern North America (colder and shorter seasons northward, wetter
 * eastward), plus a small noise of its own. A cycle warmer than today therefore
 * finds its twins south of the farm, farther when it is warmer.
 */
import { IndicatorTable } from '../climate/IndicatorTable.js';
import { TWIN_PERIOD } from '../config/climate.js';
import { SeededRandom } from '../math/SeededRandom.js';

/** Grid step and extent around the farm, in degrees. */
const GRID = { stepDeg: 0.5, latitudeSpanDeg: 6, longitudeSpanDeg: 8 };
/** Change of each indicator per degree north and per degree east (fictitious, plausible). */
const PER_DEGREE_NORTH = [-100, -4, -6, -2.5, -1.3];
const PER_DEGREE_EAST = [-8, 6, 0.5, -0.4, 0.3];
/** Local climate of a cell (hills, lakes…): a fixed offset per indicator, this standard deviation. */
const CELL_OFFSET_SD = [40, 20, 4, 1.5, 0.6];
/** Small year-to-year noise of a cell, so that no two cells are exactly alike. */
const YEAR_NOISE_SD = [10, 5, 1, 0.5, 0.2];
/** Indicators that cannot be negative: degree-days, rain, frost-free days, hot days. */
const NON_NEGATIVE = [true, true, true, true, false];
const NOISE_SEED = 2011;

/**
 * @param {{ lat: number, lon: number }} farm
 * @param {import('../weather/DailyWeather.js').DailyWeather} farmWeather
 * @returns {import('../twins/ClimateTwinFinder.js').GridCell[]}
 */
export function demoTwinAtlas(farm, farmWeather, period = TWIN_PERIOD) {
  const observed = IndicatorTable.fromWeather(farmWeather).between(period.first, period.last);
  const rng = new SeededRandom(NOISE_SEED);
  const steps = (span) => Math.round(span / GRID.stepDeg);
  const cells = [];
  for (let i = -steps(GRID.latitudeSpanDeg); i <= steps(GRID.latitudeSpanDeg); i++) {
    for (let j = -steps(GRID.longitudeSpanDeg); j <= steps(GRID.longitudeSpanDeg); j++) {
      const north = i * GRID.stepDeg;
      const east = j * GRID.stepDeg;
      const offset = CELL_OFFSET_SD.map((sd) => rng.normal(0, sd));
      const rows = observed.rows.map((row) =>
        row.map((value, k) => {
          const moved =
            value +
            PER_DEGREE_NORTH[k] * north +
            PER_DEGREE_EAST[k] * east +
            offset[k] +
            rng.normal(0, YEAR_NOISE_SD[k]);
          return NON_NEGATIVE[k] ? Math.max(0, moved) : moved;
        }),
      );
      cells.push({
        id: `${i}:${j}`,
        lat: farm.lat + north,
        lon: farm.lon + east,
        cultivated: true,
        indicators: new IndicatorTable(observed.years, rows),
      });
    }
  }
  return cells;
}
