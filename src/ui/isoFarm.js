/**
 * Isometric view of the farm: one diamond per section, textured with the crop
 * of the selected year. The selected section is raised. Works for any number
 * of sections (laid out on a square grid).
 */
import { html } from '../lib/html.js';
import { CROPS } from '../data/crops.js';

export function isoFarm({ sections, cropOf, selectedId }) {
  const n = Math.max(1, sections.length);
  const cols = Math.ceil(Math.sqrt(n));
  const rows = Math.ceil(n / cols);
  const hw = cols > 2 ? 300 / cols : 110;
  const hh = hw / 2;
  const lift = 26;
  const top = 24 + lift;
  const ox = rows * hw + 20;
  const W = (rows + cols) * hw + 40;
  const H = top + (rows + cols) * hh + 24;

  const tiles = sections
    .map((s, i) => {
      const col = i % cols;
      const row = Math.floor(i / cols);
      return { s, col, row, cx: ox + (col - row) * hw, cy: top + hh + (col + row) * hh };
    })
    .sort((a, b) => a.col + a.row - (b.col + b.row) || a.col - b.col);

  const plate = [
    [ox, top],
    [ox + cols * hw, top + cols * hh],
    [ox + (cols - rows) * hw, top + (cols + rows) * hh],
    [ox - rows * hw, top + rows * hh],
  ]
    .map((p) => p.join(','))
    .join(' ');

  const k = 0.95;
  const w = hw * k;
  const h = hh * k;
  return html`<svg
    class="iso-farm"
    viewBox="0 0 ${W} ${H}"
    role="img"
    aria-label="Vue de la ferme : chaque losange est une section, colorée selon la culture de l’année"
  >
    <polygon points="${plate}" fill="#CBD3C2" opacity=".55"></polygon>
    ${tiles.map(({ s, cx, cy }) => {
      const crop = cropOf(s.id);
      const up = s.id === selectedId ? lift : 0;
      const t = cy - up;
      const topFace = `${cx},${t - h} ${cx + w},${t} ${cx},${t + h} ${cx - w},${t}`;
      const left = `${cx - w},${t} ${cx},${t + h} ${cx},${cy + h} ${cx - w},${cy}`;
      const right = `${cx},${t + h} ${cx + w},${t} ${cx + w},${cy} ${cx},${cy + h}`;
      return html`<g class="iso-tile" data-action="select-section" data-id="${s.id}">
        ${up ? html`<polygon points="${left}" fill="#6B4F35"></polygon><polygon points="${right}" fill="#54402B"></polygon>` : ''}
        <polygon
          points="${topFace}"
          fill="url(#pat-${crop || 'sol'})"
          stroke="${up ? '#18211B' : '#FFFFFF'}"
          stroke-width="${up ? 3 : 2}"
        ></polygon>
        <rect
          x="${cx - 40}"
          y="${t - 24}"
          width="80"
          height="48"
          rx="10"
          fill="#FFFFFF"
          fill-opacity=".92"
        ></rect>
        <text x="${cx}" y="${t - 2}" text-anchor="middle" class="iso-tile__id">${s.id}</text>
        <text x="${cx}" y="${t + 17}" text-anchor="middle" class="iso-tile__crop"
          >${CROPS[crop]?.name ?? '—'}</text
        >
      </g>`;
    })}
  </svg>`;
}
