/** Page frames: app header, onboarding header, section layout with side menu. */
import { html } from '../lib/html.js';
import { colorOf, nameOf } from '../../data/reference/crops.js';
import { icon, ICONS } from './icons.js';
import { demoBadge, logo } from './widgets.js';
import { getLanguage, t, formatNumber } from '../../data/i18n/index.js';

export function languageButton() {
  return html`<button
    type="button"
    class="language-toggle"
    id="language-toggle"
    data-refocus
    data-action="toggle-language"
    aria-label="${t('language.switch')}"
    title="${t('language.switch')}"
  >
    <span lang="en" class="${getLanguage() === 'en' ? 'is-current' : ''}">EN</span>
    <span aria-hidden="true">⇄</span
    ><span lang="fr" class="${getLanguage() === 'fr' ? 'is-current' : ''}">FR</span>
  </button>`;
}

export function isDemo(state) {
  return state.plan.data?.meta?.demo ?? false;
}

export function appHeader(state, active) {
  const links = [
    ['tableau', '#/tableau', 'Tableau de bord'],
    ['sources', '#/sources', 'Sources'],
    ['compte', '#/compte', 'Compte'],
  ];
  return html`<header class="app-header">
    <a class="brand" href="#/tableau">${logo()}</a>
    <nav class="main-nav" aria-label="Navigation principale">
      ${links.map(([id, href, label]) =>
        id === active
          ? html`<a href="${href}" class="is-active" aria-current="page">${label}</a>`
          : html`<a href="${href}">${label}</a>`,
      )}
    </nav>
    <div class="app-header__end">
      ${languageButton()} ${demoBadge(isDemo(state))}
      <a class="avatar" href="#/compte" aria-label="Mon compte"
        >${icon(ICONS.user, { size: 20 })}</a
      >
    </div>
  </header>`;
}

const STEPS = [
  'Type de ferme',
  'Localisation',
  'Tracer la ferme',
  'Mes cultures',
  'Cycle et horizon',
  'Priorités',
];

export function onboardingHeader(step) {
  return html`<header class="app-header">
    <span class="brand">${logo()}</span>
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
    ${languageButton()}<a class="link-quiet" href="#/connexion">Enregistrer et quitter</a>
  </header>`;
}

const SECTION_TABS = [
  ['plan', 'Rotations proposées'],
  ['parcelle', 'Ma parcelle'],
  ['champ', 'Mon champ'],
  ['jumeaux', 'Climat et jumeaux'],
];

/** "Maïs en place, récolte oct. 2026" or "Parcelle libre". */
function inPlaceText(section) {
  if (!section.currentCrop) return 'Parcelle libre';
  return `${nameOf(section.currentCrop)} en place`;
}

export function sectionLayout(state, section, tab, body) {
  const rotation = section.currentRotation ?? [];
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
              ><span class="muted small"
                >${formatNumber(section.areaHa)} ha · ${inPlaceText(section)}</span
              ></span
            >
          </div>
          <div class="mini-cycle">
            ${rotation.map((id) => html`<span title="${nameOf(id)}" style="background: ${colorOf(id)}"></span>`)}
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
