/** 13 · Compte et réglages. Owner: Loïc. */
import { html } from '../lib/html.js';
import { CROPS } from '../data/crops.js';
import { toSlots } from '../lib/rotation.js';
import { appHeader } from '../ui/layout.js';
import { switchButton } from '../ui/widgets.js';
import { priorityList, movePriority } from './priorites.js';

const TABS = [
  ['profil', 'Profil'],
  ['ferme', 'Ma ferme'],
  ['prio', 'Priorités'],
  ['capteurs', 'Capteurs'],
  ['cgu', 'Conditions d’utilisation'],
];
const HORIZONS = [3, 4, 5, 10, 12, 15, 30];

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
    case 'prio':
      return html`<div class="stack-md">
        <div class="stack-xs">
          <h2 class="h2 h2--lg">Priorités</h2>
          <p class="muted small">L’ordre sert à classer les rotations proposées.</p>
        </div>
        ${priorityList(farm.farm.priorities)}
      </div>`;
    case 'capteurs':
      return html`<div class="stack-md">
        <div class="row-between">
          <div class="stack-xs">
            <h2 class="h2 h2--lg">Capteurs</h2>
            <p class="muted small">
              Option pour les grandes fermes : vos mesures remplacent les estimations des
              satellites.
            </p>
          </div>
          ${switchButton(farm.farm.sensors, 'toggle-sensors', 'Utiliser mes capteurs')}
        </div>
        ${
          farm.farm.sensors
            ? html`<div class="stack-xs">
                <div class="list-row">
                  <span class="dot dot--blue"></span
                  ><span class="grow">Sonde d’humidité · Section A</span
                  ><span class="pill pill--info">Connectée</span>
                </div>
                <button type="button" class="btn btn--dashed">+ Ajouter un capteur</button>
              </div>`
            : html`<div class="card card--tint small">
                Formule de base : toutes les données viennent des satellites de la NASA. Aucun
                matériel nécessaire.
              </div>`
        }
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
                    >${toSlots(s.rotation)
                      .map((x) => CROPS[x.crop]?.name ?? '—')
                      .join(' → ')}</span
                  ></span
                ><a href="#/section/${s.id}/rotation">Modifier</a>
              </div>`,
          )}
        </div>
        <label class="field field--narrow"
          >Durée d’analyse de la ferme
          <select data-change="set-horizon">
            ${HORIZONS.map((h) => html`<option value="${h}" ${h === farm.farm.horizonYears ? 'selected' : ''}>${h} ans (${farm.farm.startYear} à ${farm.farm.startYear + h - 1})</option>`)}
          </select>
          <span class="muted small">Chaque section répète son cycle pour remplir cette durée.</span>
        </label>
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
    'settings-tab': (app, el) =>
      app.update((s) => {
        s.ui.settingsTab = el.dataset.tab;
      }),
    'set-user': (app, el) =>
      app.update((s) => {
        s.user[el.dataset.key] = el.value;
      }),
    'set-horizon': (app, el) =>
      app.updateFarm((farm) => {
        farm.farm.horizonYears = Number(el.value);
      }),
    'toggle-sensors': (app) => {
      app.updateFarm((farm) => {
        farm.farm.sensors = !farm.farm.sensors;
      });
      app.update((s) => {
        s.field = {};
      });
    },
    'prio-move': movePriority,
    logout: (app) => {
      app.update((s) => {
        s.user = null;
      });
      app.go('#/connexion');
    },
  },
};
