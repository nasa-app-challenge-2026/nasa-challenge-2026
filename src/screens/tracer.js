/**
 * 4 · Tracer la ferme et ses sections. Owner: Loïc.
 * The map is a placeholder: sections are laid out on a grid. Drawing real
 * polygons (Leaflet) is in docs/ROADMAP.md; the data model already has
 * `section.polygon`.
 */
import { html, plural } from '../lib/html.js';
import { onboardingHeader } from '../ui/layout.js';
import { icon, ICONS } from '../ui/icons.js';
import { fakeSatellite } from '../ui/fakeMap.js';

const LETTERS = 'ABCDEFGHIJ';
const DEFAULT_ROTATION = [
  { crop: 'mais', years: 1, cover: null },
  { crop: 'soya', years: 1, cover: null },
  { crop: 'ble', years: 1, cover: null },
];

export default {
  title: 'Tracer la ferme',
  render(state) {
    const sections = state.farm.sections;
    const sel = state.ui.selectedSection;
    const total = sections.reduce((a, s) => a + s.areaHa, 0);
    const cols = sections.length > 4 ? 3 : 2;
    const rows = Math.ceil(sections.length / cols);
    const W = 520;
    const H = 510;
    return html`${onboardingHeader(3)}
      <div class="split" id="main">
        <aside class="split__side stack-md">
          <div class="stack-xs">
            <h1 class="h1">Tracez votre ferme</h1>
            <p class="muted">
              Dessinez le contour, puis découpez-le en sections. Chaque section aura sa propre
              rotation.
            </p>
          </div>
          <div class="tool-grid">
            <button type="button" class="tool is-on" title="À brancher sur la vraie carte">
              ${icon(ICONS.draw, { size: 20 })}Délimiter
            </button>
            <button type="button" class="tool" title="À brancher sur la vraie carte">
              ${icon(ICONS.undo, { size: 20 })}Annuler
            </button>
            <button
              type="button"
              class="tool"
              data-action="add-section"
              ${sections.length >= LETTERS.length ? 'disabled' : ''}
            >
              ${icon(ICONS.plus, { size: 20 })}Nouvelle section
            </button>
          </div>
          <div class="stack-xs">
            <div class="row-between">
              <span class="eyebrow">Sections</span><strong>${total} ha au total</strong>
            </div>
            ${sections.map(
              (s) =>
                html`<div class="list-row ${s.id === sel ? 'is-selected' : ''}">
                  <button
                    type="button"
                    class="list-row__main"
                    data-action="select-section"
                    data-id="${s.id}"
                  >
                    <span class="section-badge ${s.id === sel ? 'is-blue' : ''}">${s.id}</span
                    ><span class="stack-0"
                      ><strong>Section ${s.id}</strong
                      ><span class="muted small"
                        >${s.areaHa} ha${s.note ? ` · ${s.note}` : ''}</span
                      ></span
                    >
                  </button>
                  ${sections.length > 1 ? html`<button type="button" class="icon-btn" data-action="remove-section" data-id="${s.id}" aria-label="Supprimer la section ${s.id}">${icon(ICONS.trash, { size: 18 })}</button>` : ''}
                </div>`,
            )}
          </div>
          <div class="card card--tint small">
            Astuce : une section = une partie de la ferme qui a la même culture la même année.
          </div>
        </aside>
        <div class="split__main map-screen map-screen--inset">
          ${fakeSatellite({ width: 1040, height: 780 })}
          <svg
            class="sections-overlay"
            viewBox="0 0 1040 780"
            preserveAspectRatio="xMidYMid slice"
            role="img"
            aria-label="${plural(sections.length, 'section', 'sections')} sur la carte"
          >
            ${sections.map((s, i) => {
              const c = i % cols;
              const r = Math.floor(i / cols);
              const w = W / cols;
              const h = H / rows;
              const x = 260 + c * w;
              const y = 130 + r * h;
              const on = s.id === sel;
              return html`<g data-action="select-section" data-id="${s.id}" class="map-section">
                <rect
                  x="${x}"
                  y="${y}"
                  width="${w}"
                  height="${h}"
                  fill="#0072B2"
                  fill-opacity="${on ? 0.32 : 0.05}"
                  stroke="#FFFFFF"
                  stroke-width="${on ? 6 : 2}"
                ></rect>
                <rect
                  x="${x + w / 2 - 38}"
                  y="${y + h / 2 - 36}"
                  width="76"
                  height="68"
                  rx="12"
                  fill="#FFFFFF"
                  fill-opacity=".9"
                ></rect>
                <text
                  x="${x + w / 2}"
                  y="${y + h / 2 - 2}"
                  text-anchor="middle"
                  class="map-section__id"
                  >${s.id}</text
                >
                <text
                  x="${x + w / 2}"
                  y="${y + h / 2 + 22}"
                  text-anchor="middle"
                  class="map-section__ha"
                  >${s.areaHa} ha</text
                >
              </g>`;
            })}
            <rect
              x="260"
              y="130"
              width="${W}"
              height="${H}"
              fill="none"
              stroke="#FFD27A"
              stroke-width="4"
              stroke-dasharray="14 8"
            ></rect>
          </svg>
          <div class="map-hint">
            Contour de la ferme · cliquez sur la carte pour ajouter des coins
          </div>
          <div class="map-actions">
            <a class="btn btn--secondary" href="#/localisation">Retour</a>
            <a class="btn btn--primary" href="#/priorites"
              >Valider ${plural(sections.length, 'section', 'sections')} →</a
            >
          </div>
        </div>
      </div>`;
  },
  actions: {
    'add-section': (app) => {
      const used = new Set(app.state.farm.sections.map((s) => s.id));
      const id = [...LETTERS].find((l) => !used.has(l));
      if (!id) return;
      app.updateFarm((farm) => {
        farm.sections.push({
          id,
          areaHa: 5,
          offset: 0,
          rotation: structuredClone(DEFAULT_ROTATION),
        });
      });
      app.update((s) => {
        s.ui.selectedSection = id;
      });
    },
    'remove-section': (app, el) => {
      app.updateFarm((farm, s) => {
        farm.sections = farm.sections.filter((x) => x.id !== el.dataset.id);
        if (s.ui.selectedSection === el.dataset.id) s.ui.selectedSection = farm.sections[0].id;
      });
    },
  },
};
