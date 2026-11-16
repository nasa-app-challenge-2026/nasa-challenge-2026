/**
 * 4 · Mes cultures (onboarding). Owner: Loïc. Step 1 of the algorithm, blocks A and B:
 * for each section, the crop in place, its harvest month and the current rotation;
 * then the seed reserve. The previous years, diseases and soil test can be given
 * later on the section screen (Ma parcelle).
 */
import { html } from '../lib/html.js';
import { formatNumber } from '../../data/i18n/index.js';
import { onboardingHeader } from '../ui/layout.js';
import { inPlaceEditor, seedActions, seedBank } from '../ui/seedsEditor.js';
import { sectionInputProblems } from '../../application/rules/sectionInputs.js';
import { alertBox } from '../ui/widgets.js';
import { askRota, askRotaIcon } from '../ui/rota.js';

export default {
  title: 'Mes cultures',
  render(state) {
    return html`${onboardingHeader(4)}
      <main class="page page--narrow stack-lg" id="main">
        <div class="row-between wrap">
          <h1 class="h1 h1--xl">Qu’est-ce que vous cultivez ?</h1>
          ${askRota('cultures')}
        </div>

        ${state.farm.sections.map(
          (s) =>
            html`<section class="card stack-md" aria-labelledby="sec-${s.id}">
              <div class="step-head">
                <span class="section-badge">${s.id}</span>
                <h2 class="h2" id="sec-${s.id}">Section ${s.id}</h2>
                <span class="muted small">${formatNumber(s.areaHa)} ha</span>
              </div>
              ${inPlaceEditor(s)} ${sectionInputProblems(s).map((p) => alertBox('warn', p))}
            </section>`,
        )}

        <section class="card stack-md" aria-labelledby="seeds-title">
          <div class="step-head">
            <h2 class="h2" id="seeds-title">Ma réserve de semences</h2>
            ${askRotaIcon('reserve')}
          </div>
          ${seedBank(state)}
        </section>

        <div class="actions-bar">
          <a class="btn btn--secondary" href="#/tracer">Retour</a>
          <a class="btn btn--primary" href="#/temps">Continuer →</a>
        </div>
      </main>`;
  },
  actions: seedActions,
};
