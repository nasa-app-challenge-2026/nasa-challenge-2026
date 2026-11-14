import { describe, expect, it } from 'vitest';
import { answer, SUGGESTED } from '../data/reference/rotaaiAnswers.js';

describe('RotaAI', () => {
  it('answers every suggested question with a real answer (not the fallback)', () => {
    for (const questions of Object.values(SUGGESTED)) {
      for (const q of questions) {
        expect(answer(q).text, q).not.toMatch(/pas encore de réponse/);
      }
    }
  });

  it('ignores accents and case', () => {
    expect(answer('POURQUOI UN CADENAS SUR LA PATATE').text).toMatch(/délai de retour/);
    expect(answer('c est quoi le ndvi').text).toMatch(/NDVI/);
  });

  it('falls back politely on unknown questions', () => {
    expect(answer('quelle heure est-il ?').text).toMatch(/pas encore de réponse/);
  });

  it('never names a study in an answer (team rule)', () => {
    for (const q of Object.values(SUGGESTED).flat()) {
      expect(answer(q).text).not.toMatch(/Kluger|Seifert|Bowles|Lobell|et al\./);
    }
  });
});
