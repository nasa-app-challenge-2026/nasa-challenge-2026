/**
 * Rota, the assistant: its written answers, and the rule that the screens explain nothing
 * themselves (a « Demander à Rota » button opens Rota on a topic that exists).
 */
import { readFileSync, readdirSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import {
  INTENTS,
  OUT_OF_MVP,
  SUGGESTED,
  TOPICS,
  answer,
  explain,
} from '../data/reference/rotaAnswers.js';
import { FIELD_MEASURES } from '../data/reference/fieldMeasures.js';

const REPO = new URL('../', import.meta.url);
const STUDY_NAMES = /Fitzpatrick|Peltonen|Pahmeyer|McGrath|Thrasher|Poggio|et al\./;

/** Every .js file of a folder of the repository, with its text. */
function sourcesOf(folder) {
  return readdirSync(new URL(folder, REPO), { recursive: true })
    .filter((name) => name.endsWith('.js'))
    .map((name) => ({
      name: `${folder}${name}`,
      text: readFileSync(new URL(`${folder}${name}`, REPO), 'utf8'),
    }));
}

describe('Rota', () => {
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

  it('answers the question of a topic with the text of that topic', () => {
    expect(answer('Comment lire la roue ?').text).toBe(TOPICS.roue.text);
    expect(explain('roue')).toEqual({ q: TOPICS.roue.q, text: TOPICS.roue.text, sources: false });
    expect(explain('sujet-inconnu')).toBeNull();
  });

  it('never names a study in an answer (team rule)', () => {
    const texts = [...Object.values(TOPICS), ...INTENTS].map((entry) => entry.text);
    for (const text of texts) expect(text).not.toMatch(STUDY_NAMES);
  });

  it('says a feature the MVP does not have is out of the MVP', () => {
    expect(OUT_OF_MVP).toBe('Hors de portée du MVP.');
  });
});

describe('the screens explain nothing themselves', () => {
  const screens = sourcesOf('frontend/');

  it('every « Demander à Rota » button of a screen opens a topic Rota knows', () => {
    const asked = screens.flatMap(({ name, text }) =>
      [...text.matchAll(/askRota(?:Icon)?\(\s*'([^']+)'/g)].map(([, topic]) => ({ name, topic })),
    );
    expect(asked.length).toBeGreaterThan(20);
    for (const { name, topic } of asked) expect(TOPICS[topic], `${topic} (${name})`).toBeDefined();
    for (const key of Object.keys(FIELD_MEASURES)) expect(TOPICS[`mesure-${key}`]).toBeDefined();
  });

  it('every topic has a question and an answer', () => {
    for (const [id, topic] of Object.entries(TOPICS)) {
      expect(topic.q, id).toMatch(/ \?$/);
      expect(topic.text.length, id).toBeGreaterThan(40);
    }
  });

  it('nothing says "coming soon", and the assistant is called Rota', () => {
    const texts = [...screens, ...sourcesOf('data/'), ...sourcesOf('application/')];
    for (const { name, text } of texts) {
      expect(text, name).not.toMatch(/bient[oô]t/i);
      expect(text, name).not.toMatch(/RotaAI/);
    }
  });
});
