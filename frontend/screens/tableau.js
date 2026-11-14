/**
 * 6 · Tableau de bord de la ferme. Owner: Ali.
 * A grid of blocks the farmer can reorder by dragging (or with the keyboard):
 * weather, isometric farm, farm mix with the "Décaler mes sections" helper,
 * and one widget per section. The order is a per-browser preference
 * (prefs.dashboard, see frontend/lib/dashboard.js). The year slider stays below.
 */
import { html, plural, fmt } from '../lib/html.js';
import { CROPS } from '../../data/reference/crops.js';
import {
  bestOffsets,
  buildCalendar,
  currentCropConflict,
  cycleLength,
  farmMix,
  toSlots,
} from '../../application/rules/rotation.js';
import { getSeeds, missingSeeds } from '../../application/rules/seeds.js';
import { blockLabel, dashboardOrder, isDefaultOrder, secBlock } from '../lib/dashboard.js';
import { appHeader, pageTitle } from '../ui/layout.js';
import { icon, ICONS } from '../ui/icons.js';
import { isoFarm } from '../ui/isoFarm.js';
import { fieldStrip } from '../ui/textures.js';
import { errorBox } from '../ui/widgets.js';
import { weatherWidget } from '../ui/weatherWidget.js';

const GRIP = 'M9 6h.01M15 6h.01M9 12h.01M15 12h.01M9 18h.01M15 18h.01';

function sectionWidget(state, s, yi, plan) {
  const L = cycleLength(s.rotation);
  const pos = (yi + (s.offset ?? 0)) % L;
  const slots = toSlots(s.rotation);
  const crop = slots[pos]?.crop;
  const sel = state.ui.selectedSection === s.id;
  const conflict = currentCropConflict(s);
  const noSeed = missingSeeds(state.farm, s.rotation);
  const score = plan?.scores
    ? Math.round(
        (plan.scores.eau + plan.scores.sol + plan.scores.resilience + plan.scores.revenu) / 4,
      )
    : null;
  return html`<article class="widget ${sel ? 'is-selected' : ''}">
    <button
      type="button"
      class="widget__hit"
      data-action="select-section"
      data-id="${s.id}"
      aria-pressed="${String(sel)}"
      aria-label="Section ${s.id}"
    ></button>
    <div class="row-between">
      <span class="row gap-sm"
        ><span
          class="section-badge ${sel ? 'is-dark' : ''}"
          style="view-transition-name: section-${s.id}"
          >${s.id}</span
        ><span class="stack-0"
          ><strong>Section ${s.id}</strong
          ><span class="muted small">${s.areaHa} ha · cycle de ${L} ans</span></span
        ></span
      ><span class="widget__score" title="Score moyen">${score ?? '…'}</span>
    </div>
    ${fieldStrip(crop, 44)}
    <div class="cycle-chips">
      ${slots.map((x, i) => html`<span class="cycle-chip ${i === pos ? 'is-current' : ''}" style="background: ${CROPS[x.crop]?.color || '#E5E9E0'}">${CROPS[x.crop]?.name ?? '—'}</span>`)}
    </div>
    <div class="row-between small">
      <span class="muted">Année ${pos + 1} sur ${L} du cycle</span
      ><strong>${CROPS[crop]?.name ?? '—'}</strong>
    </div>
    ${
      conflict || noSeed.length
        ? html`<span class="widget__flag" title="${conflict ?? ''}"
            >⚠
            ${
              conflict
                ? 'Répète la culture actuelle'
                : `Sans semences de ${noSeed.map((c) => CROPS[c].name.toLowerCase()).join(', ')}`
            }</span
          >`
        : ''
    }
    <div class="bar widget__bar">
      <div class="bar__fill is-blue" style="width: ${score ?? 0}%"></div>
    </div>
  </article>`;
}

