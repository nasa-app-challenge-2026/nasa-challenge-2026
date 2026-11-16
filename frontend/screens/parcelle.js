/**
 * 8 · Ma parcelle. Owner: Ali. Everything the farmer knows about one section
 * (step 1, block A): crop in place and harvest month, current rotation, previous
 * years (as many as the return delays need), soil diseases, irrigation, soil test.
 */
import { html } from '../lib/html.js';
import { MIN_HISTORY_YEARS } from '../../data/reference/planning.js';
import { SOIL_PROPERTIES } from '../../data/reference/fieldMeasures.js';
import { sectionInputProblems } from '../../application/rules/sectionInputs.js';
import { sectionLayout, pageTitle } from '../ui/layout.js';
import { alertBox, switchButton } from '../ui/widgets.js';
import { askRota, askRotaIcon } from '../ui/rota.js';
import { diseasesEditor, historyEditor, inPlaceEditor, seedActions } from '../ui/seedsEditor.js';

/** Typical soil of the region, proposed when the farmer starts a soil test. */
const SOIL_TEST_START = { clayPct: 30, sandPct: 25, organicCarbon: 25, ph: 6.5 };

function soilTestEditor(section) {
  if (!section.soilTest)
    return html`<button
      type="button"
      class="btn btn--secondary btn--sm"
      data-action="start-soil-test"
      data-id="${section.id}"
    >
      J’ai une analyse de sol
    </button>`;
  return html`<div class="stack-sm">
    <div class="row-wrap gap-sm">
      ${Object.entries(SOIL_PROPERTIES).map(
        ([key, p]) =>
          html`<label class="field field--narrow"
            >${p.label}${p.unit ? ` (${p.unit})` : ''}
            <input
              type="number"
              step="0.1"
              id="soil-${section.id}-${key}"
              value="${section.soilTest[key]}"
              data-change="set-soil"
              data-id="${section.id}"
              data-key="${key}"
            />
          </label>`,
      )}
    </div>
    <button
      type="button"
      class="link-btn small"
      data-action="clear-soil-test"
      data-id="${section.id}"
    >
      Utiliser SoilGrids à la place
    </button>
  </div>`;
}

export default {
  title: 'Ma parcelle',
  rota: 'parcelle',
  render(state, { id }, app) {
    const section = app.section(id);
    const plan = app.sectionPlan(id);
    const currentYear = state.plan.data?.settings.currentYear ?? new Date().getFullYear();
    const years = plan?.historyYears ?? MIN_HISTORY_YEARS;
    const body = html`${pageTitle(`Ma parcelle ${id}`, '', askRota('parcelle'))}
      <section class="card stack-md">
        <div class="step-head">
          <span class="step-num">1</span>
          <h2 class="h2">Aujourd’hui</h2>
        </div>
        ${inPlaceEditor(section)} ${sectionInputProblems(section).map((p) => alertBox('warn', p))}
        ${plan?.repeatsCurrentCrop ? alertBox('warn', 'Pas de rotation actuelle : la culture en place sert de comparaison.') : ''}
      </section>
      <section class="card stack-md">
        <div class="step-head">
          <span class="step-num">2</span>
          <h2 class="h2">Les années précédentes</h2>
          ${askRotaIcon('historique')}
        </div>
        ${historyEditor(section, { currentYear, years })}
      </section>
      <section class="card stack-md">
        <div class="step-head">
          <span class="step-num">3</span>
          <h2 class="h2">Maladies du sol connues</h2>
          ${askRotaIcon('maladies')}
        </div>
        ${diseasesEditor(section)}
      </section>
      <section class="card stack-md">
        <div class="step-head">
          <span class="step-num">4</span>
          <h2 class="h2">Eau et sol</h2>
          ${askRotaIcon('analyse-sol')}
        </div>
        <div class="toggle-card">
          <span class="row gap-xs grow"
            ><strong class="small">Parcelle irriguée</strong>${askRotaIcon('irrigation')}</span
          >
          ${switchButton(section.irrigated, 'toggle-irrigated', 'Parcelle irriguée', html`data-id="${id}"`)}
        </div>
        ${soilTestEditor(section)}
      </section>
      <div class="actions-bar">
        <a class="btn btn--primary" href="#/section/${id}/plan">Consulter la rotation →</a>
      </div>`;
    return sectionLayout(state, section, 'parcelle', body);
  },
  actions: {
    ...seedActions,
    'toggle-irrigated': (app, el) =>
      app.updateSection(el.dataset.id, (s) => (s.irrigated = !s.irrigated)),
    'start-soil-test': (app, el) =>
      app.updateSection(el.dataset.id, (s) => (s.soilTest = { ...SOIL_TEST_START })),
    'clear-soil-test': (app, el) => app.updateSection(el.dataset.id, (s) => (s.soilTest = null)),
    'set-soil': (app, el) =>
      app.updateSection(el.dataset.id, (s) => {
        const value = Number(el.value);
        if (Number.isFinite(value)) s.soilTest = { ...s.soilTest, [el.dataset.key]: value };
      }),
  },
};
