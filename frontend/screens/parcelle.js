/**
 * 8 · Ma parcelle. Owner: Ali. Everything the farmer knows about one section
 * (step 1, block A): crop in place and harvest month, current rotation, previous
 * years (as many as the return delays need), soil diseases, irrigation, soil test.
 */
import { html } from '../lib/html.js';
import { CROPS } from '../../data/reference/crops.js';
import { MIN_HISTORY_YEARS } from '../../data/reference/planning.js';
import { SOIL_PROPERTIES } from '../../data/reference/fieldMeasures.js';
import { sectionInputProblems } from '../../application/rules/sectionInputs.js';
import { sectionLayout, pageTitle } from '../ui/layout.js';
import { alertBox, switchButton } from '../ui/widgets.js';
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
    const body = html`${pageTitle(`Ma parcelle ${id}`, 'Ce que vous savez de cette section. Tout se recalcule dès que vous changez quelque chose.')}
      <section class="card stack-md">
        <div class="step-head">
          <span class="step-num">1</span>
          <h2 class="h2">Aujourd’hui</h2>
        </div>
        ${inPlaceEditor(section)} ${sectionInputProblems(section).map((p) => alertBox('warn', p))}
        ${plan?.repeatsCurrentCrop ? alertBox('warn', 'Sans rotation actuelle, l’appli compare son plan à la culture en place répétée chaque année.') : ''}
      </section>
      <section class="card stack-md">
        <div class="step-head">
          <span class="step-num">2</span>
          <h2 class="h2">Les années précédentes</h2>
          <span class="muted small"
            >${years} années : le plus long délai de retour des cultures possibles</span
          >
        </div>
        ${historyEditor(section, { currentYear, years })}
        ${
          plan?.history.length
            ? html`<span class="muted small"
                >L’algorithme lit :
                ${plan.history.map((h) => `${CROPS[h.crop]?.name ?? h.crop} ${h.from === h.to ? h.from : `${h.from}–${h.to}`}`).join(' · ')}</span
              >`
            : ''
        }
      </section>
      <section class="card stack-md">
        <div class="step-head">
          <span class="step-num">3</span>
          <h2 class="h2">Maladies du sol connues</h2>
        </div>
        <span class="muted small"
          >Une maladie déclarée rend obligatoire son délai le plus long pour toutes ses
          cultures-hôtes (ex. hernie : 7 ans sans crucifère).</span
        >
        ${diseasesEditor(section)}
      </section>
      <section class="card stack-md">
        <div class="step-head">
          <span class="step-num">4</span>
          <h2 class="h2">Eau et sol</h2>
        </div>
        <div class="toggle-card">
          <span class="stack-0"
            ><strong class="small">Parcelle irriguée</strong
            ><span class="muted small">Le risque de manque d’eau est réduit</span></span
          >
          ${switchButton(section.irrigated, 'toggle-irrigated', 'Parcelle irriguée', html`data-id="${id}"`)}
        </div>
        ${soilTestEditor(section)}
      </section>
      <div class="actions-bar">
        <a class="btn btn--secondary" href="#/tableau">Retour</a
        ><a class="btn btn--primary" href="#/section/${id}/plan">Voir le plan →</a>
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
