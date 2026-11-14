/** 9 · Résultats d'une section. Owner: Justin. Everything here comes from the engine (FarmPlan). */
import { html, fmt } from '../lib/html.js';
import { CROPS, COVERS, ROLES, SOIL_ROLES } from '../../data/reference/crops.js';
import { BASELINES, SCORE_KEYS, SCORE_LABELS } from '../../data/reference/catalog.js';
import { buildCalendar } from '../../application/rules/rotation.js';
import { soilByCalendar, countTrue } from '../../application/rules/soil.js';
import { sectionLayout, pageTitle } from '../ui/layout.js';
import { icon } from '../ui/icons.js';
import { errorBox, loading, scoreBar } from '../ui/widgets.js';
import { revenueChart } from '../ui/revenueChart.js';

const CONF = { elevee: 'élevée', moyenne: 'moyenne', faible: 'faible' };
const WORK = { faible: 'Faible', moyenne: 'Moyenne', elevee: 'Élevée' };
const range = ([a, b]) => `${a >= 0 ? '+' : ''}${a} à ${b >= 0 ? '+' : ''}${b} %`;

export function rotationLabel(rotation) {
  return rotation
    .map(
      (e) =>
        `${CROPS[e.crop]?.name ?? '—'}${e.years > 1 ? ` (${e.years} ans)` : ''}${e.cover ? ` (+ ${COVERS[e.cover].name.toLowerCase()} l’hiver)` : ''}`,
    )
    .join(' → ');
}

