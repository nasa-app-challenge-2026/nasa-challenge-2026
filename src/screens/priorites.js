/** 5 · Priorités. Owner: Loïc. The order is sent to the engine (farm.priorities). */
import { html } from '../lib/html.js';
import { PRIORITIES, PRIORITY_WEIGHTS } from '../data/catalog.js';
import { onboardingHeader } from '../ui/layout.js';
import { icon, ICONS } from '../ui/icons.js';
import { autoStagger } from '../lib/rotation.js';

export function priorityList(order, { movable = true } = {}) {
  return html`<ol class="prio-list">
    ${order.map((k, i) => {
      const p = PRIORITIES[k];
      return html`<li class="prio ${i === 0 ? 'is-first' : ''}">
        <span class="prio__rank">${i + 1}</span>
        <span class="prio__icon">${icon(p.icon, { size: 22, color: '#2E6B3B' })}</span>
        <span class="stack-0 grow"
          ><strong>${p.label}</strong><span class="muted small">${p.text}</span></span
        >
        ${k === 'travail' ? html`<span class="pill pill--info">nouveau</span>` : ''}
        ${
          movable
            ? html`<span class="row gap-xs">
                <button
                  type="button"
                  class="icon-btn"
                  data-action="prio-move"
                  data-i="${i}"
                  data-d="-1"
                  aria-label="Monter ${p.label}"
                  ${i === 0 ? 'disabled' : ''}
                >
                  ${icon(ICONS.up, { size: 18 })}
                </button>
                <button
                  type="button"
                  class="icon-btn"
                  data-action="prio-move"
                  data-i="${i}"
                  data-d="1"
                  aria-label="Descendre ${p.label}"
                  ${i === order.length - 1 ? 'disabled' : ''}
                >
                  ${icon(ICONS.down, { size: 18 })}
                </button>
              </span>`
            : ''
        }
      </li>`;
    })}
  </ol>`;
}

export const movePriority = (app, el) => {
  const i = Number(el.dataset.i);
  const j = i + Number(el.dataset.d);
  app.updateFarm((farm) => {
    const p = farm.farm.priorities;
    if (j < 0 || j >= p.length) return;
    [p[i], p[j]] = [p[j], p[i]];
  });
};

export default {
  title: 'Priorités',
  render(state) {
    const order = state.farm.farm.priorities;
    return html`${onboardingHeader(5)}
      <main class="page page--narrow" id="main">
        <div class="row-wrap align-start gap-lg">
          <div class="grow-3 stack-md">
            <div class="stack-xs">
              <h1 class="h1 h1--xl">Qu’est-ce qui compte le plus pour vous ?</h1>
              <p class="lead">
                Classez ces cinq objectifs, du plus important au moins important. L’appli s’en sert
                pour classer les rotations qu’elle vous propose.
              </p>
            </div>
            ${priorityList(order)}
            <div class="actions-bar">
              <a class="btn btn--secondary" href="#/cultures">Retour</a>
              <button type="button" class="btn btn--primary" data-action="finish-onboarding">
                Terminer et voir ma ferme →
              </button>
            </div>
          </div>
          <aside class="grow-1 stack-md">
            <div class="card stack-sm">
              <span class="eyebrow">Votre ordre</span>
              ${order.map(
                (k, i) =>
                  html`<div class="stack-xxs">
                    <div class="row-between small">
                      <strong>${PRIORITIES[k].label}</strong
                      ><span class="muted">${PRIORITY_WEIGHTS[i]} %</span>
                    </div>
                    <div class="bar">
                      <div
                        class="bar__fill ${i === 0 ? '' : 'is-soft'}"
                        style="width: ${PRIORITY_WEIGHTS[i] * 2.5}%"
                      ></div>
                    </div>
                  </div>`,
              )}
              <p class="muted small">
                Le premier choix pèse le plus dans le classement des rotations.
              </p>
            </div>
            <div class="card card--soft row-start">
              <span class="info-dot">i</span>
              <p class="small">
                Vous pourrez changer cet ordre dans Compte et réglages. Il ne s’affiche pas dans «
                Explorer et modifier », pour garder cet écran simple.
              </p>
            </div>
          </aside>
        </div>
      </main>`;
  },
  actions: {
    'prio-move': movePriority,
    'finish-onboarding': (app) => {
      // Start with the sections staggered: different crops across the farm each year.
      app.updateFarm((farm, s) => {
        autoStagger(farm.farm, farm.sections);
        s.onboarded = true;
      });
      app.go('#/tableau');
    },
  },
};
