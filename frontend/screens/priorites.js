/**
 * 6 · Priorités (onboarding). Owner: Loïc. Step 1 of the algorithm, block D: the
 * farmer ranks the criteria that matter (the others keep a small weight), says if
 * he has livestock and which equipment he lacks. The weights shown are the rank
 * order centroid the algorithm uses.
 */
import { html } from '../lib/html.js';
import { CRITERIA } from '../../data/reference/criteria.js';
import { EQUIPMENT } from '../../data/reference/crops.js';
import {
  moveCriterion,
  unrankedCriteria,
  weightsFromRanking,
} from '../../application/rules/priorities.js';
import { onboardingHeader } from '../ui/layout.js';
import { icon, ICONS } from '../ui/icons.js';
import { switchButton } from '../ui/widgets.js';

const PERCENT = 100;

export function priorityEditor(state) {
  const ranking = state.farm.farm.priorities;
  const weights = weightsFromRanking(ranking);
  const total = Object.values(weights).reduce((a, b) => a + b, 0);
  const share = (c) => Math.round((PERCENT * weights[c]) / total);
  return html`<div class="stack-md">
    <ol class="prio-list">
      ${ranking.map((k, i) => {
        const c = CRITERIA[k];
        return html`<li class="prio ${i === 0 ? 'is-first' : ''}">
          <span class="prio__rank">${i + 1}</span>
          <span class="prio__icon">${icon(c.icon, { size: 22, color: '#2E6B3B' })}</span>
          <span class="stack-0 grow"
            ><strong>${c.label}</strong><span class="muted small">${c.text}</span></span
          >
          <span class="muted small nowrap">${share(k)} %</span>
          <span class="row gap-xs">
            <button
              type="button"
              class="icon-btn"
              data-action="prio-move"
              data-i="${i}"
              data-d="-1"
              aria-label="Monter ${c.label}"
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
              aria-label="Descendre ${c.label}"
              ${i === ranking.length - 1 ? 'disabled' : ''}
            >
              ${icon(ICONS.down, { size: 18 })}
            </button>
            <button
              type="button"
              class="icon-btn"
              data-action="prio-remove"
              data-c="${k}"
              aria-label="Ne pas classer ${c.label}"
            >
              ${icon(ICONS.close, { size: 18 })}
            </button>
          </span>
        </li>`;
      })}
    </ol>
    ${
      unrankedCriteria(ranking).length
        ? html`<div class="stack-xs">
            <span class="eyebrow">Non classés (comptent peu)</span>
            <div class="row-wrap gap-xs">
              ${unrankedCriteria(ranking).map(
                (k) =>
                  html`<button
                    type="button"
                    class="now-chip"
                    data-action="prio-add"
                    data-c="${k}"
                    title="${CRITERIA[k].text}"
                  >
                    + ${CRITERIA[k].label} · ${share(k)} %
                  </button>`,
              )}
            </div>
          </div>`
        : ''
    }
  </div>`;
}

export function farmFactsEditor(state) {
  const f = state.farm.farm;
  return html`<div class="stack-sm">
    <div class="toggle-card">
      <span class="stack-0"
        ><strong class="small">J’ai du bétail</strong
        ><span class="muted small">Sinon, le fourrage compte peu</span></span
      >
      ${switchButton(f.livestock, 'toggle-livestock', 'J’ai du bétail')}
    </div>
    ${Object.values(EQUIPMENT).map(
      (e) =>
        html`<div class="toggle-card">
          <span class="stack-0"
            ><strong class="small">${e.name}</strong
            ><span class="muted small">Sans elle, pas de luzerne ni de foin</span></span
          >
          ${switchButton(!f.missingEquipment.includes(e.id), 'toggle-equipment', `J’ai une ${e.name.toLowerCase()}`, html`data-equipment="${e.id}"`)}
        </div>`,
    )}
  </div>`;
}

export const priorityActions = {
  'prio-move': (app, el) =>
    app.updateFarm((farm) => {
      farm.farm.priorities = moveCriterion(
        farm.farm.priorities,
        Number(el.dataset.i),
        Number(el.dataset.d),
      );
    }),
  'prio-remove': (app, el) =>
    app.updateFarm((farm) => {
      farm.farm.priorities = farm.farm.priorities.filter((c) => c !== el.dataset.c);
    }),
  'prio-add': (app, el) =>
    app.updateFarm((farm) => {
      farm.farm.priorities = [...farm.farm.priorities, el.dataset.c];
    }),
  'toggle-livestock': (app) =>
    app.updateFarm((farm) => (farm.farm.livestock = !farm.farm.livestock)),
  'toggle-equipment': (app, el) =>
    app.updateFarm((farm) => {
      const id = el.dataset.equipment;
      const missing = farm.farm.missingEquipment;
      farm.farm.missingEquipment = missing.includes(id)
        ? missing.filter((e) => e !== id)
        : [...missing, id];
    }),
};

export default {
  title: 'Priorités',
  render(state) {
    return html`${onboardingHeader(6)}
      <main class="page page--narrow stack-lg" id="main">
        <div class="stack-xs">
          <h1 class="h1 h1--xl">Qu’est-ce qui compte le plus pour vous ?</h1>
          <p class="lead">
            Classez les critères qui comptent, du plus important au moins important. L’appli note
            chaque suite de cultures sur ces critères ; le premier pèse le plus. Elle donne aussi
            plus de poids à l’érosion et à l’eau si votre champ y est fragile.
          </p>
        </div>
        ${priorityEditor(state)}
        <section class="card stack-sm">
          <h2 class="h2">Votre ferme</h2>
          ${farmFactsEditor(state)}
        </section>
        <div class="actions-bar">
          <a class="btn btn--secondary" href="#/temps">Retour</a>
          <button type="button" class="btn btn--primary" data-action="finish-onboarding">
            Terminer et voir mon plan →
          </button>
        </div>
      </main>`;
  },
  actions: {
    ...priorityActions,
    'finish-onboarding': (app) => {
      app.update((s) => (s.onboarded = true));
      app.go('#/tableau');
    },
  },
};
