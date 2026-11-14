/** 11 · Stress test. Owner: Justin. Scenario results come from plan.sections[].stress. */
import { html } from '../lib/html.js';
import { SCORE_KEYS, SCORE_LABELS, STRESS_SCENARIOS } from '../../data/reference/catalog.js';
import { lockReason, placeCrop, toSlots } from '../../application/rules/rotation.js';
import { sectionLayout, pageTitle } from '../ui/layout.js';
import { icon } from '../ui/icons.js';
import { errorBox, loading, roleTag } from '../ui/widgets.js';

const pct = ([a, b]) => (a === 0 && b === 0 ? '±0 %' : `${a} à ${b} %`);

export default {
  title: 'Stress test',
  rota: 'stress',
  render(state, { id }, app) {
    const section = app.section(id);
    const plan = app.sectionPlan(id);
    const cur = state.ui.stressScenario;
    const sc = STRESS_SCENARIOS.find((s) => s.id === cur);
    const years = state.farm.options?.stressYears ?? 1;
    const head = html`${pageTitle('Stress test', 'Et si l’année tournait mal ? Comparez votre rotation au maïs en continu dans quatre situations.')}
      <div class="grid grid--4" role="tablist" aria-label="Scénarios">
        ${STRESS_SCENARIOS.map((s) => html`<button type="button" role="tab" aria-selected="${String(s.id === cur)}" class="scenario ${s.id === cur ? 'is-on' : ''}" data-action="set-scenario" data-s="${s.id}">${icon(s.icon, { size: 26 })}<strong>${s.name}</strong><span class="small">${s.sub}</span></button>`)}
      </div>
      <div class="row-wrap align-center gap-sm card card--dashed">
        <strong class="small">Durée du choc</strong>
        <div class="segmented segmented--inline">
          ${[1, 3].map((n) => html`<button type="button" class="${n === years ? 'is-on' : ''}" data-action="set-stress-years" data-n="${n}" aria-pressed="${String(n === years)}">${n === 1 ? '1 année' : '3 années de suite'}</button>`)}
        </div>
        <span class="small text-warn">À décider en équipe</span>
      </div>`;
    if (!plan)
      return sectionLayout(
        state,
        section,
        'stress',
        html`${head}${state.plan.status === 'error' ? errorBox(state.plan.error) : loading()}`,
      );

    const r = plan.stress[cur];
    const n = plan.stress.normal;
    const tip = plan.suggestions.find((s) => s.scenario === cur);
    const body = html`${head}
      <section class="row-wrap gap-md align-stretch">
        <div class="card grow-2 stack-xs">
          <span class="eyebrow">Le scénario</span><span class="h2 h2--lg">${sc.title}</span>
          <p class="muted">${sc.desc}</p>
          <span class="muted small">Source du scénario : ${sc.source}</span>
        </div>
        <div class="card grow-1 stack-xs justify-center">
          <span class="muted small">Votre rotation</span
          ><span class="big-number big-number--md ${r.yieldPct[1] < -12 ? 'text-bad' : 'text-good'}"
            >${pct(r.yieldPct)}</span
          ><span class="muted small">de rendement</span>
        </div>
        <div class="card grow-1 stack-xs justify-center">
          <span class="muted small">Maïs en continu</span
          ><span
            class="big-number big-number--md ${r.baselineYieldPct[1] < 0 ? 'text-bad' : 'text-good'}"
            >${pct(r.baselineYieldPct)}</span
          ><span class="muted small">de rendement</span>
        </div>
      </section>
      ${
        tip
          ? html`<section class="card card--accent row-wrap align-center gap-md">
              <span
                class="soil-card__icon soil-card__icon--lg"
                style="background: #FAEEDA; color: #633806"
                >${icon(STRESS_SCENARIOS[1].icon, { size: 22 })}</span
              >
              <div class="grow-3 stack-xs">
                <span class="row-wrap gap-sm"><strong>Suggestion</strong>${roleTag('sec')}</span
                ><span class="muted"
                  >${tip.message}${tip.yieldPctAfter ? ` Perte estimée : ${pct(tip.yieldPctAfter)} au lieu de ${pct(r.yieldPct)}.` : ''}</span
                >
              </div>
              <button
                type="button"
                class="btn btn--dark"
                data-action="apply-suggestion"
                data-code="${tip.code}"
              >
                Essayer ce changement
              </button>
            </section>`
          : ''
      }
      <section class="card stack-sm">
        <h2 class="h2">Scores dans ce scénario</h2>
        <div class="table-wrap">
          <table class="table">
            <thead>
              <tr>
                <th>Score</th>
                <th>Année normale</th>
                <th>${sc.title}</th>
                <th>Écart</th>
              </tr>
            </thead>
            <tbody>
              ${SCORE_KEYS.map((k) => {
                const d = r.scores[k] - n.scores[k];
                return html`<tr>
                  <td class="strong">${SCORE_LABELS[k]}</td>
                  <td>${n.scores[k]}</td>
                  <td>
                    <span class="row gap-sm"
                      ><span class="bar bar--inline"
                        ><span
                          class="bar__fill ${d < 0 ? 'is-bad' : 'is-blue'}"
                          style="width: ${r.scores[k]}%"
                        ></span></span
                      >${r.scores[k]}</span
                    >
                  </td>
                  <td class="${d < 0 ? 'text-bad strong' : 'muted'}">
                    ${d === 0 ? '±0' : d > 0 ? `↑ +${d}` : `↓ ${d}`}
                  </td>
                </tr>`;
              })}
            </tbody>
          </table>
        </div>
      </section>
      <div class="actions-bar">
        <a class="btn btn--secondary" href="#/section/${id}/resultats">Retour aux résultats</a
        ><a class="btn btn--primary" href="#/sources">D’où viennent ces chiffres ? →</a>
      </div>`;
    return sectionLayout(state, section, 'stress', body);
  },
  actions: {
    'set-scenario': (app, el) => app.update((s) => (s.ui.stressScenario = el.dataset.s)),
    'set-stress-years': (app, el) =>
      app.updateFarm((farm) => {
        farm.options = { ...(farm.options ?? {}), stressYears: Number(el.dataset.n) };
      }),
    'apply-suggestion': (app, el) => {
      const { id } = app.state.ui.route.params;
      if (el.dataset.code === 'SWAP_MAIS_ORGE') {
        const rot = app.section(id).rotation;
        const i = toSlots(rot).findIndex((s) => s.crop === 'mais');
        if (i >= 0 && !lockReason(rot, i, 'orge')) {
          app.update((s) => {
            s.ui.explorerSnap[id] = structuredClone(rot);
            const p = s.plan.data?.sections.find((x) => x.id === id);
            if (p) s.ui.explorerBase[id] = p.scores;
          });
          app.updateFarm((farm) => {
            const sec = farm.sections.find((x) => x.id === id);
            sec.rotation = placeCrop(sec.rotation, i, 'orge');
          });
        }
      }
      app.go(`#/section/${id}/explorer`);
    },
  },
};
