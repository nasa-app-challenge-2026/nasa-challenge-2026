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
    expect(answer('C’EST QUOI UN DÉLAI DE RETOUR').text).toMatch(/délai de retour/);
    expect(answer('c est quoi un jumeau climatique').text).toMatch(/jumeau climatique/);
  });

  it('falls back politely on unknown questions', () => {
    expect(answer('quelle heure est-il ?').text).toMatch(/pas encore de réponse/);
  });

  it('never names a study in an answer (team rule)', () => {
    for (const q of Object.values(SUGGESTED).flat()) {
      expect(answer(q).text).not.toMatch(
        /Fitzpatrick|Peltonen|Pahmeyer|McGrath|Thrasher|Poggio|et al\./,
      );
    }
  });
});
