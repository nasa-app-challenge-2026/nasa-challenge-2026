/**
 * Isometric view of the farm, textured with the crop of the selected year.
 * The selected section is raised.
 *
 * When sections have been traced on the map, their real polygons (and the
 * farm outline as the ground plate) are projected in isometric. Sections not
 * traced yet fall back to a square grid of diamonds.
 */
import { html } from '../lib/html.js';
import { CROPS } from '../data/crops.js';
import { centroidXY, fitToBox, isClosed } from '../lib/geo.js';

const LIFT = 26;
const COS30 = Math.cos(Math.PI / 6);

export function isoFarm({ sections, cropOf, selectedId, boundary = null }) {
  const drawn = sections.filter((s) => isClosed(s.polygon));
  return drawn.length
    ? polygonFarm({ sections, drawn, cropOf, selectedId, boundary })
    : gridFarm({ sections, cropOf, selectedId });
}

const pts = (list) => list.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');

/** One section drawn as a raised prism: base, side walls, then the top face. */
function prism({ s, top, up, cropId, selected, labelScale = 1 }) {
  const lifted = top.map((p) => ({ x: p.x, y: p.y - up }));
  const c = centroidXY(lifted);
  const walls = [];
  if (up) {
    for (let i = 0; i < top.length; i++) {
      const a = lifted[i];
      const b = lifted[(i + 1) % top.length];
      walls.push(
        html`<polygon
          points="${pts([a, b, { x: b.x, y: b.y + up }, { x: a.x, y: a.y + up }])}"
          fill="${b.x > a.x ? '#54402B' : '#6B4F35'}"
        ></polygon>`,
      );
    }
  }
  return html`<g class="iso-tile" data-action="select-section" data-id="${s.id}">
    ${up ? html`<polygon points="${pts(top)}" fill="#3E2E1F"></polygon>` : ''}${walls}
    <polygon
      points="${pts(lifted)}"
      fill="url(#pat-${cropId || 'sol'})"
      stroke="${selected ? '#18211B' : '#FFFFFF'}"
      stroke-width="${selected ? 3 : 2}"
      stroke-linejoin="round"
    ></polygon>
    <g transform="translate(${c.x.toFixed(1)} ${c.y.toFixed(1)}) scale(${labelScale})">
      <rect x="-40" y="-24" width="80" height="48" rx="10" fill="#FFFFFF" fill-opacity=".92"></rect>
      <text x="0" y="-2" text-anchor="middle" class="iso-tile__id">${s.id}</text>
      <text x="0" y="17" text-anchor="middle" class="iso-tile__crop"
        >${CROPS[cropId]?.name ?? '—'}</text
      >
    </g>
  </g>`;
}

function polygonFarm({ sections, drawn, cropOf, selectedId, boundary }) {
  const S = 420;
  const hasBoundary = isClosed(boundary);
  const polys = [hasBoundary ? boundary : [], ...drawn.map((s) => s.polygon)];
  const { shapes } = fitToBox(polys, { width: S, height: S, padding: 6 });

  const W = 2 * S * COS30 + 40;
  const top = 20 + LIFT;
  const iso = (p) => ({ x: W / 2 + (p.x - p.y) * COS30, y: top + (p.x + p.y) / 2 });
  const [outline, ...tiles] = shapes.map((poly) => poly.map(iso));
  const plate = hasBoundary
    ? outline
    : [
        { x: 0, y: 0 },
        { x: S, y: 0 },
        { x: S, y: S },
        { x: 0, y: S },
      ].map(iso);

  const missing = sections.filter((s) => !isClosed(s.polygon));
  const rowY = top + S + 30;
  const H = rowY + (missing.length ? 70 : 10);

  const order = drawn
    .map((s, i) => ({ s, top: tiles[i], depth: centroidXY(tiles[i]).y }))
    .sort((a, b) => a.depth - b.depth);

  return html`<svg
    class="iso-farm"
    viewBox="0 0 ${W.toFixed(0)} ${H}"
    role="img"
    aria-label="Vue de la ferme : chaque forme est une section tracée sur la carte, colorée selon la culture de l’année"
  >
    <polygon
      points="${pts(plate)}"
      fill="#CBD3C2"
      opacity=".55"
      stroke="#FFD27A"
      stroke-width="3"
      stroke-dasharray="10 6"
    ></polygon>
    ${order.map(({ s, top: face }) =>
      prism({
        s,
        top: face,
        up: s.id === selectedId ? LIFT : 0,
        cropId: cropOf(s.id),
        selected: s.id === selectedId,
        labelScale: 1.25,
      }),
    )}
    ${missing.map((s, i) => {
      const cx = 80 + i * 110;
      const cy = rowY + 28;
      const face = [
        { x: cx, y: cy - 20 },
        { x: cx + 40, y: cy },
        { x: cx, y: cy + 20 },
        { x: cx - 40, y: cy },
      ];
      return html`${prism({
          s,
          top: face,
          up: 0,
          cropId: cropOf(s.id),
          selected: s.id === selectedId,
          labelScale: 0.8,
        })}
        <text x="${cx}" y="${cy + 40}" text-anchor="middle" class="iso-tile__crop muted"
          >non tracée</text
        >`;
    })}
  </svg>`;
}

function gridFarm({ sections, cropOf, selectedId }) {
  const n = Math.max(1, sections.length);
  const cols = Math.ceil(Math.sqrt(n));
  const rows = Math.ceil(n / cols);
  const hw = cols > 2 ? 300 / cols : 110;
  const hh = hw / 2;
  const top = 24 + LIFT;
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
    { x: ox, y: top },
    { x: ox + cols * hw, y: top + cols * hh },
    { x: ox + (cols - rows) * hw, y: top + (cols + rows) * hh },
    { x: ox - rows * hw, y: top + rows * hh },
  ];

  const k = 0.95;
  const w = hw * k;
  const h = hh * k;
  return html`<svg
    class="iso-farm"
    viewBox="0 0 ${W} ${H}"
    role="img"
    aria-label="Vue de la ferme : chaque losange est une section, colorée selon la culture de l’année"
  >
    <polygon points="${pts(plate)}" fill="#CBD3C2" opacity=".55"></polygon>
    ${tiles.map(({ s, cx, cy }) =>
      prism({
        s,
        top: [
          { x: cx, y: cy - h },
          { x: cx + w, y: cy },
          { x: cx, y: cy + h },
          { x: cx - w, y: cy },
        ],
        up: s.id === selectedId ? LIFT : 0,
        cropId: cropOf(s.id),
        selected: s.id === selectedId,
      }),
    )}
  </svg>`;
}
