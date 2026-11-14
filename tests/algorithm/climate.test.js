/** Steps 2 and 3 against the reference implementation (field_shift.py v5.1). */
import { describe, expect, it } from 'vitest';
import { IndicatorTable } from '../../backend/algorithm/climate/IndicatorTable.js';
import { TemperatureTrend } from '../../backend/algorithm/climate/TemperatureTrend.js';
import { DeltaMethod } from '../../backend/algorithm/climate/DeltaMethod.js';
import { TargetClimateProjector } from '../../backend/algorithm/climate/TargetClimateProjector.js';
import { close, fixture, syntheticModel, syntheticWeather } from './helpers/reference.js';

const ref = fixture('climate.json');
const weather = syntheticWeather(ref.weather.first_year, ref.weather.last_year, ref.weather.seed);
const models = Object.entries(ref.models).map(([name, m]) => syntheticModel(name, m));

const expectRowsClose = (actual, expected, relative = 1e-9) => {
  expect(actual.length).toBe(expected.length);
  actual.forEach((row, i) =>
    row.forEach((v, j) =>
      expect(close(v, expected[i][j], relative), `[${i}][${j}] ${v} ≠ ${expected[i][j]}`).toBe(
        true,
      ),
    ),
  );
};

const expectClimateClose = (actual, expected) => {
  actual.degreeDaysPerDay.forEach((v, k) => expect(close(v, expected.dj_jour[k])).toBe(true));
  expect(close(actual.lastSpringFrost, expected.gel_printemps)).toBe(true);
  expect(close(actual.firstFallFrost, expected.gel_automne)).toBe(true);
  expect(close(actual.januaryMinimumC, expected.tmin_janvier)).toBe(true);
  expect(close(actual.harvestAdvanceMonths, expected.decalage_fin, 1e-7)).toBe(true);
  expect(close(actual.summerRainChangePct, expected.delta_pluie_ete_pct, 1e-7, 1e-7)).toBe(true);
  expect(actual.source).toBe(expected.source);
};

describe('step 2 · climate in 5 numbers', () => {
  it('gives the same yearly indicators as the reference', () => {
    const table = IndicatorTable.fromWeather(weather);
    expect(table.years).toEqual(ref.yearly_indicators.years);
    expectRowsClose(table.rows, ref.yearly_indicators.table);
  });
});

describe('step 3 · target climate', () => {
  it('case 1: extends the 40-year NASA POWER trend', () => {
    const trend = new TemperatureTrend(weather);
    const { weather: shifted, shiftC } = trend.extendTo(ref.extended.target_year);
    expect(close(trend.slopePerYear, ref.extended.slope, 1e-9)).toBe(true);
    expect(close(shiftC, ref.extended.shift, 1e-9)).toBe(true);
    expectRowsClose(IndicatorTable.fromWeather(shifted).rows.slice(0, 3), ref.extended.first_rows);
  });

  it('case 2: applies the monthly deltas of a model', () => {
    const { historical, future } = models[0].simulate(2028, 2047);
    const moved = DeltaMethod.apply(weather.between(1985, 2014), historical, future);
    const table = IndicatorTable.fromWeather(moved);
    expectRowsClose(table.rows.slice(0, 3), ref.delta_x_2028_2047.table_first_rows, 1e-8);
  });

  it('picks the trend for a cycle that ends within 10 years, the models after', () => {
    const projector = new TargetClimateProjector({
      farmWeather: weather,
      currentYear: 2026,
      models,
    });
    const short = projector.project(2027, 2030);
    expect(short.targets.map((t) => t.source)).toEqual(['NASA POWER']);
    expect(short.targets[0].indicators.rows).toHaveLength(
      ref.cycle_2027_2030.target_rows['NASA POWER'],
    );
    expectClimateClose(short.climate, ref.cycle_2027_2030.climate);

    const long = projector.project(2037, 2040);
    expect(long.targets.map((t) => t.source)).toEqual(Object.keys(ref.models));
    for (const t of long.targets) {
      t.indicators
        .means()
        .forEach((v, j) =>
          expect(close(v, ref.cycle_2037_2040.targets[t.source][j], 1e-8)).toBe(true),
        );
    }
    expectClimateClose(long.climate, ref.cycle_2037_2040.climate);
  });
});
