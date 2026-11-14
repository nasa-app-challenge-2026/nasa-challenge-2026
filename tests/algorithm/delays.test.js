/** Return delays (part B) and weights (step 1) against the reference (field_shift.py v5.1). */
import { describe, expect, it } from 'vitest';
import { defaultDelayCatalog as catalog } from '../../backend/algorithm/delays/ReturnDelayCatalog.js';
import {
  ReturnDelayChecker,
  historyDepth,
  impossibleCrops,
} from '../../backend/algorithm/delays/ReturnDelayChecker.js';
import { Occupation } from '../../backend/algorithm/delays/Occupation.js';
import { fieldHistory } from '../../backend/algorithm/delays/FieldHistory.js';
import {
  impossibleText,
  sharedDiseaseText,
  ruleReasonText,
} from '../../backend/algorithm/report/messages.js';
import { weightsFromRanking } from '../../application/rules/priorities.js';
import { SHEETS } from '../../data/reference/crops.js';
import { close, cropIdOf, diseaseIdOf, fixture, idOf } from './helpers/reference.js';

const ref = fixture('delays.json');
const text = (s) => s.replace(/’/g, "'");
const occs = (list) =>
  list.map(([crop, first, last, source]) => new Occupation(cropIdOf(crop), first, last, source));

const sameViolations = (actual, expected) => {
  expect(actual.map((v) => text(ruleReasonText(v.reason)))).toEqual(
    expected.map((v) => text(v.raison)),
  );
  expect(
    actual.map((v) => [
      v.yearsWithout,
      v.minimum,
      v.from.year,
      v.from.source,
      v.to.year,
      v.to.source,
    ]),
  ).toEqual(expected.map((v) => [v.annees_sans, v.minimum, v.de[0], v.de[1], v.a[0], v.a[1]]));
};

describe('return delays', () => {
  it('derives the minimum and recommended delays of every crop', () => {
    for (const [name, d] of Object.entries(ref.delays)) {
      const mine = catalog.get(cropIdOf(name));
      expect([mine.minimum, mine.recommended, mine.family, mine.perennial], name).toEqual([
        d.minimum,
        d.recommande,
        d.famille,
        d.perenne,
      ]);
    }
  });

  for (const c of ref.cases) {
    it(`checks the chain "${c.name}" like the reference`, () => {
      const checker = new ReturnDelayChecker({
        cycleYears: c.C,
        history: c.historique ? occs(c.historique) : null,
        diseases: c.maladies.map(diseaseIdOf),
      });
      const verdict = checker.check(occs(c.occs));
      expect(verdict.ok).toBe(c.ok);
      sameViolations(verdict.violations, c.violations);
      expect(verdict.warnings.map((w) => text(sharedDiseaseText(w)))).toEqual(
        c.vigilances.map(text),
      );
      expect(close(verdict.pestScore, c.note_ravageurs, 1e-12)).toBe(true);
      const partial = occs(c.occs).slice(0, 2);
      sameViolations(checker.violations(partial, { closed: false }), c.partial.violations);
      expect(close(checker.pestScore(partial, { closed: false }), c.partial_note, 1e-12)).toBe(
        true,
      );
    });
  }

  it('removes the crops whose delay does not fit in the cycle', () => {
    const sheets = ['mais', 'soya', 'canola', 'luzerne-2', 'luzerne-3', 'foin-3', 'pois'].map(
      (id) => SHEETS[id] ?? { id, cropId: id, productionYears: 0 },
    );
    for (const { C, maladies, result } of ref.impossible) {
      const out = impossibleCrops(C, sheets, maladies.map(diseaseIdOf));
      const expected = Object.fromEntries(
        Object.entries(result).map(([name, msg]) => [idOf(name), text(msg)]),
      );
      const mine = Object.fromEntries(
        [...out]
          .filter(([id]) => SHEETS[id])
          .map(([id, info]) => [id, text(impossibleText(id, info, C))]),
      );
      const expectedSheets = Object.fromEntries(
        Object.entries(expected).filter(([id]) => SHEETS[id]),
      );
      expect(mine).toEqual(expectedSheets);
      expect([...out.keys()].sort()).toEqual(Object.keys(expected).sort());
    }
  });

  it('asks enough years of history', () => {
    for (const { cultures, maladies, depth } of ref.history_depth)
      expect(historyDepth(cultures.map(cropIdOf), maladies.map(diseaseIdOf))).toBe(depth);
  });

  it('rebuilds the history of a field like the reference', () => {
    for (const h of ref.history) {
      const sheet = SHEETS[idOf(h.culture_en_place)];
      const freeYear = 2000 + Math.floor(h.libre / 12);
      // The reference reads the past crops from the most recent backwards; the last one,
      // when it is the annual crop in place, is that crop itself.
      let past = [...h.historique];
      if (past.length && !sheet.productionYears && cropIdOf(past[past.length - 1]) === sheet.cropId)
        past = past.slice(0, -1);
      const entries = past
        .reverse()
        .map((name, i) => ({ year: freeYear - 1 - i, cropId: cropIdOf(name) }));
      const result = fieldHistory({ inPlace: sheet, freeYear, past: entries });
      expect(result.map((o) => [o.cropId, o.firstYear, o.lastYear])).toEqual(
        h.result.map(([c, a, b]) => [cropIdOf(c), a, b]),
      );
    }
  });
});

describe('step 1 · weights', () => {
  it('turns a ranking into rank-order-centroid weights', () => {
    for (const { classement, base } of ref.weights) {
      const weights = weightsFromRanking(classement);
      for (const [c, w] of Object.entries(base)) expect(close(weights[c], w, 1e-12), c).toBe(true);
    }
  });
});
