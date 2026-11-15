/**
 * 2 · Type de ferme. Owner: Loïc. The MVP plans field crops ("grandes cultures"). The other
 * types are shown like the first one, without any "coming soon": touching one opens Rota, who
 * says it is out of the MVP.
 */
import { html } from '../lib/html.js';
import { FARM_TYPES } from '../../data/reference/catalog.js';
import { onboardingHeader } from '../ui/layout.js';
import { icon } from '../ui/icons.js';
import { askRota } from '../ui/rota.js';

function typeCard(type) {
  const action = type.available
    ? html`aria-pressed="true"`
    : html`data-action="rota-mvp" data-what="${type.name}"`;
  return html`<button
    type="button"
    class="type-card ${type.available ? 'is-selected' : ''}"
    ${action}
  >
    <span class="type-card__icon">${icon(type.icon, { size: 26 })}</span>
    <span class="type-card__name">${type.name}</span>
    <span class="muted small">${type.what}</span>
  </button>`;
}

export default {
  title: 'Type de ferme',
  render() {
    return html`${onboardingHeader(1)}
      <main class="page page--narrow stack-lg" id="main">
        <div class="row-between wrap">
          <h1 class="h1 h1--xl">Quel type de ferme avez-vous ?</h1>
          ${askRota('types-ferme')}
        </div>
        <div class="grid grid--types">${FARM_TYPES.map(typeCard)}</div>
        <div class="actions-bar">
          <a class="btn btn--secondary" href="#/connexion">Retour</a>
          <button type="button" class="btn btn--primary" data-action="confirm-type">
            Continuer →
          </button>
        </div>
      </main>`;
  },
  actions: {
    'confirm-type': (app) => {
      app.updateFarm((farm) => {
        farm.farm.type = 'grandes-cultures';
      });
      app.go('#/localisation');
    },
  },
};
