/** 5 · Cycle et horizon (onboarding). Owner: Loïc. Step 1 of the algorithm, block C. */
import { html } from '../lib/html.js';
import { onboardingHeader } from '../ui/layout.js';
import { askRota } from '../ui/rota.js';
import { timeActions, timeSettingsEditor } from '../ui/timeSettingsEditor.js';

export default {
  title: 'Cycle et horizon',
  render(state) {
    return html`${onboardingHeader(5)}
      <main class="page page--narrow stack-lg" id="main">
        <div class="row-between wrap">
          <h1 class="h1 h1--xl">Sur combien de temps planifier ?</h1>
          ${askRota('temps')}
        </div>
        <section class="card">${timeSettingsEditor(state)}</section>
        <div class="actions-bar">
          <a class="btn btn--secondary" href="#/cultures">Retour</a>
          <a class="btn btn--primary" href="#/priorites">Continuer →</a>
        </div>
      </main>`;
  },
  actions: timeActions,
};
