/**
 * 4 · Tracer la ferme et ses sections. Owner: Loïc.
 * Leaflet map with a home-made polygon editor (src/ui/drawMap.js). The farm
 * outline goes to `farm.boundary`, each section to `section.polygon`; the
 * area of a section is computed from its polygon. These polygons are what
 * the 3D view (tableau) and the section map (champ) draw later.
 */
import { html, plural } from '../lib/html.js';
import { onboardingHeader } from '../ui/layout.js';
import { icon, ICONS } from '../ui/icons.js';
import { mapSlot, ensureMap, destroyMap } from '../ui/leafletMap.js';
import { createPolygonEditor } from '../ui/drawMap.js';
import { areaHa, bounds, isClosed, roundHa } from '../lib/geo.js';
import { autoStagger } from '../lib/rotation.js';

const KEY = 'tracer';
const LETTERS = 'ABCDEFGHIJ';
const DEFAULT_ROTATION = [
  { crop: 'mais', years: 1, cover: null },
  { crop: 'soya', years: 1, cover: null },
  { crop: 'ble', years: 1, cover: null },
];
const FARM_COLOR = '#FFD27A';
const SECTION_COLOR = '#0072B2';

let editor = null;

const pointsOf = (state, target) =>
  target === 'farm'
    ? (state.farm.farm.boundary ?? [])
    : (state.farm.sections.find((s) => s.id === target)?.polygon ?? []);

function setPoints(app, target, pts) {
  let areaChanged = false;
  app.update((s) => {
    if (target === 'farm') {
      s.farm.farm.boundary = pts;
      return;
    }
    const sec = s.farm.sections.find((x) => x.id === target);
    if (!sec) return;
    sec.polygon = pts;
    if (isClosed(pts)) {
      const ha = Math.max(0.1, roundHa(areaHa(pts)));
      areaChanged = ha !== sec.areaHa;
      sec.areaHa = ha;
    }
  });
  if (areaChanged) app.refreshPlan();
}

function nextTarget(state) {
  if (!isClosed(state.farm.farm.boundary)) return { target: 'farm', drawing: true };
  const open = state.farm.sections.find((s) => !isClosed(s.polygon));
  return open ? { target: open.id, drawing: true } : { target: 'farm', drawing: false };
}

function hint(draw, pts) {
  const who = draw.target === 'farm' ? 'Contour de la ferme' : `Section ${draw.target}`;
  if (draw.drawing) {
    if (pts.length < 3)
      return `${who} · cliquez sur la carte pour poser les coins (${pts.length}/3 minimum)`;
    return `${who} · double-cliquez ou cliquez sur le premier coin pour fermer`;
  }
  if (!pts.length) return `${who} · appuyez sur « Dessiner » puis cliquez sur la carte`;
  return `${who} · glissez les coins blancs pour ajuster · clic droit sur un coin pour l’enlever`;
}