function mixCard(state, { year, thisYear, bad, sections }) {
  const { farm } = state;
  const conflicts = sections.filter((s) => currentCropConflict(s));
  const best = bestOffsets(farm.farm, sections);
  const canShift =
    best.conflicts < conflicts.length ||
    (best.conflicts === conflicts.length && best.imbalanced < bad);
  const shifted = sections.some((s) => s.offset);
  return html`<section class="card stack-sm" aria-label="Toute la ferme en ${year}">
    <h2 class="h2">Sur toute la ferme en ${year}</h2>
    <div class="mix-bar">
      ${Object.entries(thisYear.areaByCrop).map(([c, ha]) => html`<span style="flex: ${ha} 1 0; background: ${CROPS[c].color}">${ha} ha</span>`)}
    </div>
    <div class="row-wrap gap-sm small muted">
      ${Object.entries(thisYear.areaByCrop).map(([c, ha]) => html`<span class="row gap-xs"><span class="dot" style="background: ${CROPS[c].color}"></span>${CROPS[c].name} · ${ha} ha</span>`)}
    </div>
    ${conflicts.map(
      (s) =>
        html`<span class="small text-warn strong"
          >⚠ Section ${s.id} : ${currentCropConflict(s)}</span
        >`,
    )}
    <div class="row-between wrap divider-top mix-foot">
      <div class="stack-0">
        ${
          thisYear.balanced
            ? html`<strong class="text-good"
                >✓ Une culture différente par section cette année</strong
              >`
            : html`<strong class="text-warn"
                >⚠
                ${thisYear.duplicates.map((c) => `${thisYear.sectionsByCrop[c]} sections en ${CROPS[c].name.toLowerCase()}`).join(', ')}
                cette année</strong
              >`
        }
        <span class="muted small"
          >Sur ${farm.farm.horizonYears} ans :
          ${plural(bad, 'année déséquilibrée', 'années déséquilibrées')}</span
        >
      </div>
      <div class="row-wrap gap-sm">
        ${shifted ? html`<button type="button" class="btn btn--secondary btn--sm" data-action="unshift">Annuler le décalage</button>` : ''}
        ${
          canShift
            ? html`<button type="button" class="btn btn--dark btn--sm" data-action="shift">
                Décaler mes sections
              </button>`
            : html`<span class="pill pill--info pill--lg">✓ Sections décalées au mieux</span>`
        }
      </div>
    </div>
  </section>`;
}

