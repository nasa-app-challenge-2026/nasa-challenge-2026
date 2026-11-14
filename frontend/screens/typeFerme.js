/** 2 · Type de ferme. Owner: Loïc. Only "grandes cultures" is available. */
import { html } from '../lib/html.js';
import { FARM_TYPES } from '../../data/reference/catalog.js';
import { onboardingHeader } from '../ui/layout.js';
import { icon } from '../ui/icons.js';

export default {
  title: 'Type de ferme',
  render(state) {
    const sel = state.ui.farmTypeSel;
    const cur = FARM_TYPES.find((t) => t.id === sel);
    return html`${onboardingHeader(1)}
      <main class="page page--narrow stack-lg" id="main">
        <div class="stack-sm">
          <h1 class="h1 h1--xl">Quel type de ferme avez-vous ?</h1>
          <p class="lead">
            La rotation ne marche pas pareil partout. Field Shift commence par les grandes cultures
            ; les autres types arrivent ensuite.
          </p>
        </div>
        <div class="grid grid--types">
          ${FARM_TYPES.map(
            (t) =>
              html`<button
                type="button"
                class="type-card ${t.id === sel ? 'is-selected' : ''} ${t.available ? '' : 'is-soon'}"
                aria-pressed="${String(t.id === sel)}"
                data-action="pick-type"
                data-id="${t.id}"
              >
                <span class="type-card__icon">${icon(t.icon, { size: 26 })}</span>
                <span class="type-card__name">${t.name}</span>
                <span class="muted small">${t.what}</span>
                <span class="pill ${t.available ? 'pill--ok' : 'pill--warn'}"
                  >${t.available ? 'Disponible' : 'Bientôt'}</span
                >
              </button>`,
          )}
        </div>
        <div class="row-wrap">
          <div class="card grow-2 stack-xs">
            <span class="eyebrow">Comment la rotation y fonctionne</span>
            <span class="h2">${cur.name}</span>
            <p>${cur.how}</p>
            <span class="muted small">Échelle de temps : ${cur.scale}</span>
          </div>
          <div class="card card--soft grow-1 row-start">
            <span class="info-dot">i</span>
            <p>
              Le même principe partout : varier ce qui pousse au même endroit pour protéger le sol.
              Seule l’échelle de temps change.
            </p>
          </div>
        </div>
        <div class="actions-bar">
          <a class="btn btn--secondary" href="#/connexion">Retour</a>
          ${
            cur.available
              ? html`<button type="button" class="btn btn--primary" data-action="confirm-type">
                  Continuer avec les grandes cultures →
                </button>`
              : html`<span class="btn btn--disabled"
                  >Bientôt disponible · choisissez Grandes cultures</span
                >`
          }
        </div>
      </main>`;
  },
  actions: {
    'pick-type': (app, el) =>
      app.update((s) => {
        s.ui.farmTypeSel = el.dataset.id;
      }),
    'confirm-type': (app) => {
      app.updateFarm((farm) => {
        farm.farm.type = 'grandes-cultures';
      });
      app.go('#/localisation');
    },
  },
};
