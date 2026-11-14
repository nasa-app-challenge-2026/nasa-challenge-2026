/**
 * Steps 9b and 10 against the reference implementation: for every scenario exported
 * from field_shift.py v5.1 (same climate, same twins), the JavaScript planner must
 * choose the same chains, with the same scores, decisions, alternatives and robustness.
 */
import { describe, expect, it } from 'vitest';
import { ParcelPlanner } from '../../backend/algorithm/planning/ParcelPlanner.js';
import { sheetIds } from '../../backend/algorithm/chain/ChainStep.js';
import { sharedDiseaseText, ruleReasonText } from '../../backend/algorithm/report/messages.js';
import { close, cropIdOf, fixture, idOf } from './helpers/reference.js';
import { inputsOf } from './helpers/referencePlan.js';

const SCENARIOS = [
  'demo-4-12-12',
  'demo-4-6-8',
  'demo-3-12-9',
  'demo-5-12-10',
  'demo-2-12-6',
  'demo-3-4-3',
  'variant-uniquement',
  'variant-betail-maladie-irrigation',
  'variant-sans-fourragere-libre',
];

/**
 * Deliberate differences with the reference (docs/ALGORITHME.md, "Écarts"):
 * a field with no crop in place has its yield successions read in order (the
 * reference pairs each crop with itself).
 */
const KNOWN_DEVIATIONS = new Set(['variant-sans-fourragere-libre/P3']);

const text = (s) => s.replace(/’/g, "'");
const SCORE_TOLERANCE = 1e-9;
const TIME_TOLERANCE = 1e-9;

function expectChain(actual, expected) {
  expect(sheetIds(actual)).toEqual(expected.map(([name]) => idOf(name)));
  actual.forEach((step, i) => {
    const [, s, r, p, q] = expected[i];
    expect(close(step.sowing, s, TIME_TOLERANCE)).toBe(true);
    expect(close(step.harvest, r, TIME_TOLERANCE), `${step.sheetId} ${step.harvest} ≠ ${r}`).toBe(
      true,
    );
    expect([step.firstPosition, step.lastPosition]).toEqual([p, q]);
  });
}

function expectCycle(actual, ref) {
  expect(actual.years).toEqual(ref.annees);
  expect(actual.context.candidates).toEqual(ref.ctx.candidates.map(idOf));
  for (const [c, w] of Object.entries(ref.ctx.poids))
    expect(close(actual.weights[c], w)).toBe(true);
  expect(actual.decision).toBe(ref.decision);
  expectChain(actual.chosen.chain, ref.chaine);
  expect(
    close(actual.chosen.score, ref.note, SCORE_TOLERANCE),
    `${actual.chosen.score} ≠ ${ref.note}`,
  ).toBe(true);
  for (const [c, v] of Object.entries(ref.criteres))
    expect(close(actual.chosen.criteria[c], v), c).toBe(true);
  expect(actual.chosen.gaps).toEqual(ref.lacunes.map((g) => g.split(' → ').map(cropIdOf)));
  expect(actual.chosen.seedsToBuy).toEqual(ref.achats.map(cropIdOf));
  expect(actual.chosen.covers.map((c) => [c.sheetId, c.sowing, c.harvest])).toEqual(
    ref.intercalaires.map(([n, s, r]) => [idOf(n), expect.closeTo(s, 9), expect.closeTo(r, 9)]),
  );
  expect(actual.chosen.warnings.map((w) => text(sharedDiseaseText(w)))).toEqual(
    ref.vigilances.map(text),
  );
  expect(close(actual.risks.erosion, ref.diagnostic.risque_erosion)).toBe(true);
  expect(close(actual.risks.water, ref.diagnostic.risque_eau)).toBe(true);
  if (ref.reference) {
    expectChain(actual.reference.chain, ref.reference);
    expect(close(actual.reference.score, ref.note_reference, SCORE_TOLERANCE)).toBe(true);
  } else expect(actual.reference).toBeNull();
  expect(
    actual.referenceAlerts.map((a) => [text(ruleReasonText(a.reason)), a.yearsWithout, a.minimum]),
  ).toEqual(ref.alertes_reference.map((a) => [text(a.raison), a.annees_sans, a.minimum]));
  expect([...actual.removed.keys()]).toEqual(Object.keys(ref.impossibles).map(idOf));
  expect(actual.alternatives.map((a) => sheetIds(a.chain))).toEqual(
    ref.alternatives.map(([names]) => names.map(idOf)),
  );
  actual.alternatives.forEach((a, i) =>
    expect(close(a.score, ref.alternatives[i][1], SCORE_TOLERANCE)).toBe(true),
  );
  expect(close(actual.robustness, ref.robustesse, SCORE_TOLERANCE)).toBe(true);
  expect(actual.becomesInfeasibleLater).toBe(ref.non_faisable_plus_tard ?? false);
}

describe('plans are the same as the reference (field_shift.py v5.1)', () => {
  for (const name of SCENARIOS) {
    const fx = fixture(`plan-${name}.json`);
    const { parcels, ...setup } = inputsOf(fx);
    const planner = new ParcelPlanner(setup);
    fx.parcels.forEach((refParcel, i) => {
      const label = `${name}/${refParcel.nom}`;
      if (KNOWN_DEVIATIONS.has(label)) return;
      it(label, () => {
        const plan = planner.plan(parcels[i]);
        expect(plan.cycles).toHaveLength(refParcel.cycles.length);
        plan.cycles.forEach((cycle, k) => expectCycle(cycle, refParcel.cycles[k]));
      });
    });
  }
});
