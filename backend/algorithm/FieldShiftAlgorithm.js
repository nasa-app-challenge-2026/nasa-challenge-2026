/**
 * Field Shift, the rotation algorithm (port of field_shift.py v5.1, see
 * docs/ALGORITHME.md). One call plans every section of a farm:
 *
 *   step 1     farmer's inputs           input/FarmInputReader.js, application/rules/
 *   steps 2-3  target climate per cycle  climate/
 *   step 4     climate twins             twins/ClimateTwinFinder.js
 *   steps 5-7  soil, rotations, precrops twins/
 *   step 8     field diagnostic          diagnostic/ParcelDiagnostic.js
 *   step 9b    best chains               chain/
 *   step 10    plan, cycle by cycle      planning/
 *
 * The data sources are given when the algorithm is built: the farm weather (real
 * NASA POWER or the demo series) and, for now, fictitious climate models, twins and
 * satellite measures (sources/Demo*.js).
 */
import { SEED_IDS } from '../../data/reference/crops.js';
import { ClimateTwinFinder } from './twins/ClimateTwinFinder.js';
import { TargetClimateProjector } from './climate/TargetClimateProjector.js';
import { historyDepth } from './delays/ReturnDelayChecker.js';
import { readFarmInput, dayTimeOf } from './input/FarmInputReader.js';
import { ParcelPlanner } from './planning/ParcelPlanner.js';
import { serializeCycle, serializeHistory, isoDateOf, round } from './report/PlanSerializer.js';
import { CycleDataProvider } from './sources/CycleDataProvider.js';
import { demoClimateModels } from './sources/DemoClimateModels.js';
import { demoFieldMeasures, demoSoil } from './sources/DemoFieldMeasures.js';
import { demoTwinAtlas } from './sources/DemoTwinAtlas.js';
import { demoTwinEvidence } from './sources/DemoTwinCrops.js';
import { MonthTime } from './time/MonthTime.js';

export const ALGORITHM_VERSION = 'field_shift v5.1';
export const CONTRACT_VERSION = '2.0';

/** Where each kind of data comes from, shown to the farmer (meta.sources). */
const DEMO_SOURCES = {
  climateModels: {
    real: false,
    label: '3 modèles climatiques fictifs (à la place de NEX-GDDP-CMIP6)',
  },
  twins: { real: false, label: 'Grille de climats et cultures des jumeaux fictive' },
  fieldMeasures: { real: false, label: 'Mesures satellites et sol fictifs' },
};

export class FieldShiftAlgorithm {
  /**
   * @param {object} p
   * @param {import('./weather/DailyWeather.js').DailyWeather} p.farmWeather daily weather at the farm
   * @param {{ real: boolean, label: string }} p.weatherSource
   * @param {{ lat: number, lon: number }} p.location
   * @param {number} p.currentYear the year the app is used
   */
  constructor({ farmWeather, weatherSource, location, currentYear }) {
    this.weatherSource = weatherSource;
    this.data = new CycleDataProvider({
      projector: new TargetClimateProjector({
        farmWeather,
        currentYear,
        models: demoClimateModels(farmWeather),
      }),
      twinFinder: new ClimateTwinFinder(demoTwinAtlas(location, farmWeather)),
      evidenceFor: demoTwinEvidence,
    });
  }

  /**
   * @param {object} input FarmInput v2 (docs/ALGO_CONTRACT.md)
   * @param {string} today ISO date the app is used
   * @returns {object} FarmPlan v2
   */
  planFarm(input, today) {
    const { time, farmer, parcels } = readFarmInput(input, (s) => demoFieldMeasures(s.id));
    const planner = new ParcelPlanner({ time, farmer, data: this.data, today: dayTimeOf(today) });
    const sections = input.sections.map((section, i) => {
      const parcel = parcels[i];
      const plan = planner.plan(parcel);
      const cycles = plan.cycles.map((c) => serializeCycle(c, time.cycleYears));
      return {
        id: section.id,
        freeAt: isoDateOf(plan.freeAt),
        firstYear: cycles[0]?.years[0] ?? null,
        lastYear: cycles[cycles.length - 1]?.years[1] ?? null,
        repeatsCurrentCrop: parcel.repeatsInPlaceCrop,
        historyYears: historyDepth(SEED_IDS, parcel.diseases),
        history: serializeHistory(plan.history),
        field: {
          measures: parcel.diagnostic.measures,
          soil: section.soilTest
            ? { ...section.soilTest, source: 'Votre analyse de sol' }
            : { ...demoSoil(section.id), source: 'SoilGrids 2.0 (fictif)' },
          risksToday: {
            erosion: round(parcel.diagnostic.erosionRisk),
            water: round(parcel.diagnostic.waterRisk(0)),
          },
        },
        cycles,
      };
    });
    return {
      version: CONTRACT_VERSION,
      meta: {
        engine: 'field-shift-js',
        algorithm: ALGORITHM_VERSION,
        demo: !this.weatherSource.real || Object.values(DEMO_SOURCES).some((s) => !s.real),
        generatedAt: new Date().toISOString(),
        sources: { farmWeather: this.weatherSource, ...DEMO_SOURCES },
      },
      settings: {
        cycleYears: time.cycleYears,
        frequencyMonths: time.frequencyMonths,
        positionsPerCycle: time.positionsPerCycle,
        horizonYears: time.horizonYears,
        currentYear: MonthTime.yearOf(dayTimeOf(today)),
      },
      weights: roundWeights(farmer.baseWeights),
      sections,
    };
  }
}

const roundWeights = (weights) =>
  Object.fromEntries(Object.entries(weights).map(([k, v]) => [k, round(v)]));
