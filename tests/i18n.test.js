import { afterEach, describe, expect, it } from 'vitest';
import { t, setLanguage, formatNumber, formatDate, translateText } from '../data/i18n/index.js';
import { html, verbatim } from '../frontend/lib/html.js';
import { initialState, persisted } from '../application/state/initialState.js';
import { globalActions } from '../frontend/actions.js';
import { answer, explain } from '../data/reference/rotaAnswers.js';
import { nameOf } from '../data/reference/crops.js';

afterEach(() => setLanguage('en'));
describe('language preferences and presentation', () => {
  it('defaults to English, migrates old preferences and persists French', () => {
    expect(initialState('remote').prefs.language).toBe('en');
    const state = initialState('remote', { prefs: { dashboard: ['sec:B'], language: 'fr' } });
    expect(persisted(state).prefs).toEqual({ dashboard: ['sec:B'], language: 'fr' });
    expect(initialState('remote', { prefs: { language: 'xx' } }).prefs.language).toBe('en');
  });
  it('toggles without altering the route, cycle, year, selected section or farm', () => {
    const state = initialState('remote');
    state.ui.year = 2030;
    state.ui.cycle = 2;
    state.ui.selectedSection = 'C';
    state.ui.route = { name: 'plan', params: { id: 'C' } };
    const before = structuredClone(state);
    globalActions['toggle-language']({ update: (fn) => fn(state) });
    expect(state.prefs.language).toBe('fr');
    expect(state.ui).toEqual(before.ui);
    expect(state.farm).toEqual(before.farm);
  });
  it('uses language-specific plural, decimal, grouping and date rules', () => {
    setLanguage('en');
    expect(t('rotation.count', { count: 0 })).toBe('0 proposed rotations');
    expect(t('rotation.count', { count: 1 })).toBe('1 proposed rotation');
    expect(formatNumber(1234.5)).toBe('1,234.5');
    expect(formatDate('2030-05-01', { month: 'long' })).toBe('May');
    setLanguage('fr');
    expect(t('rotation.count', { count: 0 })).toBe('0 rotation proposée');
    expect(t('rotation.count', { count: 2 })).toBe('2 rotations proposées');
    expect(formatNumber(1234.5)).toMatch(/1\s234,5/);
    expect(formatDate('2030-05-01', { month: 'long' })).toBe('mai');
  });
  it('localises legacy text and accessibility attributes without changing IDs or user text', () => {
    setLanguage('en');
    const page = String(
      html`<button data-action="rota-mvp" data-id="soya" aria-label="Demander à Rota">
          Ma ferme
        </button>
        <p>${verbatim('Ma ferme <script>')}</p>`,
    );
    expect(page).toContain('data-action="rota-mvp" data-id="soya"');
    expect(page).toContain('aria-label="Ask Rota"');
    expect(page).toMatch(/>\s*My farm\s*<\/button>/);
    expect(page).toContain('Ma ferme &lt;script&gt;');
    expect(String(html`<div ${html`aria-hidden="true"`}></div>`)).toContain('aria-hidden="true"');
    expect(String(html`<p>${'<img onerror="evil()">'}</p>`)).not.toContain('<img');
  });
  it('changes crop names and existing French server messages at presentation time', () => {
    setLanguage('en');
    expect(nameOf('ble-automne')).toBe('Winter wheat');
    expect(
      translateText(
        'Soya 2025 puis Soya 2028 : moisissure blanche, 2 ans sans hôte pour 5 conseillés, pression moyenne.',
      ),
    ).toBe(
      'Soybean 2025 then Soybean 2028: white mould, 2 years without a host versus 5 recommended, moderate pressure.',
    );
    setLanguage('fr');
    expect(nameOf('ble-automne')).toBe('Blé d’automne');
  });
  it('understands suggested and free English questions, retaining canonical replies for toggling', () => {
    setLanguage('en');
    expect(answer('What is a climate twin?').text).toBe(explain('jumeaux').text);
    expect(translateText(answer('Tell me about cover crops').text)).toContain('rye');
  });
});
