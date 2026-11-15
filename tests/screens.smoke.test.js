/**
 * The screens that show the priorities and the plan render the example plan of the contract
 * without error, and say what the algorithm scores: four priorities, the water of the chain.
 */
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { initialState } from '../application/state/initialState.js';
import { CRITERIA, CRITERIA_IDS } from '../data/reference/criteria.js';
import champ from '../frontend/screens/champ.js';
import compte from '../frontend/screens/compte.js';
import plan from '../frontend/screens/plan.js';
import priorites from '../frontend/screens/priorites.js';

const example = (name) =>
  JSON.parse(
    readFileSync(new URL(`../backend/contract/examples/${name}`, import.meta.url), 'utf8'),
  );

function stateWithPlan() {
  const state = initialState('remote', null);
  state.plan = { status: 'ready', data: example('ferme-demo.plan.json'), error: null };
  return state;
}

const appOf = (state) => ({
  section: (id) => state.farm.sections.find((s) => s.id === id),
  sectionPlan: (id) => state.plan.data?.sections.find((s) => s.id === id),
});

describe('the screens of the priorities and the plan', () => {
  it('the priorities screen lists the four priorities with the weights of the plan', () => {
    const state = stateWithPlan();
    const page = String(priorites.render(state, {}, appOf(state)));
    for (const id of CRITERIA_IDS) expect(page).toContain(CRITERIA[id].label);
    expect(page).toContain('52 %');
    expect(page).not.toMatch(/bétail|Fourrage|Non classés/);
  });

  it('the settings show the same priorities', () => {
    const state = stateWithPlan();
    state.ui.settingsTab = 'prio';
    const page = String(compte.render(state, {}, appOf(state)));
    for (const id of CRITERIA_IDS) expect(page).toContain(CRITERIA[id].label);
  });

  it('the plan of a section shows the four priorities, the water and the pests of its chain', () => {
    const state = stateWithPlan();
    const page = String(plan.render(state, { id: 'A' }, appOf(state)));
    expect(page).toContain('Les 4 priorités');
    for (const id of CRITERIA_IDS) expect(page).toContain(CRITERIA[id].label);
    expect(page).toContain('L’eau de cette suite');
    expect(page).toContain('Les ravageurs de cette suite');
    expect(page).toContain('moisissure blanche');
    expect(page).not.toContain('9 critères');
  });

  it('my field names the priority each risk gives more weight to', () => {
    const state = stateWithPlan();
    const page = String(champ.render(state, { id: 'A' }, appOf(state)));
    expect(page).toContain('« Protection du sol »');
    expect(page).toContain('« Utilisation de l’eau »');
    expect(page).toContain('La pression sur l’eau');
  });
});
