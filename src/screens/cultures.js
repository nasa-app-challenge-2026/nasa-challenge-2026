/**
 * 4b · Mes cultures (onboarding, between Tracer and Priorités). Owner: Loïc.
 * What grows on each section now, the seed reserve, and a first rotation per
 * section proposed by the engine from those seeds (farm.seeds, section.currentCrop).
 */
import { html } from '../lib/html.js';
import { onboardingHeader } from '../ui/layout.js';
import { currentCropsEditor, proposeAllCard, seedActions, seedBank } from '../ui/seedsEditor.js';

export default {
  title: 'Mes cultures',
  render(state) {
    const year = state.farm.farm.startYear - 1;
    return html`${onboardingHeader(4)}
      <main class="page page--narrow stack-lg" id="main">
        <div class="stack-xs">
          <h1 class="h1 h1--xl">Qu’est-ce que vous cultivez ?</h1>
          <p class="lead">
            Dites-nous ce qui pousse maintenant et les semences que vous avez. L’appli construit les
            rotations avec, et vous gardez la main sur tout.
          </p>
        </div>

        <section class="card stack-md" aria-labelledby="now-title">
          <div class="step-head">
            <span class="step-num">1</span>
            <h2 class="h2" id="now-title">Ce qui pousse en ${year}</h2>
            <span class="muted small">La culture de l’an prochain ne pourra pas être la même</span>
          </div>
          ${currentCropsEditor(state)}
        </section>

        <section class="card stack-md" aria-labelledby="seeds-title">
          <div class="step-head">
            <span class="step-num">2</span>
            <h2 class="h2" id="seeds-title">Ma réserve de semences</h2>
            <span class="muted small"
              >Ce que vous pouvez semer · vos cultures actuelles sont déjà cochées</span
            >
          </div>
          ${seedBank(state)}
        </section>

        <section class="stack-sm" aria-labelledby="start-title">
          <div class="step-head">
            <span class="step-num">3</span>
            <h2 class="h2" id="start-title">Mes rotations de départ</h2>
          </div>
          ${proposeAllCard(state)}
        </section>

        <div class="actions-bar">
          <a class="btn btn--secondary" href="#/tracer">Retour</a>
          <a class="btn btn--primary" href="#/priorites">Continuer →</a>
        </div>
      </main>`;
  },
  actions: seedActions,
};
