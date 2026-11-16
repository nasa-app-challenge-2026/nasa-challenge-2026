/**
 * 7 · Tableau de bord de la ferme. Owner: Ali.
 *
 *   weather of the day, across the page
 *   the year shown (it moves the farm and the cards)
 *   the farm in 3D on the left, with the crops of the year as a pie chart in its corner;
 *   one card per section on the right: the crop of the year, the rotation of its cycle, keep or
 *   change and the score
 *
 * A section card opens its rotation; hovering or focusing highlights it in 3D. Touching the
 * section in the scene selects it. Handles reorder cards independently, by pointer or keyboard;
 * the order is a per-browser preference (prefs.dashboard).
 */
import { html, plural, verbatim } from '../lib/html.js';
import { formatNumber } from '../../data/i18n/index.js';
import { colorOf, nameOf, textureOf } from '../../data/reference/crops.js';
import { cropOfYear, cycleOfYear, farmMix, planYears } from '../../application/rules/planView.js';
import { getSeeds } from '../../application/rules/seeds.js';
import { blockLabel, dashboardOrder, isDefaultOrder, sectionOf } from '../lib/dashboard.js';
import { appHeader, pageTitle } from '../ui/layout.js';
import { icon, ICONS } from '../ui/icons.js';
import { isoFarm } from '../ui/isoFarm.js';
import { closeFarm3d, farm3dSlot, showFarm3d, highlightFarm3d } from '../ui/farm3d/index.js';
import { pieChart } from '../ui/pieChart.js';
import { fieldSwatch } from '../ui/textures.js';
import { errorBox, loading } from '../ui/widgets.js';
import { askRota } from '../ui/rota.js';
import { weatherWidget } from '../ui/weatherWidget.js';
import { decisionPill, planStatus, selectedYear } from '../ui/planWidgets.js';
import { rotationStrip } from '../ui/rotationViews.js';

const GRIP = 'M9 6h.01M15 6h.01M9 12h.01M15 12h.01M9 18h.01M15 18h.01';
/** Beyond this many years, the slider replaces the row of year buttons. */
const MAX_YEAR_BUTTONS = 14;
/** The score of a plan is on 100. */
const SCORE_MAX = 100;
/** The ring that shows a score: drawn in a 40 × 40 box. */
const RING = { size: 44, center: 20, radius: 16 };
const RING_LENGTH = 2 * Math.PI * RING.radius;

/** What the dashboard shows now: the year, the selected section, the crop of each section. */
function dashboardView(state, app) {
  const sections = state.farm.sections;
  const years = planYears(state.plan.data);
  const year = selectedYear(state, years);
  const frequency = state.farm.farm.time.frequencyMonths;
  const cropOf = (id) => cropOfYear(app.section(id), app.sectionPlan(id), year, frequency).id;
  const selected = sections.find((s) => s.id === state.ui.selectedSection) ?? sections[0];
  return { sections, years, year, frequency, cropOf, selected };
}

/** The score of a plan as a ring that fills up, with the number in the middle. */
function scoreRing(score, pending) {
  const filled = score === null ? 0 : (RING_LENGTH * score) / SCORE_MAX;
  return html`<span class="score-ring" title="Note du plan sur 100">
    <svg viewBox="0 0 40 40" width="${RING.size}" height="${RING.size}" aria-hidden="true">
      <circle
        class="score-ring__track"
        cx="${RING.center}"
        cy="${RING.center}"
        r="${RING.radius}"
      ></circle>
      <circle
        class="score-ring__value"
        cx="${RING.center}"
        cy="${RING.center}"
        r="${RING.radius}"
        stroke-dasharray="${filled.toFixed(1)} ${RING_LENGTH.toFixed(1)}"
      ></circle>
    </svg>
    <strong>${score === null ? (pending ? '…' : '—') : score}</strong>
  </span>`;
}

