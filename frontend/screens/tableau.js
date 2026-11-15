/**
 * 7 · Tableau de bord de la ferme. Owner: Ali.
 * The year slider on top moves the whole page. Under it, a grid of blocks the farmer can reorder
 * by dragging (or with the keyboard): weather, isometric farm, what the whole farm grows, and
 * one card per section with the rotation of its cycle (the crop of the year is ringed), keep or
 * change and the score. The order is a per-browser preference (prefs.dashboard).
 */
import { html, plural } from '../lib/html.js';
import { colorOf, nameOf } from '../../data/reference/crops.js';
import { cropOfYear, cycleOfYear, farmMix, planYears } from '../../application/rules/planView.js';
import { getSeeds } from '../../application/rules/seeds.js';
import { blockLabel, dashboardOrder, isDefaultOrder, secBlock } from '../lib/dashboard.js';
import { appHeader, pageTitle } from '../ui/layout.js';
import { icon, ICONS } from '../ui/icons.js';
import { isoFarm } from '../ui/isoFarm.js';
import { errorBox, loading } from '../ui/widgets.js';
import { askRota } from '../ui/rota.js';
import { weatherWidget } from '../ui/weatherWidget.js';
import { decisionPill, planStatus, selectedYear } from '../ui/planWidgets.js';
import { rotationStrip } from '../ui/rotationViews.js';

const GRIP = 'M9 6h.01M15 6h.01M9 12h.01M15 12h.01M9 18h.01M15 18h.01';
/** Beyond this many years, the slider replaces the row of year buttons. */
const MAX_YEAR_BUTTONS = 14;

function sectionWidget(state, section, year, sectionPlan) {
  const sel = state.ui.selectedSection === section.id;
  const f = state.farm.farm.time.frequencyMonths;
  const { id: crop, source } = cropOfYear(section, sectionPlan, year, f);
  // Before its first cycle (crop still in place), a section shows its first cycle.
  const cycle =
    cycleOfYear(sectionPlan, year) ?? sectionPlan?.cycles.find((c) => c.years[0] > year) ?? null;
  const alerts = cycle?.referenceAlerts.length ?? 0;
  return html`<article class="widget ${sel ? 'is-selected' : ''}">
    <button
      type="button"
      class="widget__hit"
      data-action="select-section"
      data-id="${section.id}"
      aria-pressed="${String(sel)}"
      aria-label="Section ${section.id}"
    ></button>
    <div class="row-between">
      <span class="row gap-sm"
        ><span
          class="section-badge ${sel ? 'is-dark' : ''}"
          style="view-transition-name: section-${section.id}"
          >${section.id}</span
        ><span class="stack-0"
          ><strong>Section ${section.id}</strong
          ><span class="muted small">${section.areaHa} ha</span></span
        ></span
      ><span class="widget__score" title="Note du plan sur 100"
        >${cycle?.chosen ? Math.round(cycle.chosen.score) : sectionPlan ? '—' : '…'}</span
      >
    </div>
    <div class="row-between small">
      <span class="muted">${source === 'en-place' ? `En place en ${year}` : `En ${year}`}</span>
      <strong>${crop ? nameOf(crop) : '—'}</strong>
    </div>
    ${
      cycle?.chosen
        ? html`${rotationStrip(cycle.chosen, cycle, f, { year })}
            <div class="row-between small">
              ${decisionPill(cycle.decision)}
              <span class="muted">${cycle.years.join('–')}</span>
            </div>`
        : ''
    }
    ${alerts ? html`<span class="widget__flag">⚠ Rotation actuelle : ${plural(alerts, 'délai de retour non respecté', 'délais de retour non respectés')}</span>` : ''}
    <a class="widget__link" href="#/section/${section.id}/plan">Voir les rotations →</a>
  </article>`;
}

function mixCard(state, year) {
  const area = farmMix(state.farm, state.plan.data, year);
  const entries = Object.entries(area);
  return html`<section class="card stack-sm" aria-label="Toute la ferme en ${year}">
    <h2 class="h2">Toute la ferme en ${year}</h2>
    ${
      entries.length
        ? html`<div class="mix-bar">
              ${entries.map(([c, ha]) => html`<span style="flex: ${ha} 1 0; background: ${colorOf(c)}">${ha} ha</span>`)}
            </div>
            <div class="row-wrap gap-sm small muted">
              ${entries.map(([c, ha]) => html`<span class="row gap-xs"><span class="dot" style="background: ${colorOf(c)}"></span>${nameOf(c)} · ${ha} ha</span>`)}
            </div>`
        : html`<span class="muted small">Pas encore de plan pour cette année.</span>`
    }
  </section>`;
}

