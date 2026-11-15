/**
 * A pie chart (camembert) in plain SVG: one slice per value, clockwise from the top.
 *
 *   pieChart([{ label: 'Maïs', value: 12, color: '#F2C14E' }, …], { label: 'Cultures en 2027' })
 */
import { html } from '../lib/html.js';

const TURN = Math.PI * 2;
/** The pie is drawn in a 100 × 100 box. */
const CENTER = 50;
const RADIUS = 48;
const HALF_TURN = 0.5;

const round = (n) => Math.round(n * 100) / 100;

/** Point of the edge of the pie at `turn` (0 = top, clockwise, 1 = a full turn). */
const edge = (turn) => [
  round(CENTER + RADIUS * Math.sin(turn * TURN)),
  round(CENTER - RADIUS * Math.cos(turn * TURN)),
];

/** The share of each slice, as [{ …slice, from, to }] in turns. Slices of 0 are left out. */
export function pieShares(slices) {
  const shown = slices.filter((slice) => slice.value > 0);
  const total = shown.reduce((sum, slice) => sum + slice.value, 0);
  let from = 0;
  return shown.map((slice) => {
    const to = from + slice.value / total;
    const share = { ...slice, from, to };
    from = to;
    return share;
  });
}

function slicePath({ from, to }) {
  const [x0, y0] = edge(from);
  const [x1, y1] = edge(to);
  const large = to - from > HALF_TURN ? 1 : 0;
  return `M${CENTER} ${CENTER}L${x0} ${y0}A${RADIUS} ${RADIUS} 0 ${large} 1 ${x1} ${y1}Z`;
}

export function pieChart(slices, { label, size = 96 }) {
  const shares = pieShares(slices);
  const title = (s) => html`<title>${s.label} · ${Math.round((s.to - s.from) * 100)} %</title>`;
  return html`<svg
    class="pie"
    viewBox="0 0 100 100"
    width="${size}"
    height="${size}"
    role="img"
    aria-label="${label} : ${shares.map((s) => s.label).join(', ')}"
  >
    ${
      shares.length === 1
        ? html`<circle cx="${CENTER}" cy="${CENTER}" r="${RADIUS}" fill="${shares[0].color}">
            ${title(shares[0])}
          </circle>`
        : shares.map(
            (s) =>
              html`<path d="${slicePath(s)}" fill="${s.color}" class="pie__slice"
                >${title(s)}</path
              >`,
          )
    }
  </svg>`;
}