export default {
  title: 'Tracer la ferme',

  onEnter(app) {
    app.update((s) => {
      s.ui.draw = nextTarget(s);
    });
  },

  render(state) {
    const sections = state.farm.sections;
    const draw = state.ui.draw;
    const boundary = state.farm.farm.boundary ?? [];
    const pts = pointsOf(state, draw.target);
    const total = roundHa(sections.reduce((a, s) => a + s.areaHa, 0));
    const farmDone = isClosed(boundary);
    const farmOn = draw.target === 'farm';
    const canFinish = draw.drawing && pts.length >= 3;
    const traced = sections.filter((s) => isClosed(s.polygon)).length;

    return html`${onboardingHeader(3)}
      <div class="split" id="main">
        <aside class="split__side stack-md">
          <div class="stack-xs">
            <h1 class="h1">Tracez votre ferme</h1>
            <p class="muted">
              Dessinez d’abord le contour de la ferme, puis chaque section. Chaque section aura sa
              propre rotation.
            </p>
          </div>

          <div class="stack-xs">
            <span class="eyebrow">1 · Contour</span>
            <div class="list-row ${farmOn ? 'is-selected' : ''}">
              <button
                type="button"
                class="list-row__main"
                data-action="draw-target"
                data-id="farm"
                aria-pressed="${String(farmOn)}"
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
          </div>

          <div class="stack-xs">
            <div class="row-between">
              <span class="eyebrow">2 · Sections</span
              ><strong>${traced}/${sections.length} tracées · ${total} ha</strong>
            </div>
            ${sections.map((s) => {
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
                      >${done ? `${s.areaHa} ha` : 'À tracer'}${s.note ? ` · ${s.note}` : ''}</span
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
          </div>

          <div class="stack-xs">
            <span class="eyebrow">Outils · ${farmOn ? 'contour' : `section ${draw.target}`}</span>
            <div class="tool-grid">
              <button
                type="button"
                class="tool ${draw.drawing ? 'is-on' : ''}"
                data-action="draw-start"
                aria-pressed="${String(draw.drawing)}"
              >
                ${icon(ICONS.draw, { size: 20 })}${isClosed(pts) && !draw.drawing ? 'Redessiner' : 'Dessiner'}
              </button>
              <button
                type="button"
                class="tool"
                data-action="draw-undo"
                ${pts.length ? '' : 'disabled'}
              >
                ${icon(ICONS.undo, { size: 20 })}Annuler un coin
              </button>
              <button
                type="button"
                class="tool"
                data-action="draw-clear"
                ${pts.length ? '' : 'disabled'}
              >
                ${icon(ICONS.trash, { size: 20 })}Effacer
              </button>
            </div>
            ${
              canFinish
                ? html`<button type="button" class="btn btn--primary" data-action="draw-finish">
                    Fermer le tracé (${plural(pts.length, 'coin', 'coins')}) →
                  </button>`
                : ''
            }
          </div>

          <div class="card card--tint small">
            Astuce : une section = une partie de la ferme qui a la même culture la même année. La
            superficie est calculée à partir de votre tracé.
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
      const b = bounds([
        s.farm.farm.boundary ?? [],
        ...s.farm.sections.map((x) => x.polygon ?? []),
      ]);
      if (b) map.fitBounds(b, { padding: [60, 60] });
      editor = createPolygonEditor(map, {
        onChange: (id, pts) => setPoints(app, id, pts),
        onSelect: (id) =>
          app.update((d) => {
            d.ui.draw = { target: id, drawing: false };
            if (id !== 'farm') d.ui.selectedSection = id;
          }),
        onFinish: (id, pts) => {
          setPoints(app, id, pts);
          app.update((d) => {
            d.ui.draw.drawing = false;
          });
        },
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
        s.ui.draw = { target: id, drawing: !isClosed(pointsOf(s, id)) };
        if (id !== 'farm') s.ui.selectedSection = id;
      }),
    'draw-start': (app) => {
      const { target, drawing } = app.state.ui.draw;
      if (drawing) return;
      if (isClosed(pointsOf(app.state, target))) setPoints(app, target, []);
      app.update((s) => {
        s.ui.draw.drawing = true;
      });
    },
    'draw-undo': (app) => {
      const { target } = app.state.ui.draw;
      const pts = pointsOf(app.state, target);
      setPoints(app, target, pts.slice(0, -1));
      if (pts.length - 1 < 3) {
        app.update((s) => {
          s.ui.draw.drawing = true;
        });
      }
    },
    'draw-clear': (app) => {
      const { target } = app.state.ui.draw;
      setPoints(app, target, []);
      app.update((s) => {
        s.ui.draw.drawing = true;
      });
    },
    'draw-finish': (app) =>
      app.update((s) => {
        if (isClosed(pointsOf(s, s.ui.draw.target))) s.ui.draw.drawing = false;
      }),
    'add-section': (app) => {
      const used = new Set(app.state.farm.sections.map((s) => s.id));
      const id = [...LETTERS].find((l) => !used.has(l));
      if (!id) return;
      app.updateFarm((farm) => {
        farm.sections.push({
          id,
          areaHa: 5,
          offset: 0,
          currentCrop: null,
          polygon: [],
          rotation: structuredClone(DEFAULT_ROTATION),
        });
        // Same rotation as the others? Shift it so the farm grows several crops each year.
        autoStagger(farm.farm, farm.sections);
      });
      app.update((s) => {
        s.ui.selectedSection = id;
        s.ui.draw = { target: id, drawing: true };
      });
    },
    'remove-section': (app, el) => {
      app.updateFarm((farm, s) => {
        farm.sections = farm.sections.filter((x) => x.id !== el.dataset.id);
        autoStagger(farm.farm, farm.sections);
        if (s.ui.selectedSection === el.dataset.id) s.ui.selectedSection = farm.sections[0].id;
        if (s.ui.draw.target === el.dataset.id) s.ui.draw = { target: 'farm', drawing: false };
      });
    },
  },
};
