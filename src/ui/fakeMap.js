/**
 * Placeholder "satellite" map. Replace with a real map (Leaflet + an imagery
 * layer) for the hackathon: see docs/ROADMAP.md. Kept as plain SVG so the
 * screens work offline and in tests.
 */
import { html } from '../lib/html.js';

export function fakeSatellite({ width = 1440, height = 800 } = {}) {
  return html`<svg
    class="fake-map"
    viewBox="0 0 ${width} ${height}"
    preserveAspectRatio="xMidYMid slice"
    aria-hidden="true"
  >
    <rect width="${width}" height="${height}" fill="#4A6B3C"></rect>
    <g stroke="#2F4527" stroke-width="2">
      <rect x="40" y="40" width="300" height="200" fill="url(#pat-soya)"></rect>
      <rect x="360" y="40" width="240" height="200" fill="url(#pat-ble)"></rect>
      <rect x="620" y="40" width="330" height="200" fill="url(#pat-mais)"></rect>
      <rect x="970" y="40" width="200" height="200" fill="url(#pat-orge)"></rect>
      <rect x="1190" y="40" width="230" height="200" fill="url(#pat-soya)"></rect>
      <rect x="40" y="290" width="220" height="230" fill="url(#pat-orge)"></rect>
      <rect x="280" y="290" width="300" height="230" fill="url(#pat-mais)"></rect>
      <rect x="600" y="290" width="380" height="230" fill="url(#pat-ble)"></rect>
      <rect x="1000" y="290" width="420" height="230" fill="url(#pat-sol)"></rect>
      <rect x="40" y="570" width="360" height="200" fill="url(#pat-ble)"></rect>
      <rect x="420" y="570" width="260" height="200" fill="url(#pat-luzerne)"></rect>
      <rect x="700" y="570" width="300" height="200" fill="url(#pat-soya)"></rect>
      <rect x="1020" y="570" width="400" height="200" fill="url(#pat-mais)"></rect>
    </g>
    <path
      d="M0 262H${width}M0 545H${width}M990 0V${height}"
      stroke="#D8D2C2"
      stroke-width="10"
    ></path>
    <path
      d="M0 262H${width}M0 545H${width}M990 0V${height}"
      stroke="#BDB6A4"
      stroke-width="2"
      stroke-dasharray="16 14"
    ></path>
    <path
      d="M-20 700C200 640 300 760 520 720S820 600 1000 650 1300 760 1460 700"
      fill="none"
      stroke="#6E9DB8"
      stroke-width="14"
      stroke-linecap="round"
    ></path>
  </svg>`;
}
