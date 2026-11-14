/** 5 · Cycle et horizon (onboarding). Owner: Loïc. Step 1 of the algorithm, block C. */
import { html } from '../lib/html.js';
import { onboardingHeader } from '../ui/layout.js';
import { timeActions, timeSettingsEditor } from '../ui/timeSettingsEditor.js';

export default {
  title: 'Cycle et horizon',
  render(state) {
    return html`${onboardingHeader(5)}
      <main class="page page--narrow stack-lg" id="main">
        <div class="stack-xs">
          <h1 class="h1 h1--xl">Sur combien de temps planifier ?</h1>
          <p class="lead">
            Le plan se découpe en cycles. Pour chaque cycle, l’appli calcule le climat de votre
            ferme, cherche les endroits qui ont déjà ce climat et choisit la meilleure suite de
            cultures.
          </p>
        </div>
        <section class="card">${timeSettingsEditor(state)}</section>
        <div class="card card--soft row-start">
          <span class="info-dot">i</span>
          <p class="small">
            Dans les 10 prochaines années, le climat vient de la tendance des 40 dernières années de
            NASA POWER. Au-delà, il vient de modèles climatiques.
          </p>
        </div>
        <div class="actions-bar">
          <a class="btn btn--secondary" href="#/cultures">Retour</a>
          <a class="btn btn--primary" href="#/priorites">Continuer →</a>
        </div>
      </main>`;
  },
  actions: timeActions,
};
