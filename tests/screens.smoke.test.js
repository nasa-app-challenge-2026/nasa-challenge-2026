/**
 * The screens render the example plan of the contract without error, and show what the challenge
 * asks for: at least three rotations proposed for every cycle, each one easy to recognise, the
 * four priorities, the water and the pests of the rotation shown.
 */
import { readFileSync, readdirSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { initialState } from '../application/state/initialState.js';
import {
  REFERENCE_OPTION,
  proposedRotations,
  shownRotation,
} from '../application/rules/planView.js';
import { CRITERIA, CRITERIA_IDS } from '../data/reference/criteria.js';
import { FARM_TYPES } from '../data/reference/catalog.js';
import champ from '../frontend/screens/champ.js';
import compte from '../frontend/screens/compte.js';
import cultures from '../frontend/screens/cultures.js';
import parcelle from '../frontend/screens/parcelle.js';
import plan from '../frontend/screens/plan.js';
import priorites from '../frontend/screens/priorites.js';
import sources from '../frontend/screens/sources.js';
import tableau from '../frontend/screens/tableau.js';
import temps from '../frontend/screens/temps.js';
import typeFerme from '../frontend/screens/typeFerme.js';
import { rotationWheel } from '../frontend/ui/rotationViews.js';

const EXAMPLES = new URL('../backend/contract/examples/', import.meta.url);
const example = (name) => JSON.parse(readFileSync(new URL(name, EXAMPLES), 'utf8'));
const examplePlans = readdirSync(EXAMPLES).filter((name) => name.endsWith('.plan.json'));

function stateWithPlan() {
  const state = initialState('remote', null);
  state.plan = { status: 'ready', data: example('ferme-demo.plan.json'), error: null };
  return state;
}

const appOf = (state) => ({
  section: (id) => state.farm.sections.find((s) => s.id === id),
  sectionPlan: (id) => state.plan.data?.sections.find((s) => s.id === id),
});

const render = (screen, state, params = {}) => String(screen.render(state, params, appOf(state)));
const count = (page, pattern) => (page.match(pattern) ?? []).length;

describe('three rotations are proposed for every cycle', () => {
  it.each(examplePlans)('%s: each cycle of each section proposes at least three', (name) => {
    for (const section of example(name).sections)
      for (const cycle of section.cycles)
        expect(proposedRotations(cycle).length, `${section.id} cycle ${cycle.index}`).toBe(3);
  });

  it('the plan screen shows them side by side, each with its wheel and its four priorities', () => {
    const page = render(plan, stateWithPlan(), { id: 'A' });
    expect(page).toContain('3 rotations proposées');
    for (const title of ['Rotation 1', 'Rotation 2', 'Rotation 3']) expect(page).toContain(title);
    expect(count(page, /class="rot-card /g)).toBe(3);
    expect(count(page, /class="wheel"/g)).toBe(3);
    expect(count(page, /★ Recommandée/g)).toBe(1);
    for (const id of CRITERIA_IDS) expect(page).toContain(CRITERIA[id].short);
    expect(page).toContain('Votre rotation actuelle');
  });

  it('the wheel has one slice per crop, in the order of the chain', () => {
    const [cycle] = example('ferme-demo.plan.json').sections[0].cycles;
    const wheel = String(rotationWheel(cycle.chosen, { positions: 4 }));
    const crops = cycle.chosen.steps.filter((s) => s.kind !== 'couvert');
    expect(count(wheel, /class="wheel__slice"/g)).toBe(crops.length);
    expect(wheel).toContain(`>${Math.round(cycle.chosen.score)}</text`);
    expect(wheel).toContain('aria-label="Rotation : ');
  });
});

describe('the rotation shown in detail', () => {
  it('is the recommended one at first: its crops, its four priorities, its water, its pests', () => {
    const page = render(plan, stateWithPlan(), { id: 'A' });
    expect(page).toMatch(/Rotation 1 · \d+ sur 100/);
    expect(page).toContain('Les 4 priorités');
    for (const id of CRITERIA_IDS) expect(page).toContain(CRITERIA[id].label);
    expect(page).toMatch(/Eau · \d+ sur 100/);
    expect(page).toMatch(/Ravageurs · \d+ sur 100/);
    expect(page).toContain('moisissure blanche');
    expect(page).not.toContain('9 critères');
  });

  it('changes when the farmer touches another rotation, or his current one', () => {
    const state = stateWithPlan();
    state.ui.option = 1;
    expect(render(plan, state, { id: 'A' })).toMatch(/Rotation 2 · \d+ sur 100/);
    state.ui.option = REFERENCE_OPTION;
    expect(render(plan, state, { id: 'A' })).toMatch(/Votre rotation actuelle · \d+ sur 100/);
  });

  it('falls back on what the cycle has', () => {
    const [cycle] = example('ferme-demo.plan.json').sections[0].cycles;
    expect(shownRotation(cycle, 7)).toEqual({ id: 0, chain: cycle.chosen });
    expect(shownRotation(cycle, REFERENCE_OPTION).chain).toBe(cycle.reference);
    const empty = { chosen: null, alternatives: [], reference: cycle.reference };
    expect(shownRotation(empty, 0)).toEqual({ id: REFERENCE_OPTION, chain: cycle.reference });
    expect(shownRotation({ ...empty, reference: null }, 0)).toBeNull();
  });
});

describe('the other screens', () => {
  it('the priorities screen lists the four priorities with the weights of the plan', () => {
    const page = render(priorites, stateWithPlan());
    for (const id of CRITERIA_IDS) expect(page).toContain(CRITERIA[id].label);
    expect(page).toContain('52 %');
    expect(page).not.toMatch(/bétail|Fourrage|Non classés/);
  });

  it('the settings show the same priorities', () => {
    const state = stateWithPlan();
    state.ui.settingsTab = 'prio';
    const page = render(compte, state);
    for (const id of CRITERIA_IDS) expect(page).toContain(CRITERIA[id].label);
  });

  it('my field shows the two risks, the measures, the water pressure and the soil', () => {
    const page = render(champ, stateWithPlan(), { id: 'A' });
    for (const text of ['Risque d’érosion', 'Risque de manque d’eau', 'Pression sur l’eau', 'Sol'])
      expect(page).toContain(text);
    expect(page).toContain('data-topic="risques"');
  });

  it('the dashboard shows every section with the rotation of its cycle', () => {
    const state = stateWithPlan();
    const page = render(tableau, state);
    expect(count(page, /class="rot-strip /g)).toBe(state.farm.sections.length);
    expect(page).toContain('Voir les rotations');
  });

  it('the dashboard puts the weather on top, then the 3D farm (with its pie) left of the sections', () => {
    const page = render(tableau, stateWithPlan());
    const at = (text) => page.indexOf(text);
    expect(at('Météo à la ferme')).toBeGreaterThan(-1);
    expect(at('Météo à la ferme')).toBeLessThan(at('Ma ferme en 3D'));
    expect(at('Ma ferme en 3D')).toBeLessThan(at('class="dash-sections"'));
    // The pie chart of the crops of the year is inside the 3D view, before the section cards.
    expect(at('data-farm3d')).toBeLessThan(at('class="pie"'));
    expect(at('class="pie"')).toBeLessThan(at('class="dash-sections"'));
    expect(count(page, /class="pie__slice"/g)).toBeGreaterThan(1);
  });

  it('a farm type out of the MVP opens Rota instead of saying "coming soon"', () => {
    const page = render(typeFerme, stateWithPlan());
    const outOfMvp = FARM_TYPES.filter((type) => !type.available);
    expect(count(page, /data-action="rota-mvp"/g)).toBe(outOfMvp.length);
    for (const type of outOfMvp) expect(page).toContain(`data-what="${type.name}"`);
  });

  it('waiting for the plan shows the little field that grows, not a bare text', () => {
    const state = initialState('remote', null);
    state.plan.status = 'loading';
    for (const page of [render(tableau, state), render(plan, state, { id: 'A' })]) {
      expect(page).toContain('class="loader"');
      expect(count(page, /class="loader__sprout"/g)).toBe(4);
    }
  });

  it.each([
    ['parcelle', parcelle, { id: 'A' }],
    ['cultures', cultures, {}],
    ['temps', temps, {}],
    ['sources', sources, {}],
  ])('%s renders with a « Demander à Rota » button', (_name, screen, params) => {
    expect(render(screen, stateWithPlan(), params)).toContain('data-action="rota-explain"');
  });
});
