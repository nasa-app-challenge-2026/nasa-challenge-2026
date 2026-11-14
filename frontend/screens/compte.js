/** 13 · Compte et réglages. Owner: Loïc. */
import { html } from '../lib/html.js';
import { nameOf } from '../../data/reference/crops.js';
import { appHeader } from '../ui/layout.js';
import { farmFactsEditor, priorityActions, priorityEditor } from './priorites.js';
import { seedActions, seedBank } from '../ui/seedsEditor.js';
import { timeActions, timeSettingsEditor } from '../ui/timeSettingsEditor.js';

const TABS = [
  ['profil', 'Profil'],
  ['ferme', 'Ma ferme'],
  ['semences', 'Semences'],
  ['temps', 'Cycle et horizon'],
  ['prio', 'Priorités'],
  ['cgu', 'Conditions d’utilisation'],
];

function panel(state) {
  const { user, farm } = state;
  switch (state.ui.settingsTab) {
    case 'profil':
      return html`<div class="stack-md">
        <div class="stack-xs">
          <h2 class="h2 h2--lg">Profil</h2>
          <p class="muted small">Vos informations de connexion.</p>
        </div>
        <div class="grid grid--2">
          <label class="field"
            >Nom complet<input
              type="text"
              value="${user?.name ?? ''}"
              data-change="set-user"
              data-key="name"
          /></label>
          <label class="field"
            >Courriel<input
              type="email"
              value="${user?.email ?? ''}"
              data-change="set-user"
              data-key="email"
          /></label>
        </div>
      </div>`;
    case 'semences':
      return html`<div class="stack-md">
        <div class="stack-xs">
          <h2 class="h2 h2--lg">Ma réserve de semences</h2>
          <p class="muted small">
            Les semences que vous avez déjà, sans les quantités. Ce qui pousse sur chaque section se
            change dans « Ma parcelle ».
          </p>
        </div>
        ${seedBank(state)}
      </div>`;
    case 'temps':
      return html`<div class="stack-md">
        <div class="stack-xs">
          <h2 class="h2 h2--lg">Cycle et horizon</h2>
          <p class="muted small">Le même découpage du temps pour toutes les sections.</p>
        </div>
        ${timeSettingsEditor(state)}
      </div>`;
    case 'prio':
      return html`<div class="stack-md">
        <div class="stack-xs">
          <h2 class="h2 h2--lg">Priorités</h2>
          <p class="muted small">
            L’ordre donne le poids de chaque critère dans la note des suites de cultures.
          </p>
        </div>
        ${priorityEditor(state)} ${farmFactsEditor(state)}
      </div>`;
    case 'cgu':
      return html`<div class="stack-sm">
        <h2 class="h2 h2--lg">Conditions d’utilisation</h2>
        <p>
          Field Shift est un outil d’aide à la décision. Ses suggestions s’appuient sur des données
          publiques de la NASA et sur des études publiées ; elles ne remplacent pas l’avis d’un
          agronome.
        </p>
        <p>
          Le contour de votre ferme et vos réglages servent uniquement à calculer vos résultats.
          [TEXTE COMPLET À RÉDIGER]
        </p>
        <a href="#/sources">Voir toutes les sources de données</a>
      </div>`;
    default:
      return html`<div class="stack-md">
        <div class="stack-xs">
          <h2 class="h2 h2--lg">Ma ferme</h2>
          <p class="muted small">
            ${farm.farm.name} · ${farm.farm.location?.label ?? ''} ·
            ${farm.sections.reduce((a, s) => a + s.areaHa, 0)} ha
          </p>
        </div>
        <div class="stack-xs">
          ${farm.sections.map(
            (s) =>
              html`<div class="list-row">
                <span class="section-badge">${s.id}</span
                ><span class="stack-0 grow"
                  ><strong>Section ${s.id} · ${s.areaHa} ha</strong
                  ><span class="muted small"
                    >${(s.currentRotation ?? []).map(nameOf).join(' → ') || 'Pas de rotation actuelle'}</span
                  ></span
                ><a href="#/section/${s.id}/parcelle">Modifier</a>
              </div>`,
          )}
        </div>
      </div>`;
  }
}

export default {
  title: 'Compte et réglages',
  render(state) {
    return html`${appHeader(state, 'compte')}
      <div class="page page--section">
        <aside class="section-aside stack-md">
          <h1 class="h1">Réglages</h1>
          <nav class="section-nav" aria-label="Réglages">
            ${TABS.map(([id, label]) => html`<button type="button" class="${state.ui.settingsTab === id ? 'is-active' : ''}" data-action="settings-tab" data-tab="${id}">${label}</button>`)}
          </nav>
          <button type="button" class="btn btn--danger" data-action="logout">Se déconnecter</button>
        </aside>
        <main class="section-main card card--lg" id="main">${panel(state)}</main>
      </div>`;
  },
  rota: 'tableau',
  actions: {
    ...seedActions,
    ...timeActions,
    ...priorityActions,
    'settings-tab': (app, el) =>
      app.update((s) => {
        s.ui.settingsTab = el.dataset.tab;
      }),
    'set-user': (app, el) =>
      app.update((s) => {
        s.user[el.dataset.key] = el.value;
      }),
    logout: (app) => {
      app.update((s) => {
        s.user = null;
      });
      app.go('#/connexion');
    },
  },
};
