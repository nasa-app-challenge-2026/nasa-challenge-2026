/**
 * 4 · Tracer la ferme et ses sections. Owner: Loïc.
 * Two steps on a Leaflet map (home-made polygon editor, frontend/ui/drawMap.js):
 *   1. Contour: click the main corners of the farm → `farm.boundary`.
 *   2. Sections, once the outline is closed: click the corners of each section
 *      the same way → `section.polygon`. Corners snap to the outline and to the
 *      other sections, so sections meet without gaps.
 * The area of a section is computed from its polygon. These polygons are what
 * the 3D view (tableau) and the section map (champ) draw later.
 */
import { html, plural } from '../lib/html.js';
import { onboardingHeader } from '../ui/layout.js';
import { icon, ICONS } from '../ui/icons.js';
import { mapSlot, ensureMap, destroyMap } from '../ui/leafletMap.js';
import { createPolygonEditor } from '../ui/drawMap.js';
import {
  areaHa,
  bounds,
  distanceToBoundsM,
  isClosed,
  roundHa,
} from '../../application/rules/geo.js';
import { blankSection } from '../../application/rules/sectionInputs.js';
import { followOutline } from '../../application/rules/sections.js';

const KEY = 'tracer';
const LETTERS = 'ABCDEFGHIJ';
/** Area of a section before it is drawn (then computed from its polygon). */
const NEW_SECTION_AREA_HA = 5;
const FARM_COLOR = '#FFD27A';
const SECTION_COLOR = '#0072B2';
/** Shapes this far from the farm pin were drawn for another place (e.g. the demo farm). */
const STALE_SHAPES_M = 2000;

let editor = null;

const pointsOf = (state, target) =>
  target === 'farm'
    ? (state.farm.farm.boundary ?? [])
    : (state.farm.sections.find((s) => s.id === target)?.polygon ?? []);

/** Sections in letter order (A, B, C…), so they are listed and drawn in that order. */
const sortSections = (farm) => farm.sections.sort((a, b) => a.id.localeCompare(b.id));

const shapesBounds = (farm) =>
  bounds([farm.farm.boundary ?? [], ...farm.sections.map((x) => x.polygon ?? [])]);

/**
 * The pin was moved far from what is drawn (Localisation only moves the pin):
 * the outline and section shapes belong to the old place, so they are cleared
 * and the drawing starts again at the new one. Sections and rotations stay.
 */
function dropStaleShapes(s) {
  const b = shapesBounds(s.farm);
  const loc = s.farm.farm.location;
  if (!b || typeof loc?.lat !== 'number' || typeof loc?.lon !== 'number') return;
  if (distanceToBoundsM(b, [loc.lat, loc.lon]) <= STALE_SHAPES_M) return;
  s.farm.farm.boundary = [];
  for (const sec of s.farm.sections) sec.polygon = [];
}

/**
 * Change the corners of the outline or of a section. Sections follow a dragged
 * outline corner; a shape left with fewer than 3 corners goes back to drawing.
 */
function setPoints(app, target, pts) {
  let planChanged = false;
  app.update((s) => {
    if (!isClosed(pts)) s.ui.draw.drawing = true;
    if (target === 'farm') {
      const before = s.farm.farm.boundary ?? [];
      s.farm.farm.boundary = pts;
      planChanged = followOutline(s.farm, before);
      return;
    }
    const sec = s.farm.sections.find((x) => x.id === target);
    if (!sec) return;
    sec.polygon = pts;
    if (isClosed(pts)) {
      const ha = Math.max(0.1, roundHa(areaHa(pts)));
      planChanged = ha !== sec.areaHa;
      sec.areaHa = ha;
    }
  });
  if (planChanged) app.refreshPlan();
}

/** What to draw next: the outline first, then each section still to draw, in order. */
function nextTarget(state, after = null) {
  if (!isClosed(state.farm.farm.boundary)) return { target: 'farm', drawing: true };
  const sections = state.farm.sections;
  const from = sections.findIndex((s) => s.id === after) + 1;
  const todo = [...sections.slice(from), ...sections.slice(0, from)].find(
    (s) => !isClosed(s.polygon),
  );
  if (todo) return { target: todo.id, drawing: true };
  return { target: after && after !== 'farm' ? after : sections[0].id, drawing: false };
}

/** A shape was closed: save it and move on to the next one to draw. */
function finish(app, id, pts) {
  setPoints(app, id, pts);
  app.update((s) => {
    s.ui.draw = nextTarget(s, id);
    if (s.ui.draw.target !== 'farm') s.ui.selectedSection = s.ui.draw.target;
  });
}

function hint(draw, pts) {
  const onFarm = draw.target === 'farm';
  const who = onFarm ? 'Contour' : `Section ${draw.target}`;
  const n = pts.length;
  if (draw.drawing) {
    if (n < 3) {
      return onFarm
        ? `Contour · cliquez les coins principaux de la ferme (${n}/3 minimum)`
        : `Section ${draw.target} · cliquez ses coins ; ils s’aimantent au contour (${n}/3 minimum)`;
    }
    return `${who} · ajoutez d’autres coins au besoin, ou cliquez sur le premier coin (ou double-cliquez) pour fermer`;
  }
  if (!n) return `${who} · appuyez sur « Dessiner » puis cliquez sur la carte`;
  return `${who} · glissez les coins blancs pour ajuster · clic droit sur un coin pour l’enlever`;
}

