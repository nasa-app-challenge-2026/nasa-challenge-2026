/**
 * 9 · Mon champ. Owner: Justin. The weak points of the section (step 8 of the
 * algorithm): erosion and water risks, the satellite measures behind them, and
 * the soil (step 5). Values come from the plan (FarmPlan.sections[].field).
 */
import { html } from '../lib/html.js';
import { nameOf } from '../../data/reference/crops.js';
import { FIELD_MEASURES, RISKS, SOIL_PROPERTIES } from '../../data/reference/fieldMeasures.js';
import { cropOfYear, planYears } from '../../application/rules/planView.js';
import { sectionLayout, pageTitle } from '../ui/layout.js';
import { errorBox, infoButton, loading } from '../ui/widgets.js';
import { farmPlan } from '../ui/farmPlan.js';
import { selectedYear } from '../ui/planWidgets.js';

const PERCENT = 100;
const DECIMAL_COMMA = (v) => String(v).replace('.', ',');

function riskCard(key, value) {
  const pct = Math.round(value * PERCENT);
  return html`<div class="card stack-xs">
    <span class="muted small">${RISKS[key].label}</span>
    <span class="h1 ${pct >= 50 ? 'text-warn' : ''}">${pct} %</span>
    <div class="bar">
      <div class="bar__fill ${pct >= 50 ? 'is-bad' : 'is-blue'}" style="width: ${pct}%"></div>
    </div>
    <span class="muted small"
      >Plus le risque est haut, plus ce critère pèse dans la note du plan.</span
    >
  </div>`;
}

function measureCard(state, sectionId, key, value) {
  const m = FIELD_MEASURES[key];
  const infoKey = `${sectionId}:${key}`;
  const open = state.ui.openInfo === infoKey;
  const reported = !!state.ui.reported[infoKey];
  return html`<article class="card metric">
    <div class="row-between">
      <span class="strong muted">${m.label}</span
      >${infoButton('toggle-info', m.label, html`data-key="${infoKey}" aria-expanded="${String(open)}"`)}
    </div>
    <div class="metric__value">
      <span>${DECIMAL_COMMA(value)}</span><span class="muted">${m.unit}</span>
    </div>
    ${open ? html`<p class="explain">${m.explain}</p>` : ''}
    <div class="row-between divider-top">
      <span class="small muted"
        >${m.source} · risque ${m.risk === 'erosion' ? 'érosion' : 'eau'}</span
      >
      <button
        type="button"
        class="report-btn ${reported ? 'is-on' : ''}"
        data-action="toggle-report"
        data-key="${infoKey}"
      >
        ${reported ? '✓ Signalé' : '⚑ Signaler'}
      </button>
    </div>
  </article>`;
}

export default {
  title: 'Mon champ',
  rota: 'champ',
  render(state, { id }, app) {
    const section = app.section(id);
    const plan = app.sectionPlan(id);
    const year = selectedYear(state, planYears(state.plan.data));
    const f = state.farm.farm.time.frequencyMonths;
    const cropOf = (sid) => cropOfYear(app.section(sid), app.sectionPlan(sid), year, f).id;
    const crop = cropOf(id);
    const map = farmPlan({
      sections: state.farm.sections,
      boundary: state.farm.farm.boundary,
      cropOf,
      selectedId: id,
      label: `Carte de la section ${id} en ${year}`,
    });
    const field = plan?.field;
    const content = field
      ? html`<div class="grid grid--2">
            ${riskCard('erosion', field.risksToday.erosion)}${riskCard('water', field.risksToday.water)}
          </div>
          <div class="grid grid--metrics">
            ${Object.entries(field.measures).map(([k, v]) => measureCard(state, id, k, v))}
          </div>
          <section class="card stack-sm">
            <div class="row-between wrap">
              <h2 class="h2">Le sol (0 à 30 cm)</h2>
              <span class="muted small">${field.soil.source}</span>
            </div>
            <div class="row-wrap gap-md">
              ${Object.entries(SOIL_PROPERTIES).map(([k, p]) => html`<div class="stack-0"><span class="muted small">${p.label}</span><strong>${DECIMAL_COMMA(field.soil[k])} ${p.unit}</strong></div>`)}
            </div>
            <span class="muted small"
              >Le sol sert à garder, chez les jumeaux climatiques, les champs au même sol que le
              vôtre. <a href="#/section/${id}/parcelle">Saisir mon analyse de sol</a></span
            >
          </section>`
      : state.plan.status === 'error'
        ? errorBox(state.plan.error)
        : loading('Lecture des données satellites…');
    const body = html`${pageTitle('Mon champ', `Les points faibles de la section ${id}, vus par satellite. Le risque d’eau ci-dessous ne compte pas encore la baisse de pluie prévue par cycle (voir le plan).`)}
      <div class="row-wrap align-start gap-lg">
        <div class="grow-3 stack-md">${content}</div>
        <div class="card card--flush grow-1 section-map">
          ${map ?? html`<div class="pad muted small">Section non tracée. <a href="#/tracer">Tracer cette section</a></div>`}
          <div class="pad stack-0">
            <strong
              >Section ${id} · ${section.areaHa} ha · ${crop ? nameOf(crop).toLowerCase() : 'rien'}
              en ${year}</strong
            >
            <span class="muted small">${section.note ?? ''}</span>
          </div>
        </div>
      </div>
      <div class="actions-bar">
        <a class="btn btn--secondary" href="#/section/${id}/parcelle">Ma parcelle</a
        ><a class="btn btn--primary" href="#/section/${id}/plan">Voir le plan →</a>
      </div>`;
    return sectionLayout(state, section, 'champ', body);
  },
  actions: {
    'toggle-info': (app, el) =>
      app.update((s) => (s.ui.openInfo = s.ui.openInfo === el.dataset.key ? null : el.dataset.key)),
    'toggle-report': (app, el) =>
      app.update((s) => (s.ui.reported[el.dataset.key] = !s.ui.reported[el.dataset.key])),
  },
};
