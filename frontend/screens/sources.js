/** 12 · Détail et sources. Owner: Justin. The only place where study names appear. */
import { html } from '../lib/html.js';
import { SOURCES } from '../../data/reference/sources.js';
import { appHeader } from '../ui/layout.js';

export default {
  title: 'Détail et sources',
  rota: 'tableau',
  render(state) {
    const f = state.ui.sourcesFilter;
    const nData = SOURCES.filter((s) => s.kind === 'data').length;
    const nStudy = SOURCES.length - nData;
    const items = SOURCES.map((s, i) => ({ ...s, i })).filter((s) => f === 'all' || s.kind === f);
    const back = state.ui.selectedSection;
    return html`${appHeader(state, 'sources')}
      <main class="page page--read stack-md" id="main">
        <a class="back-link" href="#/section/${back}/resultats">← Retour à la section ${back}</a>
        <div class="stack-xs">
          <h1 class="h1 h1--xl">D’où viennent les chiffres</h1>
          <p class="lead">
            Les suggestions de l’appli ne citent pas d’études, pour rester simples. Tout est ici :
            les données des satellites de la NASA et les études qui donnent l’effet de chaque
            enchaînement de cultures.
          </p>
        </div>
        <div class="row-wrap gap-md align-stretch">
          <div class="card grow-1 stack-0">
            <span class="h1">${nData}</span><span class="muted small">jeux de données</span>
          </div>
          <div class="card grow-1 stack-0">
            <span class="h1">${nStudy}</span><span class="muted small">études scientifiques</span>
          </div>
          <div class="card card--soft grow-2 row-start">
            <span class="info-dot">i</span>
            <p class="small">
              Confiance élevée = plusieurs études couvrent cet enchaînement. Sur 15 ans et plus, la
              confiance baisse d’un niveau.
            </p>
          </div>
        </div>
        <div class="row-wrap gap-sm" role="group" aria-label="Filtrer">
          ${[
            ['all', `Tout (${SOURCES.length})`],
            ['data', `Données NASA (${nData})`],
            ['study', `Études (${nStudy})`],
          ].map(
            ([k, label]) =>
              html`<button
                type="button"
                class="filter ${f === k ? 'is-on' : ''}"
                data-action="filter-sources"
                data-k="${k}"
                aria-pressed="${String(f === k)}"
              >
                ${label}
              </button>`,
          )}
        </div>
        <div class="stack-sm">
          ${items.map((s) => {
            const open = !!state.ui.openSources[s.i];
            return html`<div class="card card--flush">
              <button
                type="button"
                class="source-head"
                data-action="toggle-source"
                data-i="${s.i}"
                aria-expanded="${String(open)}"
              >
                <span class="pill ${s.kind === 'data' ? 'pill--info' : 'pill--ok'}"
                  >${s.kind === 'data' ? 'Données' : 'Étude'}</span
                >
                <span class="stack-0 grow"
                  ><strong>${s.title}</strong><span class="muted small">${s.use}</span></span
                >
                <span class="source-head__chev" aria-hidden="true">${open ? '−' : '+'}</span>
              </button>
              ${
                open
                  ? html`<div class="source-body stack-sm">
                      <p>${s.what}</p>
                      <div class="row-wrap gap-sm align-center">
                        <span class="pill pill--neutral">Utilisé dans : ${s.where}</span
                        ><a
                          href="${s.href}"
                          target="_blank"
                          rel="noopener noreferrer"
                          class="strong"
                          >${s.linkLabel} ↗</a
                        >
                      </div>
                    </div>`
                  : ''
              }
            </div>`;
          })}
        </div>
        <p class="muted small">
          Field Shift aide à décider ; il ne remplace pas l’avis d’un agronome. Les effets viennent
          surtout d’études menées aux États-Unis et devront être calibrés pour le Québec.
        </p>
      </main>`;
  },
  actions: {
    'filter-sources': (app, el) => app.update((s) => (s.ui.sourcesFilter = el.dataset.k)),
    'toggle-source': (app, el) =>
      app.update((s) => (s.ui.openSources[el.dataset.i] = !s.ui.openSources[el.dataset.i])),
  },
};
