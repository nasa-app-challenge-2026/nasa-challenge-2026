/** Page frames: app header, onboarding header, section layout with side menu. */
import { html } from '../lib/html.js';
import { CROPS } from '../data/crops.js';
import { cycleLength, toSlots } from '../lib/rotation.js';
import { icon, ICONS } from './icons.js';
import { demoBadge, logo } from './widgets.js';

export function isDemo(state) {
  return state.plan.data?.meta?.demo ?? state.engineName === 'mock';
}

export function appHeader(state, active) {
  const links = [
    ['tableau', '#/tableau', 'Tableau de bord'],
    ['sources', '#/sources', 'Sources'],
    ['compte', '#/compte', 'Compte'],
  ];
  return html`<header class="app-header">
    <a class="brand" href="#/tableau">${logo()}<span class="brand__name">Field Shift</span></a>
    <nav class="main-nav" aria-label="Navigation principale">
      ${links.map(([id, href, label]) =>
        id === active
          ? html`<a href="${href}" class="is-active" aria-current="page">${label}</a>`
          : html`<a href="${href}">${label}</a>`,
      )}
    </nav>
    <div class="app-header__end">
      ${demoBadge(isDemo(state))}
      <a class="avatar" href="#/compte" aria-label="Mon compte"
        >${icon(ICONS.user, { size: 20 })}</a
      >
    </div>
  </header>`;
}

const STEPS = ['Type de ferme', 'Localisation', 'Tracer la ferme', 'Mes cultures', 'Priorités'];

export function onboardingHeader(step) {
  return html`<header class="app-header">
    <span class="brand">${logo()}<span class="brand__name">Field Shift</span></span>
    <ol class="stepper" aria-label="Étapes de configuration">
      ${STEPS.map((label, i) => {
        const n = i + 1;
        const state = n < step ? 'done' : n === step ? 'current' : 'todo';
        return html`<li
          class="stepper__item is-${state}"
          ${state === 'current' ? html`aria-current="step"` : ''}
        >
          <span class="stepper__dot">${state === 'done' ? '✓' : n}</span>${label}
        </li>`;
      })}
    </ol>
    <a class="link-quiet" href="#/connexion">Enregistrer et quitter</a>
  </header>`;
}

const SECTION_TABS = [
  ['champ', 'Mon champ'],
  ['rotation', 'Rotation'],
  ['resultats', 'Résultats'],
  ['explorer', 'Explorer et modifier'],
  ['stress', 'Stress test'],
];

export function sectionLayout(state, section, tab, body) {
  const L = cycleLength(section.rotation);
  return html`${appHeader(state, 'tableau')}
    <div class="page page--section">
      <aside class="section-aside">
        <a class="back-link" href="#/tableau">← Tableau de bord</a>
        <div class="card section-card">
          <div class="section-card__head">
            <span class="section-badge is-dark" style="view-transition-name: section-${section.id}"
              >${section.id}</span
            ><span class="stack-xs"
              ><strong>Section ${section.id}</strong
              ><span class="muted small">${section.areaHa} ha · cycle de ${L} ans</span></span
            >
          </div>
          <div class="mini-cycle">
            ${toSlots(section.rotation).map((s) => html`<span style="background: ${CROPS[s.crop]?.color || '#E5E9E0'}"></span>`)}
          </div>
        </div>
        <nav class="section-nav" aria-label="Pages de la section">
          ${SECTION_TABS.map(([id, label]) =>
            id === tab
              ? html`<a class="is-active" aria-current="page" href="#/section/${section.id}/${id}"
                  >${label}</a
                >`
              : html`<a href="#/section/${section.id}/${id}">${label}</a>`,
          )}
          <a href="#/sources">Détail et sources</a>
        </nav>
      </aside>
      <main class="section-main" id="main">${body}</main>
    </div>`;
}

export function pageTitle(title, lead, aside = '') {
  return html`<div class="page-title">
    <div class="stack-xs">
      <h1 class="h1">${title}</h1>
      ${lead ? html`<p class="lead">${lead}</p>` : ''}
    </div>
    ${aside}
  </div>`;
}
