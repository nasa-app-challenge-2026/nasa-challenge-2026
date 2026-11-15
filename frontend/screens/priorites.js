/**
 * 6 · Priorités (onboarding). Owner: Loïc. Step 1 of the algorithm, block D: the
 * farmer ranks the four priorities (rendement, utilisation de l’eau, protection du
 * sol, ravageurs) and says which equipment he lacks. The weights shown are the rank
 * order centroid the algorithm uses.
 */
import { html } from '../lib/html.js';
import { CRITERIA } from '../../data/reference/criteria.js';
import { EQUIPMENT } from '../../data/reference/crops.js';
import { moveCriterion, weightShares } from '../../application/rules/priorities.js';
import { onboardingHeader } from '../ui/layout.js';
import { icon, ICONS } from '../ui/icons.js';
import { switchButton } from '../ui/widgets.js';

export function priorityEditor(state) {
  const ranking = state.farm.farm.priorities;
  const shares = weightShares(state.plan.data, ranking);
  const share = (c) => (shares ? `${shares[c]} %` : '…');
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
          <span class="muted small nowrap" title="Poids calculé par l’algorithme">${share(k)}</span>
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
          </span>
        </li>`;
      })}
    </ol>
    <span class="muted small"
      >La note de chaque suite de cultures est la moyenne de ces quatre notes, pondérée par ces
      poids.</span
    >
  </div>`;
}

export function farmFactsEditor(state) {
  const f = state.farm.farm;
  return html`<div class="stack-sm">
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
            Classez les quatre priorités, de la plus importante à la moins importante. L’appli note
            chaque suite de cultures sur ces quatre priorités ; la première pèse le plus. Elle donne
            aussi plus de poids à la protection du sol et à l’eau si votre champ y est fragile.
          </p>
        </div>
        ${priorityEditor(state)}
        <section class="card stack-sm">
          <h2 class="h2">Votre équipement</h2>
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