function sectionCard(state, section, sectionPlan, { year, frequency }) {
  const selected = state.ui.selectedSection === section.id;
  const { id: crop, source } = cropOfYear(section, sectionPlan, year, frequency);
  // Before its first cycle (crop still in place), a section shows its first cycle.
  const cycle =
    cycleOfYear(sectionPlan, year) ?? sectionPlan?.cycles.find((c) => c.years[0] > year) ?? null;
  const alerts = cycle?.referenceAlerts.length ?? 0;
  const score = cycle?.chosen ? Math.round(cycle.chosen.score) : null;
  return html`<article
    data-section-card="${section.id}"
    class="widget ${selected ? 'is-selected' : ''}"
  >
    <button
      type="button"
      class="widget__hit"
      data-action="open-section"
      data-id="${section.id}"
      aria-label="Consulter la rotation de la section ${section.id}"
    ></button>
    <header class="widget__head">
      <span
        class="section-badge ${selected ? 'is-dark' : ''}"
        style="view-transition-name: section-${section.id}"
        >${section.id}</span
      >
      <span class="stack-0 grow">
        <strong>Section ${section.id}</strong>
        <span class="muted small"
          >${formatNumber(section.areaHa)} ha${cycle ? ` · ${cycle.years.join('–')}` : ''}</span
        >
      </span>
      ${scoreRing(score, !sectionPlan)}
    </header>
    <div class="widget__crop">
      ${fieldSwatch(crop, 44)}
      <span class="stack-0">
        <span class="muted small"
          >${source === 'en-place' ? `En place en ${year}` : `En ${year}`}</span
        >
        <strong class="widget__crop-name">${crop ? nameOf(crop) : '—'}</strong>
      </span>
    </div>
    ${cycle?.chosen ? rotationStrip(cycle.chosen, cycle, frequency, { year }) : ''}
    ${alerts ? html`<span class="widget__flag">⚠ Rotation actuelle : ${plural(alerts, 'délai de retour non respecté', 'délais de retour non respectés')}</span>` : ''}
    <footer class="widget__foot">
      ${cycle ? decisionPill(cycle.decision) : html`<span></span>`}
      <span class="widget__link" aria-hidden="true">Consulter la rotation →</span>
    </footer>
  </article>`;
}

/** A section card with its handle, in the grid the farmer can reorder. */
function sortableCard(block, card) {
  return html`<div class="dash-block" data-sort-id="${block}">
    <button
      type="button"
      class="drag-handle"
      id="drag-${block.replace(':', '-')}"
      data-drag-handle
      data-refocus
      aria-label="Déplacer : ${blockLabel(block)}"
      aria-describedby="dash-help"
      title="Glisser pour déplacer"
    >
      ${icon(GRIP, { size: 18, width: 3.2 })}
    </button>
    ${card}
  </div>`;
}

/** What the whole farm grows this year: a pie chart and its legend, in the corner of the 3D view. */
function cropMix(state, year) {
  const hectares = Object.entries(farmMix(state.farm, state.plan.data, year));
  if (!hectares.length) return '';
  const slices = hectares.map(([crop, ha]) => ({
    label: `${nameOf(crop)} ${formatNumber(ha)} ha`,
    value: ha,
    color: colorOf(crop),
  }));
  return html`<aside class="farm3d__mix" aria-label="Cultures de la ferme en ${year}">
    ${pieChart(slices, { label: `Cultures de la ferme en ${year}` })}
    <ul class="farm3d__legend">
      ${hectares.map(
        ([crop, ha]) =>
          html`<li>
            <span class="dot" style="background: ${colorOf(crop)}"></span>${nameOf(crop)}
            <strong>${formatNumber(ha)} ha</strong>
          </li>`,
      )}
    </ul>
  </aside>`;
}

function farm3dCard(state, { sections, selected, cropOf, year }) {
  if (!selected)
    return html`<section class="card stack-md">
      <h2 class="h2">Ajoutez votre première section</h2>
      <a class="btn btn--primary" href="#/tracer">Tracer ma ferme</a>
    </section>`;
  const crop = cropOf(selected.id);
  const flatView = () =>
    isoFarm({ sections, cropOf, selectedId: selected.id, boundary: state.farm.farm.boundary });
  return html`<section class="card farm3d" aria-label="Vue 3D de la ferme">
    <div class="row-between">
      <h2 class="h2">Ma ferme en 3D</h2>
      <span class="farm3d__year">${year}</span>
    </div>
    <div class="farm3d__view">${farm3dSlot(flatView)}${cropMix(state, year)}</div>
    <div class="farm3d__selected">
      <span class="row gap-sm">
        <span class="section-badge is-dark">${selected.id}</span>
        <span class="stack-0">
          <strong>Section ${selected.id} · ${formatNumber(selected.areaHa)} ha</strong>
          <span class="muted small">${crop ? nameOf(crop) : '—'} en ${year}</span>
        </span>
      </span>
      <span class="row-wrap gap-sm">
        <a class="btn btn--primary btn--sm" href="#/section/${selected.id}/plan"
          >Consulter la rotation →</a
        >
      </span>
    </div>
  </section>`;
}

/** The year the whole page shows: a row of year buttons, or a slider for a long horizon. */
function yearPicker(years, year) {
  if (!years) return '';
  const list = Array.from({ length: years.last - years.first + 1 }, (_, i) => years.first + i);
  return html`<section class="year-bar" aria-label="Année affichée">
    <span class="year-bar__year" aria-hidden="true">${year}</span>
    ${
      list.length <= MAX_YEAR_BUTTONS
        ? html`<div class="year-ticks" role="group" aria-label="Choisir l’année">
            ${list.map((y) => html`<button type="button" class="year-tick ${y === year ? 'is-on' : ''}" data-action="set-year" data-year="${y}" aria-pressed="${String(y === year)}">${y}</button>`)}
          </div>`
        : html`<input
            aria-label="Choisir l’année"
            class="range"
            type="range"
            min="${years.first}"
            max="${years.last}"
            value="${year}"
            data-change="set-year"
          />`
    }
  </section>`;
}