function farm3dCard(state, { sections, sel, cropOf }) {
  return html`<section class="card stack-sm farm3d" aria-label="Vue 3D de la ferme">
    <div class="row-between">
      <h2 class="h2">Ma ferme en 3D</h2>
      <span class="muted small">Texture = culture de l’année</span>
    </div>
    <div class="iso-wrap">
      ${isoFarm({ sections, cropOf, selectedId: sel.id, boundary: state.farm.farm.boundary })}
    </div>
    <div class="card card--tint row-between wrap">
      <div class="stack-0">
        <strong>Section ${sel.id} · ${sel.areaHa} ha</strong
        ><span class="muted small"
          >${sel.rotation.map((e) => `${CROPS[e.crop]?.name ?? '—'}${e.years > 1 ? ` (${e.years} ans)` : ''}`).join(' → ')}</span
        >
      </div>
      <div class="row-wrap gap-sm">
        <a class="btn btn--secondary btn--sm" href="#/section/${sel.id}/rotation"
          >Modifier la rotation</a
        ><a class="btn btn--primary btn--sm" href="#/section/${sel.id}/champ"
          >Ouvrir la section →</a
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

export default {
  title: 'Tableau de bord',
  rota: 'tableau',
  onEnter: (app) => app.loadWeather(),
  render(state, _params, app) {
    const { farm } = state;
    const sections = farm.sections;
    const yi = Math.min(state.ui.yearIndex, farm.farm.horizonYears - 1);
    const year = farm.farm.startYear + yi;
    const mix = farmMix(farm.farm, sections);
    const thisYear = mix[yi];
    const bad = mix.filter((y) => !y.balanced).length;
    const sel = sections.find((s) => s.id === state.ui.selectedSection) ?? sections[0];
    const cropOf = (id) => {
      const s = sections.find((x) => x.id === id);
      return buildCalendar(s.rotation, {
        offset: s.offset,
        startYear: farm.farm.startYear,
        horizonYears: farm.farm.horizonYears,
      })[yi]?.crop;
    };
    const total = sections.reduce((a, s) => a + s.areaHa, 0);
    const planFarm = state.plan.data?.farm;
    const seeds = getSeeds(farm);
    const ids = sections.map((s) => s.id);
    const order = dashboardOrder(state.prefs.dashboard, ids);

    const content = {
      weather: () => weatherWidget(state),
      farm3d: () => farm3dCard(state, { sections, sel, cropOf }),
      mix: () => mixCard(state, { year, thisYear, bad, sections }),
    };
    for (const s of sections) {
      content[secBlock(s.id)] = () => sectionWidget(state, s, yi, app.sectionPlan(s.id));
    }

    return html`${appHeader(state, 'tableau')}
      <main class="page stack-lg" id="main">
        ${pageTitle(
          `Ma ferme · ${total} ha · ${plural(sections.length, 'section', 'sections')}`,
          `${farm.farm.name} · ${farm.farm.location?.label ?? ''}`,
          html`<div class="row-wrap gap-sm">
            <span class="chip"
              >${icon(ICONS.calendar, { size: 16 })}Analyse sur ${farm.farm.horizonYears} ans ·
              ${farm.farm.startYear} à ${farm.farm.startYear + farm.farm.horizonYears - 1}</span
            >
            ${planFarm ? html`<span class="chip chip--strong">Score de la ferme ${planFarm.score} · ${fmt(planFarm.revenuePerYear)} $ par an</span>` : ''}
            <button
              type="button"
              class="chip chip--link"
              data-action="open-settings"
              data-tab="semences"
            >
              ${icon(ICONS.sprout, { size: 16 })}Mes semences ·
              ${plural(seeds.crops.length, 'culture', 'cultures')}
            </button>
            <a class="chip chip--link" href="#/tracer">+ Ajouter une section</a>
          </div>`,
        )}
        ${state.plan.status === 'error' ? errorBox(state.plan.error) : ''}
        <div class="dash-toolbar">
          <span class="muted small row gap-xs"
            >${icon(GRIP, { size: 16, width: 3.2 })}Glissez les poignées pour réorganiser vos
            blocs</span
          >
          ${
            isDefaultOrder(order, ids)
              ? ''
              : html`<button type="button" class="link-btn small" data-action="reset-dashboard">
                  Disposition par défaut
                </button>`
          }
        </div>
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
        <section class="card stack-sm" aria-label="Curseur des années">
          <div class="row-between wrap">
            <label for="year" class="strong">Curseur des années</label
            ><span class="h2 text-brand"
              >${year} · année ${yi + 1} sur ${farm.farm.horizonYears}</span
            >
          </div>
          <input
            id="year"
            class="range"
            type="range"
            min="0"
            max="${farm.farm.horizonYears - 1}"
            value="${yi}"
            data-change="set-year"
          />
          <div class="year-ticks">
            ${mix.map((y, i) => html`<button type="button" class="year-tick ${i === yi ? 'is-on' : ''} ${y.balanced ? '' : 'is-warn'}" data-action="pick-year" data-i="${i}" aria-label="${y.year}${y.balanced ? '' : ', année déséquilibrée'}">${y.year}${y.balanced ? '' : ' ⚠'}</button>`)}
          </div>
        </section>
      </main>`;
  },
  actions: {
    'set-year': (app, el) => app.update((s) => (s.ui.yearIndex = Number(el.value))),
    'pick-year': (app, el) => app.update((s) => (s.ui.yearIndex = Number(el.dataset.i))),
    shift: (app) => {
      const { offsets } = bestOffsets(app.state.farm.farm, app.state.farm.sections);
      app.updateFarm((farm) => farm.sections.forEach((s) => (s.offset = offsets[s.id] ?? 0)));
    },
    unshift: (app) => app.updateFarm((farm) => farm.sections.forEach((s) => (s.offset = 0))),
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
