/**
 * 10 · Explorer et modifier. Owner: Justin.
 * Click a year to change its crop; the engine re-evaluates and the scores move.
 * Priorities are intentionally not shown here (team decision).
 */
import { html } from '../lib/html.js';
import { CROPS, CROP_IDS } from '../../data/reference/crops.js';
import { SCORE_KEYS, SCORE_LABELS } from '../../data/reference/catalog.js';
import { placeCrop, rotationErrors, toSlots } from '../../application/rules/rotation.js';
import { sectionLayout, pageTitle } from '../ui/layout.js';
import { fieldStrip } from '../ui/textures.js';
import { alertBox, loading, scoreBar } from '../ui/widgets.js';

const ONE_YEAR = CROP_IDS.filter((c) => CROPS[c].years === 1);
const WORK = { faible: 'Faible', moyenne: 'Moyenne', elevee: 'Élevée' };

export default {
  title: 'Explorer et modifier',
  rota: 'rotation',
  onEnter(app, { id }) {
    app.update((s) => {
      if (!s.ui.explorerSnap[id]) {
        s.ui.explorerSnap[id] = structuredClone(s.farm.sections.find((x) => x.id === id).rotation);
        const p = s.plan.data?.sections.find((x) => x.id === id);
        if (p) s.ui.explorerBase[id] = p.scores;
      }
    });
  },
  render(state, { id }, app) {
    const section = app.section(id);
    const plan = app.sectionPlan(id);
    const base = state.ui.explorerBase[id];
    const slots = toSlots(section.rotation);
    const errors = rotationErrors(section.rotation);
    const cmp = plan?.comparisons['mais-continu'];
    const body = html` ${pageTitle('Explorer et modifier', 'Cliquez sur une année pour changer sa culture. Tout se recalcule en direct.')}
      <div class="row-wrap align-start gap-lg">
        <div class="grow-2 stack-md">
          <section class="card stack-md">
            <div class="row-between wrap">
              <h2 class="h2">Votre cycle de ${slots.length} ans</h2>
              <button type="button" class="btn btn--secondary btn--sm" data-action="reset-explorer">
                Annuler les changements
              </button>
            </div>
            <div
              class="explore-grid"
              style="grid-template-columns: repeat(${slots.length}, minmax(0, 1fr))"
            >
              ${slots.map(
                (s, i) =>
                  html`<button
                    type="button"
                    class="explore-slot"
                    style="background: ${CROPS[s.crop]?.color ?? '#FFFFFF'}"
                    data-action="next-crop"
                    data-i="${i}"
                    ${CROPS[s.crop]?.years > 1 ? 'disabled' : ''}
                  >
                    ${fieldStrip(s.crop, 56, 8)}
                    <span class="small strong muted-dark">Année ${i + 1}</span>
                    <span class="seg__name">${CROPS[s.crop]?.name ?? '—'}</span>
                    <span class="small"
                      >${CROPS[s.crop]?.years > 1 ? 'culture sur plusieurs années' : '↻ changer'}</span
                    >
                  </button>`,
              )}
            </div>
            ${errors.map((e) => alertBox('warn', e))}
          </section>
          <section class="card stack-sm">
            <h2 class="h2">Pourquoi ces chiffres</h2>
            ${plan ? (plan.explanations.length ? plan.explanations.map((e) => html`<p class="bullet">${e.message}</p>`) : html`<p class="bullet">Plus il y a de cultures différentes, plus la section résiste aux mauvaises années.</p>`) : loading()}
            <span class="muted small"
              >Les études derrière ces explications sont dans Détail et sources.</span
            >
          </section>
        </div>
        <aside class="card grow-1 stack-md live-panel">
          <span class="eyebrow"
            >En direct ${state.plan.status === 'refreshing' ? '· calcul…' : ''}</span
          >
          ${
            plan
              ? html`<div class="card card--dark stack-xs">
                    <span class="small">Rendement vs maïs en continu</span
                    ><span class="big-number big-number--md"
                      >${cmp.yieldGainPct[0] >= 0 ? '+' : ''}${cmp.yieldGainPct[0]} à
                      ${cmp.yieldGainPct[1] >= 0 ? '+' : ''}${cmp.yieldGainPct[1]} %</span
                    >
                  </div>
                  ${SCORE_KEYS.map((k) => scoreBar(SCORE_LABELS[k], plan.scores[k], { delta: base ? plan.scores[k] - base[k] : undefined }))}
                  <div class="row-between divider-top">
                    <strong>Charge de travail</strong
                    ><span class="pill ${plan.workload === 'faible' ? 'pill--info' : 'pill--warn'}"
                      >${WORK[plan.workload]}</span
                    >
                  </div>`
              : loading()
          }
          <button type="button" class="btn btn--primary btn--block" data-action="save-explorer">
            Enregistrer cette version
          </button>
        </aside>
      </div>`;
    return sectionLayout(state, section, 'explorer', body);
  },
  actions: {
    'next-crop': (app, el) => {
      const { id } = app.state.ui.route.params;
      const i = Number(el.dataset.i);
      app.updateFarm((farm) => {
        const sec = farm.sections.find((x) => x.id === id);
        const cur = toSlots(sec.rotation)[i].crop;
        const next = ONE_YEAR[(ONE_YEAR.indexOf(cur) + 1) % ONE_YEAR.length];
        sec.rotation = placeCrop(sec.rotation, i, next);
      });
    },
    'reset-explorer': (app) => {
      const { id } = app.state.ui.route.params;
      const snap = app.state.ui.explorerSnap[id];
      if (!snap) return;
      app.updateFarm(
        (farm) => (farm.sections.find((x) => x.id === id).rotation = structuredClone(snap)),
      );
    },
    'save-explorer': (app) => {
      const { id } = app.state.ui.route.params;
      app.update((s) => {
        delete s.ui.explorerSnap[id];
        delete s.ui.explorerBase[id];
      });
      app.go(`#/section/${id}/resultats`);
    },
  },
};