/** The year picker once there is a plan; before that, why there is none yet. */
function planProgress(state, { years, year }) {
  if (state.plan.data) return yearPicker(years, year);
  if (state.plan.status === 'error') return errorBox(state.plan.error);
  if (state.plan.status === 'incomplete') return '';
  return loading('Rota prépare votre plan', askRota('chargement'));
}

export default {
  title: 'Tableau de bord',
  rota: 'tableau',
  onEnter: (app) => app.loadWeather(),
  render(state, _params, app) {
    const { farm } = state;
    const view = dashboardView(state, app);
    const { sections } = view;
    const total = sections.reduce((a, s) => a + s.areaHa, 0);
    const seeds = getSeeds(farm);
    const ids = sections.map((s) => s.id);
    const order = dashboardOrder(state.prefs.dashboard, ids);
    const time = farm.farm.time;

    return html`${appHeader(state, 'tableau')}
      <main class="page stack-md" id="main">
        ${pageTitle(
          'Ma ferme',
          html`${verbatim(farm.farm.name)} · ${formatNumber(total)} ha ·
          ${plural(sections.length, 'section', 'sections')}`,
          html`<div class="row-wrap gap-sm align-center">
            <button
              type="button"
              class="chip chip--link"
              data-action="open-settings"
              data-tab="temps"
            >
              ${icon(ICONS.calendar, { size: 16 })}Cycle de ${time.cycleYears} ans · horizon
              ${time.horizonYears} ans
            </button>
            <button
              type="button"
              class="chip chip--link"
              data-action="open-settings"
              data-tab="semences"
            >
              ${icon(ICONS.sprout, { size: 16 })}${plural(seeds.crops.length, 'semence', 'semences')}
            </button>
            <a class="chip chip--link" href="#/tracer">+ Section</a>
            ${askRota('tableau')}
          </div>`,
        )}
        ${weatherWidget(state)} ${planStatus(state)} ${planProgress(state, view)}
        <p id="dash-help" class="sr-only">
          Glissez la poignée, ou utilisez les flèches du clavier, Début et Fin, pour déplacer la
          carte.
        </p>
        <p class="sr-only" aria-live="polite">${state.ui.dashAnnounce}</p>
        <div class="dash-main">
          ${farm3dCard(state, view)}
          <div class="stack-sm">
            <div
              class="dash-sections"
              data-sortable
              data-commit="reorder-dashboard"
              aria-label="Sections de la ferme"
            >
              ${order.map((block) => {
                const id = sectionOf(block);
                return sortableCard(
                  block,
                  sectionCard(state, app.section(id), app.sectionPlan(id), view),
                );
              })}
            </div>
            ${isDefaultOrder(order, ids) ? '' : html`<button type="button" class="link-btn small" data-action="reset-dashboard">Ordre de la ferme</button>`}
          </div>
        </div>
      </main>`;
  },
  /** After every render: the 3D scene goes back in its place and learns what changed. */
  mount(app) {
    const state = app.state;
    const { sections, cropOf, selected } = dashboardView(state, app);
    if (!selected) return;
    document.querySelectorAll('[data-section-card]').forEach((card) => {
      const highlight = () => highlightFarm3d(card.dataset.sectionCard);
      const reset = () => highlightFarm3d(null);
      card.addEventListener('pointerenter', highlight);
      card.addEventListener('pointerleave', reset);
      card.addEventListener('focusin', highlight);
      card.addEventListener('focusout', reset);
    });
    const crops = Object.fromEntries(
      sections.map((s) => {
        const crop = cropOf(s.id);
        return [s.id, { texture: textureOf(crop), name: crop ? nameOf(crop) : '—' }];
      }),
    );
    showFarm3d(
      {
        sections: sections.map((s) => ({ id: s.id, polygon: s.polygon ?? null })),
        boundary: state.farm.farm.boundary ?? null,
        crops,
        selectedId: selected.id,
      },
      (id) => app.update((s) => (s.ui.selectedSection = id)),
    );
  },
  unmount: () => closeFarm3d(),
  actions: {
    'open-section': (app, el) => app.go(`#/section/${el.dataset.id}/plan`),
    'retry-weather': (app) => app.loadWeather({ force: true }),
    'reorder-dashboard': (app, _list, { ids, moved }) =>
      app.update((s) => {
        s.prefs.dashboard = ids;
        const i = ids.indexOf(moved);
        s.ui.dashAnnounce = moved ? `${blockLabel(moved)} : place ${i + 1} sur ${ids.length}` : '';
      }),
    'reset-dashboard': (app) =>
      app.update((s) => {
        s.prefs.dashboard = null;
        s.ui.dashAnnounce = 'Ordre de la ferme rétabli';
      }),
  },
};