function farm3dCard(state, { sections, sel, cropOf }) {
  return html`<section class="card stack-sm farm3d" aria-label="Vue 3D de la ferme">
    <h2 class="h2">Ma ferme en 3D</h2>
    <div class="iso-wrap">
      ${isoFarm({ sections, cropOf, selectedId: sel.id, boundary: state.farm.farm.boundary })}
    </div>
    <div class="card card--tint row-between wrap">
      <strong>Section ${sel.id} · ${sel.areaHa} ha</strong>
      <div class="row-wrap gap-sm">
        <a class="btn btn--secondary btn--sm" href="#/section/${sel.id}/parcelle">Ma parcelle</a
        ><a class="btn btn--primary btn--sm" href="#/section/${sel.id}/plan"
          >Voir les rotations →</a
        >
      </div>
    </div>
  </section>`;
}

function block(id, content) {
  const kind = id.startsWith('sec:') ? 'section' : id;
  const label = blockLabel(id);
  return html`<div class="dash-block dash-block--${kind}" data-sort-id="${id}">
    <button
      type="button"
      class="drag-handle"
      id="drag-${id.replace(':', '-')}"
      data-drag-handle
      data-refocus
      aria-label="Déplacer : ${label}"
      aria-describedby="dash-help"
      title="Glisser pour déplacer"
    >
      ${icon(GRIP, { size: 18, width: 3.2 })}
    </button>
    ${content}
  </div>`;
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

export default {
  title: 'Tableau de bord',
  rota: 'tableau',
  onEnter: (app) => app.loadWeather(),
  render(state, _params, app) {
    const { farm } = state;
    const sections = farm.sections;
    const years = planYears(state.plan.data);
    const year = selectedYear(state, years);
    const sel = sections.find((s) => s.id === state.ui.selectedSection) ?? sections[0];
    const f = farm.farm.time.frequencyMonths;
    const cropOf = (id) => cropOfYear(app.section(id), app.sectionPlan(id), year, f).id;
    const total = sections.reduce((a, s) => a + s.areaHa, 0);
    const seeds = getSeeds(farm);
    const ids = sections.map((s) => s.id);
    const order = dashboardOrder(state.prefs.dashboard, ids);
    const time = farm.farm.time;
    const content = {
      weather: () => weatherWidget(state),
      farm3d: () => farm3dCard(state, { sections, sel, cropOf }),
      mix: () => mixCard(state, year),
    };
    for (const s of sections)
      content[secBlock(s.id)] = () => sectionWidget(state, s, year, app.sectionPlan(s.id));

    return html`${appHeader(state, 'tableau')}
      <main class="page stack-lg" id="main">
        ${pageTitle(
          'Ma ferme',
          `${farm.farm.name} · ${total} ha · ${plural(sections.length, 'section', 'sections')}`,
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
        ${planStatus(state)}
        ${
          state.plan.data
            ? yearPicker(years, year)
            : state.plan.status === 'error'
              ? errorBox(state.plan.error)
              : state.plan.status === 'incomplete'
                ? ''
                : loading('Rota prépare votre plan', askRota('chargement'))
        }
        <p id="dash-help" class="sr-only">
          Glissez la poignée, ou utilisez les flèches du clavier, Début et Fin, pour déplacer le
          bloc.
        </p>
        <p class="sr-only" aria-live="polite">${state.ui.dashAnnounce}</p>
        <div
          class="dash-grid"
          data-sortable
          data-commit="reorder-dashboard"
          aria-label="Blocs du tableau de bord"
        >
          ${order.map((id) => block(id, content[id]()))}
        </div>
        ${isDefaultOrder(order, ids) ? '' : html`<button type="button" class="link-btn small" data-action="reset-dashboard">Disposition par défaut</button>`}
      </main>`;
  },
  actions: {
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
        s.ui.dashAnnounce = 'Disposition par défaut rétablie';
      }),
  },
};
