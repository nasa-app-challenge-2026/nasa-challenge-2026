/** Steps 4 to 8 against the reference implementation (field_shift.py v5.1). */
import { describe, expect, it } from 'vitest';
import { sigmaDissimilarity } from '../../backend/algorithm/twins/SigmaDissimilarity.js';
import { ClimateTwinFinder } from '../../backend/algorithm/twins/ClimateTwinFinder.js';
import { SoilFilter, soilDistance } from '../../backend/algorithm/twins/SoilComparison.js';
import { rotationOf } from '../../backend/algorithm/twins/RotationPattern.js';
import { precropValue, yieldGapFromNdvi } from '../../backend/algorithm/twins/PrecropValue.js';
import { buildTwinEvidence } from '../../backend/algorithm/twins/TwinEvidenceBuilder.js';
import { IndicatorTable } from '../../backend/algorithm/climate/IndicatorTable.js';
import { ParcelDiagnostic } from '../../backend/algorithm/diagnostic/ParcelDiagnostic.js';
import { chiCdf, chiOneQuantile } from '../../backend/algorithm/math/distributions.js';
import { close, fixture, num } from './helpers/reference.js';

const twins = fixture('twins.json');
const steps = fixture('steps-5-to-8.json');

const cellRows = (c) => twins.present.map((year) => year[c]);
const soil = ({ argile, sable, soc, ph }) => ({
  clayPct: argile,
  sandPct: sable,
  organicCarbon: soc,
  ph,
});

describe('step 4 · climate twins', () => {
  it('chi distribution: percentiles and back', () => {
    expect(close(chiCdf(1, 1.959963984540054), 0.95, 1e-12)).toBe(true);
    expect(close(chiOneQuantile(0.95), 1.959963984540054, 1e-12)).toBe(true);
    expect(close(chiOneQuantile(chiCdf(5, 3)), 1.6024136970635021, 1e-10)).toBe(true);
    expect(close(chiOneQuantile(chiCdf(5, 8)), 7.048654961450338, 1e-8)).toBe(true);
    expect(chiOneQuantile(1)).toBe(Infinity);
  });

  it('gives the same sigma as the reference for every cell', () => {
    twins.sigma.forEach((expected, c) => {
      const sigma = sigmaDissimilarity(twins.future, cellRows(c));
      expect(close(sigma, num(expected), 1e-7, 1e-9), `cell ${c}: ${sigma} ≠ ${expected}`).toBe(
        true,
      );
    });
  });

  it('keeps the closest cultivated cells', () => {
    const years = twins.present.map((_, i) => 2011 + i);
    const cells = twins.mask.map((cultivated, c) => ({
      id: `c${c}`,
      lat: 45,
      lon: -73,
      cultivated,
      indicators: new IndicatorTable(years, cellRows(c)),
    }));
    const finder = new ClimateTwinFinder(cells, { twinsPerTarget: twins.best.n });
    const best = finder.closestCells(twins.future);
    expect(best.map((b) => Number(b.cell.id.slice(1)))).toEqual(twins.best.cells);
    const union = finder.twinsOf([
      { source: 'A', indicators: { rows: twins.future } },
      { source: 'B', indicators: { rows: twins.future } },
    ]);
    expect(union).toHaveLength(twins.best.n);
    expect(union[0].sources).toEqual(['A', 'B']);
  });
});

describe('step 5 · soil', () => {
  it('measures the soil distance like the reference', () => {
    for (const { a, b, distance } of steps.soil) {
      expect(close(soilDistance(soil(a), soil(b)), distance, 1e-12)).toBe(true);
    }
  });

  it('widens the tolerances when too few fields are left', () => {
    const field = soil(steps.soil[1].a);
    const near = { soil: soil(steps.soil[1].a) };
    const medium = { soil: { ...field, clayPct: field.clayPct + 18 } };
    const filter = new SoilFilter(field, { minFields: 2 });
    expect(filter.keepComparable([near, near, medium])).toEqual({
      fields: [near, near],
      widened: false,
    });
    expect(filter.keepComparable([near, medium]).widened).toBe(true);
    expect(filter.keepComparable([near, medium]).fields).toHaveLength(2);
  });
});

describe('steps 6 and 7 · rotations and precrop values', () => {
  it('reduces a sequence to its rotation like the reference', () => {
    for (const { sequence, result } of steps.canonical) expect(rotationOf(sequence)).toBe(result);
  });

  it('turns greenness into a yield gap, then a precrop value', () => {
    for (const { args, result } of steps.ndvi_gap) {
      const [x, p90, p50, p25] = args;
      expect(close(yieldGapFromNdvi(x, { p90, p50, p25 }), result, 1e-12)).toBe(true);
    }
    const rows = steps.precrop.rows.map((r) => ({
      crop: r.culture,
      previous: r.precedent,
      yieldGap: r.ecart,
    }));
    for (const { a, b, value } of steps.precrop.results) {
      const v = precropValue(rows, a, b);
      if (value === null) expect(v).toBeNull();
      else expect(close(v, value, 1e-9)).toBe(true);
    }
  });

  it('builds the twin evidence like the reference', () => {
    const rows = steps.precrop.rows.map((r) => ({
      crop: r.culture,
      previous: r.precedent,
      yieldGap: r.ecart,
    }));
    const ref = steps.twin_evidence;
    const fields = ref.fields.map((f) => ({
      sequence: f.sequence,
      areaHa: f.superficie,
      sigma: f.sigma,
    }));
    const evidence = buildTwinEvidence(fields, rows);
    expect([...evidence.crops].sort()).toEqual(ref.cultures);
    for (const [a, b, v] of ref.precedents) {
      expect(evidence.isObserved(a, b)).toBe(true);
      if (v === null) expect(evidence.precropValue(a, b)).toBeNull();
      else expect(close(evidence.precropValue(a, b), v, 1e-9)).toBe(true);
    }
    expect(close(evidence.sigmaMean, ref.sigma_moyen)).toBe(true);
    expect(evidence.topRotations.map(([r]) => r)).toEqual(ref.top.map(([r]) => r));
  });
});

describe('step 8 · diagnostic', () => {
  it('gives the same risks as the reference', () => {
    for (const { measures: m, rain, irrigation, result } of steps.diagnostics) {
      const diagnostic = new ParcelDiagnostic(
        {
          slopePct: m.pente_pct,
          heavyRainDays: m.jours_pluie_intense,
          bareSoilDays: m.jours_sol_nu,
          summerStressIndex: m.esi_ete,
          rootZoneDrought: m.smap_secheresse,
          groundwaterTrendCmPerYear: m.grace_tendance_cm_an,
        },
        { irrigated: irrigation },
      );
      const risks = diagnostic.risksFor({ summerRainChangePct: rain });
      expect(close(risks.erosion, result.risque_erosion, 1e-12)).toBe(true);
      expect(close(risks.water, result.risque_eau, 1e-12)).toBe(true);
    }
  });
});
