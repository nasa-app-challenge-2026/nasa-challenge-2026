/**
 * Step 8: the weak points of a field, redone for every cycle, to give more weight
 * to the criteria concerned.
 *
 *   Erosion  slope (SRTM / NASADEM) 50 %, days with ≥ 25 mm of rain (GPM IMERG) 30 %,
 *            days of bare soil (MODIS / HLS NDVI) 20 %
 *   Water    summer plant stress (ECOSTRESS ESI) 40 %, root-zone drought (SMAP L4) 30 %,
 *            summer rain drop forecast for the cycle (step 3) 20 %,
 *            regional water storage drop (GRACE-FO) 10 %
 *
 * The satellite measures describe the field today and do not change from one cycle
 * to the next; only the rain drop forecast does (0 % in the short term, since rain
 * is not extended; mean of the models in the long term). An irrigated field keeps
 * 40 % of its water risk.
 */
import { EROSION_RISK, IRRIGATED_WATER_RISK_FACTOR, WATER_RISK } from '../config/scoring.js';
import { clamp01 } from '../math/numbers.js';

/**
 * @typedef {object} FieldMeasures
 * @property {number} slopePct            slope (%)
 * @property {number} heavyRainDays       days a year with 25 mm of rain or more
 * @property {number} bareSoilDays        days a year with bare soil
 * @property {number} summerStressIndex   ECOSTRESS evaporative stress index in summer (1 = no stress)
 * @property {number} rootZoneDrought     SMAP L4 root-zone drought, 0 to 1
 * @property {number} groundwaterTrendCmPerYear GRACE-FO water storage trend (negative = drop)
 */

export class ParcelDiagnostic {
  /** @param {FieldMeasures} measures @param {{ irrigated?: boolean }} [options] */
  constructor(measures, { irrigated = false } = {}) {
    this.measures = measures;
    this.irrigated = irrigated;
  }

  get erosionRisk() {
    const m = this.measures;
    return (
      EROSION_RISK.slopePct.share * clamp01(m.slopePct / EROSION_RISK.slopePct.saturation) +
      EROSION_RISK.heavyRainDays.share *
        clamp01(m.heavyRainDays / EROSION_RISK.heavyRainDays.saturation) +
      EROSION_RISK.bareSoilDays.share *
        clamp01(m.bareSoilDays / EROSION_RISK.bareSoilDays.saturation)
    );
  }

  /** Water risk with the summer rain change forecast for a cycle (%). */
  waterRisk(summerRainChangePct) {
    const m = this.measures;
    const stress = WATER_RISK.summerStressIndex;
    const raw =
      stress.share * clamp01((stress.noStress - m.summerStressIndex) / stress.range) +
      WATER_RISK.rootZoneDrought.share * clamp01(m.rootZoneDrought) +
      WATER_RISK.summerRainDropPct.share *
        clamp01(-summerRainChangePct / WATER_RISK.summerRainDropPct.saturation) +
      WATER_RISK.groundwaterDropCmPerYear.share *
        clamp01(-m.groundwaterTrendCmPerYear / WATER_RISK.groundwaterDropCmPerYear.saturation);
    return raw * (this.irrigated ? IRRIGATED_WATER_RISK_FACTOR : 1);
  }

  /** The two risks (0 to 1) of the field during a cycle. */
  risksFor(climate) {
    return { erosion: this.erosionRisk, water: this.waterRisk(climate.summerRainChangePct) };
  }
}