/** Dessiner / Annuler un coin / Effacer, and « Fermer » once there are 3 corners. */
function drawTools(draw, pts, what) {
  const closed = isClosed(pts);
  return html`<div class="tool-grid">
      <button
        type="button"
        class="tool ${draw.drawing ? 'is-on' : ''}"
        data-action="draw-start"
        aria-pressed="${String(draw.drawing)}"
      >
        ${icon(ICONS.draw, { size: 20 })}${closed && !draw.drawing ? 'Redessiner' : 'Dessiner'}
      </button>
      <button type="button" class="tool" data-action="draw-undo" ${pts.length ? '' : 'disabled'}>
        ${icon(ICONS.undo, { size: 20 })}Annuler un coin
      </button>
      <button type="button" class="tool" data-action="draw-clear" ${pts.length ? '' : 'disabled'}>
        ${icon(ICONS.trash, { size: 20 })}Effacer
      </button>
    </div>
    ${
      draw.drawing && pts.length >= 3
        ? html`<button type="button" class="btn btn--primary" data-action="draw-finish">
            Fermer ${what} (${plural(pts.length, 'coin', 'coins')}) →
          </button>`
        : ''
    }`;
}

export default {
  title: 'Tracer la ferme',

  onEnter(app) {
    app.update((s) => {
      dropStaleShapes(s);
      sortSections(s.farm);
      s.ui.draw = nextTarget(s);
      if (s.ui.draw.target !== 'farm') s.ui.selectedSection = s.ui.draw.target;
    });
  },

  render(state) {
    const sections = state.farm.sections;
    const draw = state.ui.draw;
    const boundary = state.farm.farm.boundary ?? [];
    const farmDone = isClosed(boundary);
    const onFarm = draw.target === 'farm';
    const pts = pointsOf(state, draw.target);
    const traced = sections.filter((s) => isClosed(s.polygon));
    const total = roundHa(traced.reduce((a, s) => a + s.areaHa, 0));

    return html`${onboardingHeader(3)}
      <div class="split" id="main">
        <aside class="split__side stack-md">
          <div class="stack-xs">
            <h1 class="h1">Tracez votre ferme</h1>
            <p class="muted">
              Cliquez d’abord les coins principaux pour relier le contour de la ferme, puis les
              coins de chaque section. L’appli planifiera chaque section à partir de ce qui y
              pousse.
            </p>
          </div>

          <div class="stack-xs">
            <span class="eyebrow">1 · Contour</span>
            <div class="list-row ${onFarm ? 'is-selected' : ''}">
              <button
                type="button"
                class="list-row__main"
                data-action="draw-target"
                data-id="farm"
                aria-pressed="${String(onFarm)}"
              >
                <span class="section-badge section-badge--farm"
                  >${icon(ICONS.draw, { size: 18 })}</span
                ><span class="stack-0"
                  ><strong>Contour de la ferme</strong
                  ><span class="muted small"
                    >${
                      farmDone
                        ? `${boundary.length} coins · ${roundHa(areaHa(boundary))} ha`
                        : boundary.length
                          ? `${plural(boundary.length, 'coin posé', 'coins posés')} · continuez`
                          : 'Pas encore tracé'
                    }</span
                  ></span
                >
              </button>
              ${farmDone ? html`<span class="pill pill--info">✓</span>` : ''}
            </div>
            ${onFarm ? drawTools(draw, pts, 'le contour') : ''}
            ${
              onFarm && farmDone && !draw.drawing
                ? html`<button type="button" class="btn btn--primary" data-action="next-section">
                    Tracer les sections →
                  </button>`
                : ''
            }
          </div>

          <div class="stack-xs">
            <div class="row-between">
              <span class="eyebrow">2 · Sections</span>${
                farmDone
                  ? html`<strong>${traced.length}/${sections.length} tracées · ${total} ha</strong>`
                  : ''
              }
            </div>
            ${
              farmDone
                ? html`${sections.map((s) => {
                      const on = s.id === draw.target;
                      const done = isClosed(s.polygon);
                      return html`<div class="list-row ${on ? 'is-selected' : ''}">
                        <button
                          type="button"
                          class="list-row__main"
                          data-action="draw-target"
                          data-id="${s.id}"
                          aria-pressed="${String(on)}"
                        >
                          <span class="section-badge ${on ? 'is-blue' : ''}">${s.id}</span
                          ><span class="stack-0"
                            ><strong>Section ${s.id}</strong
                            ><span class="muted small"
                              >${done ? `${s.areaHa} ha` : 'À tracer'}</span
                            ></span
                          >
                        </button>
                        ${
                          sections.length > 1
                            ? html`<button
                                type="button"
                                class="icon-btn"
                                data-action="remove-section"
                                data-id="${s.id}"
                                aria-label="Supprimer la section ${s.id}"
                              >
                                ${icon(ICONS.trash, { size: 18 })}
                              </button>`
                            : ''
                        }
                      </div>`;
                    })}
                    <button
                      type="button"
                      class="btn btn--dashed"
                      data-action="add-section"
                      ${sections.length >= LETTERS.length ? 'disabled' : ''}
                    >
                      ${icon(ICONS.plus, { size: 18 })}Nouvelle section
                    </button>
                    ${onFarm ? '' : drawTools(draw, pts, `la section ${draw.target}`)}`
                : html`<p class="muted small">
                    Fermez d’abord le contour, puis tracez chaque section de la même façon.
                  </p>`
            }
          </div>

          <div class="card card--tint small">
            ${
              onFarm
                ? 'Astuce : cliquez seulement les coins principaux, pas chaque courbe. Vous pourrez glisser les coins pour ajuster.'
                : 'Astuce : une section = une partie de la ferme qui a la même culture la même année. Ses coins s’aimantent au contour et aux autres sections, pour qu’elles se touchent sans trou.'
            }
          </div>
        </aside>

        <div class="split__main map-screen map-screen--inset">
          ${mapSlot(KEY, 'Carte pour tracer la ferme et ses sections')}
          <div class="map-hint" aria-live="polite">${hint(draw, pts)}</div>
          <div class="map-actions">
            <a class="btn btn--secondary" href="#/localisation">Retour</a>
            <a class="btn btn--primary" href="#/cultures"
              >Valider ${plural(sections.length, 'section', 'sections')} →</a
            >
          </div>
        </div>
      </div>`;
  },

  mount(app) {
    const s = app.state;
    const loc = s.farm.farm.location;
    const { map, created } = ensureMap(KEY, { center: [loc.lat, loc.lon], zoom: 15 });
    if (created) {
      const b = shapesBounds(s.farm);
      // maxZoom: a lone corner has an empty box, which would zoom in all the way.
      if (b) map.fitBounds(b, { padding: [60, 60], maxZoom: 17 });
      editor = createPolygonEditor(map, {
        onChange: (id, pts) => setPoints(app, id, pts),
        onFinish: (id, pts) => finish(app, id, pts),
      });
    }
    editor.sync({
      shapes: [
        {
          id: 'farm',
          points: s.farm.farm.boundary ?? [],
          color: FARM_COLOR,
          dashed: true,
          fill: false,
        },
        ...s.farm.sections.map((sec) => ({
          id: sec.id,
          points: sec.polygon ?? [],
          color: SECTION_COLOR,
          label: isClosed(sec.polygon) ? `${sec.id} · ${sec.areaHa} ha` : null,
        })),
      ],
      activeId: s.ui.draw.target,
      drawing: s.ui.draw.drawing,
    });
  },

  unmount() {
    destroyMap(KEY);
    editor = null;
  },

  actions: {
    'draw-target': (app, el) =>
      app.update((s) => {
        const id = el.dataset.id;
        if (id !== 'farm' && !isClosed(s.farm.farm.boundary)) return;
        s.ui.draw = { target: id, drawing: !isClosed(pointsOf(s, id)) };
        if (id !== 'farm') s.ui.selectedSection = id;
      }),
    'next-section': (app) =>
      app.update((s) => {
        s.ui.draw = nextTarget(s, 'farm');
        if (s.ui.draw.target !== 'farm') s.ui.selectedSection = s.ui.draw.target;
      }),
    'draw-start': (app) => {
      const { target, drawing } = app.state.ui.draw;
      if (drawing) return;
      if (isClosed(pointsOf(app.state, target))) {
        setPoints(app, target, []); // « Redessiner »
      } else {
        app.update((s) => {
          s.ui.draw.drawing = true;
        });
      }
    },
    'draw-undo': (app) => {
      const { target } = app.state.ui.draw;
      setPoints(app, target, pointsOf(app.state, target).slice(0, -1));
    },
    'draw-clear': (app) => setPoints(app, app.state.ui.draw.target, []),
    'draw-finish': (app) => {
      const { target } = app.state.ui.draw;
      const pts = pointsOf(app.state, target);
      if (isClosed(pts)) finish(app, target, pts);
    },
    'add-section': (app) => {
      const used = new Set(app.state.farm.sections.map((s) => s.id));
      const id = [...LETTERS].find((l) => !used.has(l));
      if (!id) return;
      app.updateFarm((farm) => {
        farm.sections.push({ ...blankSection(id), areaHa: NEW_SECTION_AREA_HA });
        sortSections(farm);
      });
      app.update((s) => {
        s.ui.selectedSection = id;
        s.ui.draw = { target: id, drawing: true };
      });
    },
    'remove-section': (app, el) => {
      app.updateFarm((farm, s) => {
        farm.sections = farm.sections.filter((x) => x.id !== el.dataset.id);
        if (s.ui.selectedSection === el.dataset.id) s.ui.selectedSection = farm.sections[0].id;
        if (s.ui.draw.target === el.dataset.id) s.ui.draw = nextTarget(s);
      });
    },
  },
};
