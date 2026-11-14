/**
 * Top view of the farm drawn from the real polygons (farm outline + sections),
 * each section textured with its crop of the year. Returns null when no
 * section has been traced yet, so callers can show a placeholder instead.
 */
import { html } from '../lib/html.js';
import { centroidXY, fitToBox, isClosed } from '../../application/rules/geo.js';
import { textureFill } from './textures.js';

const toPoints = (pts) => pts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');

export function farmPlan({
  sections,
  boundary = null,
  cropOf,
  selectedId = null,
  width = 320,
  height = 300,
  label,
}) {
  const drawn = sections.filter((s) => isClosed(s.polygon));
  if (!drawn.length) return null;

  const hasBoundary = isClosed(boundary);
  const polys = [hasBoundary ? boundary : [], ...drawn.map((s) => s.polygon)];
  const { shapes } = fitToBox(polys, { width, height, padding: 22 });
  const [outline, ...tiles] = shapes;

  return html`<svg
    viewBox="0 0 ${width} ${height}"
    role="img"
    aria-label="${label ?? 'Plan de la ferme'}"
  >
    <rect width="${width}" height="${height}" fill="#4A6B3C"></rect>
    ${
      hasBoundary
        ? html`<polygon
            points="${toPoints(outline)}"
            fill="#CBD3C2"
            fill-opacity=".35"
            stroke="#FFD27A"
            stroke-width="3"
            stroke-dasharray="10 6"
            stroke-linejoin="round"
          ></polygon>`
        : ''
    }
    ${drawn.map((s, i) => {
      const on = s.id === selectedId;
      const crop = cropOf(s.id);
      const c = centroidXY(tiles[i]);
      return html`<g class="map-section" data-action="select-section" data-id="${s.id}">
        <polygon
          points="${toPoints(tiles[i])}"
          fill="${textureFill(crop)}"
          stroke="#FFFFFF"
          stroke-opacity="${on ? 1 : 0.75}"
          stroke-width="${on ? 4 : 1.5}"
          stroke-linejoin="round"
        ></polygon>
        ${
          on
            ? html`<rect
                  x="${c.x - 24}"
                  y="${c.y - 24}"
                  width="48"
                  height="48"
                  rx="12"
                  fill="#FFFFFF"
                  fill-opacity=".92"
                ></rect>
                <text x="${c.x}" y="${c.y + 11}" text-anchor="middle" class="map-section__id"
                  >${s.id}</text
                >`
            : html`<text
                x="${c.x}"
                y="${c.y + 6}"
                text-anchor="middle"
                class="map-section__id map-section__id--light"
                >${s.id}</text
              >`
        }
      </g>`;
    })}
  </svg>`;
}