export default {
  title: 'Résultats',
  rota: 'resultats',
  render(state, { id }, app) {
    const section = app.section(id);
    const plan = app.sectionPlan(id);
    const base = state.ui.compare;
    const H = state.farm.farm.horizonYears;
    const head = pageTitle(
      'Résultats de votre rotation',
      rotationLabel(section.rotation),
      html`<div class="segmented segmented--inline" role="group" aria-label="Comparer avec">
        <span class="muted small pad-x">Comparer avec</span
        >${Object.entries(BASELINES).map(([k, b]) => html`<button type="button" class="${k === base ? 'is-on' : ''}" data-action="set-compare" data-k="${k}" aria-pressed="${String(k === base)}">${b.label}</button>`)}
      </div>`,
    );
    if (!plan) {
      const content =
        state.plan.status === 'error'
          ? errorBox(state.plan.error)
          : state.plan.status === 'incomplete'
            ? html`<div class="alert alert--warn">
                ⚠ Une section a une année sans culture : terminez sa rotation pour voir les
                résultats.
              </div>`
            : loading();
      return sectionLayout(state, section, 'resultats', html`${head}${content}`);
    }
    const cmp = plan.comparisons[base];
    const cal = buildCalendar(section.rotation, {
      offset: section.offset,
      startYear: state.farm.farm.startYear,
      horizonYears: H,
    });
    const soil = soilByCalendar(cal);
    const role = SOIL_ROLES.includes(state.ui.role) ? state.ui.role : 'azote';
    const body = html`${head}
      <section class="row-wrap gap-md align-stretch">
        <div class="card card--dark grow-2 stack-xs">
          <span class="small">Rendement moyen par rapport à ${BASELINES[base].name}</span>
          <span class="big-number">${range(cmp.yieldGainPct)}</span>
          <span class="small"
            >Fourchette selon les années. Confiance : <strong>${CONF[plan.confidence]}</strong>. Les
            chiffres viennent d’études publiées et des données NASA de votre section (voir Détail et
            sources).</span
          >
        </div>
        <div class="card grow-1 stack-xs justify-center">
          <span class="muted small">Revenu moyen par année</span
          ><span class="h1">${fmt(plan.revenue.perHaYear)} $/ha</span
          ><span class="${cmp.revenueDeltaPerHaYear >= 0 ? 'text-good' : 'text-bad'} strong small"
            >${cmp.revenueDeltaPerHaYear >= 0 ? '↑ +' : '↓ '}${fmt(cmp.revenueDeltaPerHaYear)} $/ha
            par an</span
          >
        </div>
        <div class="card grow-1 stack-xs justify-center">
          <span class="muted small">Charge de travail</span
          ><span class="h1 ${plan.workload === 'faible' ? '' : 'text-warn'}"
            >${plan.workload === 'faible' ? '✓' : '⚠'} ${WORK[plan.workload]}</span
          ><span class="muted small"
            >${new Set(section.rotation.map((e) => e.crop)).size} cultures différentes à semer et
            récolter</span
          >
        </div>
      </section>
      <section class="row-wrap gap-md align-stretch">
        <div class="card grow-1 stack-md">
          <h2 class="h2">Scores sur 100</h2>
          ${SCORE_KEYS.map((k) => scoreBar(SCORE_LABELS[k], plan.scores[k], { reference: cmp.scores[k], delta: plan.scores[k] - cmp.scores[k] }))}
          <span class="muted small">Trait noir = ${BASELINES[base].name}</span>
        </div>
        <div class="card grow-2 stack-sm">
          <div class="row-between wrap">
            <h2 class="h2">Revenu sur ${H} ans</h2>
            <span class="legend"
              ><span><i class="legend__line"></i>Votre rotation</span
              ><span><i class="legend__dash"></i>${BASELINES[base].label}</span></span
            >
          </div>
          ${revenueChart(plan.revenue.series, plan.revenue.baselines[base], BASELINES[base].name)}
          <span class="muted small"
            >Zone bleue = fourchette selon la météo. Revenu net par hectare.</span
          >
        </div>
      </section>
      <section class="card stack-md">
        <div class="row-between wrap">
          <h2 class="h2">Santé du sol sur ${H} ans</h2>
          <span class="muted small">Chaque barre = une année · cliquez pour comprendre</span>
        </div>
        <div class="grid grid--4">
          ${SOIL_ROLES.map((r) => {
            const R = ROLES[r];
            const n = countTrue(soil[r]);
            return html`<button
              type="button"
              class="soil-card ${r === role ? 'is-active' : ''}"
              data-action="set-role"
              data-role="${r}"
            >
              <span class="row gap-sm strong"
                ><span class="soil-card__icon" style="background: ${R.bg}; color: ${R.fg}"
                  >${icon(R.icon, { size: 16, width: 2.2 })}</span
                >${R.label}</span
              >
              <span class="soil-card__count">${n} ans sur ${H}</span>
              <span class="dots"
                >${soil[r].map((v) => html`<span style="background: ${v ? R.fg : '#E5E9E0'}"></span>`)}</span
              >
            </button>`;
          })}
        </div>
        <div class="card card--soft row-start">
          <span class="info-dot">i</span>
          <p class="small"><strong>${ROLES[role].label} :</strong> ${ROLES[role].text}</p>
        </div>
        ${plan.suggestions.filter((s) => !s.scenario).map((s) => html`<div class="alert alert--warn"><span aria-hidden="true">⚠</span><span class="grow">${s.message}</span><a href="#/section/${id}/rotation" class="strong">Essayer dans Rotation →</a></div>`)}
      </section>
      ${
        plan.explanations.length
          ? html`<section class="card stack-sm">
              <h2 class="h2">Pourquoi ces chiffres</h2>
              ${plan.explanations.map((e) => html`<p class="bullet">${e.message}</p>`)}
            </section>`
          : ''
      }
      <div class="actions-bar">
        <a class="btn btn--secondary" href="#/section/${id}/rotation">Modifier la rotation</a
        ><a class="btn btn--secondary" href="#/section/${id}/stress">Faire un stress test</a
        ><a class="btn btn--primary" href="#/tableau">Garder cette rotation ✓</a>
      </div>`;
    return sectionLayout(state, section, 'resultats', body);
  },
  actions: {
    'set-compare': (app, el) => app.update((s) => (s.ui.compare = el.dataset.k)),
  },
};
