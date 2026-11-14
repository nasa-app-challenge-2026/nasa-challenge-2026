/**
 * The plan of a field, from the objects of the algorithm to the plain JSON of the
 * contract (docs/ALGO_CONTRACT.md, FarmPlan v2): dates as ISO strings, positions
 * from 1, French messages next to the structured data.
 */
import { CROP_SHEETS, ROLE, SHEETS } from '../../../data/reference/crops.js';
import { DAYS_PER_MONTH } from '../config/calendar.js';
import { isGoodTwin } from '../twins/ClimateTwinFinder.js';
import { MonthTime } from '../time/MonthTime.js';
import { chainLabel } from './chainLabel.js';
import { impossibleText, sharedDiseaseText, successionText, violationText } from './messages.js';

const DECIMALS = 1000;
const round = (v) =>
  v === null || v === undefined || !Number.isFinite(v)
    ? (v ?? null)
    : Math.round(v * DECIMALS) / DECIMALS;
const roundAll = (record) =>
  Object.fromEntries(Object.entries(record).map(([k, v]) => [k, round(v)]));

const date = (time) => (time === null ? null : MonthTime.toIsoDate(time));
const annualDate = (month) => (month === null ? null : MonthTime.dayOfYearParts(month));

function stepKind(step) {
  if (step.firstPosition === null) return 'couvert';
  return SHEETS[step.sheetId].role === ROLE.FALLOW ? 'jachere' : 'culture';
}

/** A step of a chain, covers included, in calendar order. */
function serializeStep(step) {
  return {
    sheet: step.sheetId,
    crop: SHEETS[step.sheetId].cropId,
    kind: stepKind(step),
    sowing: date(step.sowing),
    harvest: stepKind(step) === 'jachere' ? null : date(step.harvest),
    positions: step.firstPosition === null ? null : [step.firstPosition + 1, step.lastPosition + 1],
  };
}

function serializeChain(scored) {
  if (!scored) return null;
  const steps = [...scored.chain, ...scored.covers]
    .map((step, i) => ({ step, i, at: step.sowing ?? step.harvest }))
    .sort((a, b) => a.at - b.at || a.i - b.i)
    .map(({ step }) => serializeStep(step));
  return {
    score: round(scored.score),
    criteria: roundAll(scored.criteria),
    label: chainLabel(scored.chain, scored.covers),
    sheets: scored.chain.map((s) => s.sheetId),
    steps,
    gaps: scored.gaps.map((pair) => ({
      previous: pair[0],
      next: pair[1],
      message: successionText(pair),
    })),
    seedsToBuy: scored.seedsToBuy,
    warnings: scored.warnings.map((w) => ({ ...w, message: sharedDiseaseText(w) })),
  };
}

function serializeClimate(climate) {
  return {
    method: climate.method,
    source: climate.source,
    models: climate.models,
    lastSpringFrost: annualDate(climate.lastSpringFrost),
    firstFallFrost: annualDate(climate.firstFallFrost),
    januaryMinimumC: round(climate.januaryMinimumC),
    warmingC: round(climate.warmingC),
    summerRainChangePct: round(climate.summerRainChangePct),
    harvestAdvanceDays: Math.round(climate.harvestAdvanceMonths * DAYS_PER_MONTH),
  };
}

function serializeTwins(evidence) {
  return {
    sigmaMean: round(evidence.sigmaMean),
    reliable: Number.isFinite(evidence.sigmaMean) && isGoodTwin(evidence.sigmaMean),
    cells: evidence.twins.map(({ cell, sigma, sources }) => ({
      lat: round(cell.lat),
      lon: round(cell.lon),
      sigma: round(sigma),
      sources,
    })),
    crops: CROP_SHEETS.map((s) => s.cropId).filter(
      (c, i, all) => all.indexOf(c) === i && evidence.isGrown(c),
    ),
  };
}

export function serializeCycle(cycle, cycleYears) {
  return {
    index: cycle.index,
    years: cycle.years,
    decision: cycle.decision,
    climate: serializeClimate(cycle.climate),
    twins: serializeTwins(cycle.evidence),
    risks: roundAll(cycle.risks),
    weights: roundAll(cycle.weights),
    chosen: serializeChain(cycle.chosen),
    reference: serializeChain(cycle.reference),
    referenceAlerts: cycle.referenceAlerts.map((v) => ({ ...v, message: violationText(v) })),
    alternatives: cycle.alternatives.map(serializeChain),
    removed: [...cycle.removed].map(([sheet, info]) => ({
      sheet,
      ...info,
      message: impossibleText(sheet, info, cycleYears),
    })),
    robustness: round(cycle.robustness),
    becomesInfeasibleLater: cycle.becomesInfeasibleLater,
  };
}

export function serializeHistory(history) {
  return history.map((o) => ({ crop: o.cropId, from: o.firstYear, to: o.lastYear }));
}

export { date as isoDateOf, round };
