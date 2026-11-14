/** Revenue per hectare over the horizon: rotation (line + range) vs a baseline (dashed). */
import { html, fmt } from '../lib/html.js';

export function revenueChart(series, baseline, baselineLabel) {
  if (!series?.length) return '';
  const W = 560;
  const H = 220;
  const pad = { l: 56, r: 12, t: 16, b: 30 };
  const all = [...series.flatMap((p) => [p.low, p.high]), ...baseline.map((p) => p.value)];
  const min = Math.floor(Math.min(...all) / 100) * 100;
  const max = Math.ceil(Math.max(...all) / 100) * 100;
  const x = (i) => pad.l + (i / Math.max(1, series.length - 1)) * (W - pad.l - pad.r);
  const y = (v) => pad.t + (1 - (v - min) / (max - min || 1)) * (H - pad.t - pad.b);
  const line = (pts, key) =>
    pts.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(p[key]).toFixed(1)}`).join(' ');
  const band = `${series.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(p.high).toFixed(1)}`).join(' ')} ${series
    .slice()
    .reverse()
    .map((p, j) => `L${x(series.length - 1 - j).toFixed(1)} ${y(p.low).toFixed(1)}`)
    .join(' ')} Z`;
  const ticks = [min, (min + max) / 2, max];
  return html`<svg
    class="chart"
    viewBox="0 0 ${W} ${H}"
    role="img"
    aria-label="Revenu par hectare et par an de la rotation, comparé à ${baselineLabel}"
  >
    ${ticks.map((t) => html`<line x1="${pad.l}" x2="${W - pad.r}" y1="${y(t)}" y2="${y(t)}" class="chart__grid"></line><text x="${pad.l - 8}" y="${y(t) + 4}" text-anchor="end" class="chart__label">${fmt(t)} $</text>`)}
    <text x="${pad.l}" y="${H - 8}" class="chart__label">${series[0].year}</text>
    <text x="${W - pad.r}" y="${H - 8}" text-anchor="end" class="chart__label">
      ${series[series.length - 1].year}
    </text>
    <path d="${band}" fill="#0072B2" fill-opacity=".12"></path>
    <path
      d="${line(series, 'value')}"
      fill="none"
      stroke="#0072B2"
      stroke-width="3"
      stroke-linejoin="round"
    ></path>
    <path
      d="${line(baseline, 'value')}"
      fill="none"
      stroke="#D55E00"
      stroke-width="2.5"
      stroke-dasharray="7 5"
      stroke-linejoin="round"
    ></path>
  </svg>`;
}
