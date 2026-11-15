/**
 * Pie chart (camembert) for the farm mix: shows the share of each crop by area.
 * Pure SVG, no dependencies beyond the html helper.
 */
import { html } from '../lib/html.js';
import { colorOf, nameOf } from '../../data/reference/crops.js';

const TAU = Math.PI * 2;
const R = 90;
const CX = 110;
const CY = 110;
const SIZE = 220;

function polarToXY(angle, radius = R) {
  return [
    CX + radius * Math.sin(angle),
    CY - radius * Math.cos(angle),
  ];
}

/**
 * Renders a pie chart of the crop mix.
 * @param {Object<string, number>} area  cropId → hectares
 * @param {number} year
 */
export function pieChart(area, year) {
  const entries = Object.entries(area);
  if (!entries.length) {
    return html`<div class="pie-empty">
      <span class="pie-empty__text">Pas encore de plan</span>
    </div>`;
  }

  const total = entries.reduce((s, [, ha]) => s + ha, 0);
  let angle = 0;
  const slices = [];
  const labels = [];

  entries.forEach(([cropId, ha], i) => {
    const share = ha / total;
    const startAngle = angle;
    const endAngle = angle + share * TAU;
    const midAngle = (startAngle + endAngle) / 2;
    const large = share > 0.5 ? 1 : 0;

    const [x0, y0] = polarToXY(startAngle);
    const [x1, y1] = polarToXY(endAngle);
    const color = colorOf(cropId);

    // Slightly pull slice out for a donut gap effect
    const gapPx = 1.5;
    const gx = gapPx * Math.sin(midAngle);
    const gy = -gapPx * Math.cos(midAngle);

    if (entries.length === 1) {
      slices.push(
        html`<circle cx="${CX}" cy="${CY}" r="${R}" fill="${color}" class="pie-slice">
          <title>${nameOf(cropId)} · ${ha} ha (100%)</title>
        </circle>`,
      );
    } else {
      slices.push(
        html`<path
          d="M${CX + gx} ${CY + gy}L${x0 + gx} ${y0 + gy}A${R} ${R} 0 ${large} 1 ${x1 + gx} ${y1 + gy}Z"
          fill="${color}"
          class="pie-slice"
          style="--i: ${i}"
        >
          <title>${nameOf(cropId)} · ${ha} ha (${Math.round(share * 100)}%)</title>
        </path>`,
      );
    }

    // Label at midpoint outside the pie
    if (share > 0.06) {
      const labelR = R + 22;
      const [lx, ly] = polarToXY(midAngle, labelR);
      const anchor = lx > CX ? 'start' : lx < CX - 2 ? 'end' : 'middle';
      labels.push(
        html`<text x="${lx.toFixed(1)}" y="${ly.toFixed(1)}" text-anchor="${anchor}" class="pie-label">
          ${Math.round(share * 100)}%
        </text>`,
      );
    }

    angle = endAngle;
  });

  return html`<div class="pie-container">
    <svg class="pie-svg" viewBox="0 0 ${SIZE} ${SIZE}" aria-label="Répartition des cultures en ${year}">
      ${slices}
      ${labels}
      <text x="${CX}" y="${CY - 4}" text-anchor="middle" class="pie-center-year">${year}</text>
      <text x="${CX}" y="${CY + 14}" text-anchor="middle" class="pie-center-total">${total} ha</text>
    </svg>
    <div class="pie-legend">
      ${entries.map(
        ([cropId, ha]) =>
          html`<span class="pie-legend__item">
            <span class="dot" style="background: ${colorOf(cropId)}"></span>
            <span>${nameOf(cropId)}</span>
            <strong>${ha} ha</strong>
          </span>`,
      )}
    </div>
  </div>`;
}
