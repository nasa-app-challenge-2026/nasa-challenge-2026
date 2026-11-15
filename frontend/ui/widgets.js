/** Small reusable pieces of UI (the "base commune"). All return safe HTML. */
import { html } from '../lib/html.js';
import { colorOf, nameOf } from '../../data/reference/crops.js';

/**
 * The Field Shift logo (leaf + name), cut from the team's logo.png into
 * frontend/public/: white lettering for dark backgrounds, dark lettering for light ones.
 */
const LOGO_RATIO = 762 / 144;
export const logo = ({ height = 34, onDark = false } = {}) =>
  html`<img
    class="brand-logo"
    src="${onDark ? 'logo-texte-blanc.png' : 'logo-texte-sombre.png'}"
    alt="Field Shift"
    width="${Math.round(height * LOGO_RATIO)}"
    height="${height}"
  />`;

export function demoBadge(show) {
  return show ? html`<span class="pill pill--warn">Données d’exemple</span>` : '';
}

export function cropChip(id, { current = false, faded = false, note = '' } = {}) {
  if (!id) return html`<span class="crop-chip crop-chip--empty">—</span>`;
  const cls = ['crop-chip', current && 'is-current', faded && 'is-faded'].filter(Boolean).join(' ');
  return html`<span class="${cls}" style="background: ${colorOf(id)}">${nameOf(id)}${note}</span>`;
}

/** Score bar with optional reference marker and delta (colour + arrow, never colour alone). */
export function scoreBar(label, value, { reference, delta, info } = {}) {
  const bad = delta !== undefined && delta < 0;
  const deltaTxt =
    delta === undefined || delta === 0 ? '' : delta > 0 ? `↑ +${delta}` : `↓ ${delta}`;
  return html`<div class="score">
    <div class="score__row">
      <span class="score__label">${label}${info || ''}</span
      ><span
        ><strong>${value ?? '…'}</strong>
        <span class="${bad ? 'delta delta--bad' : 'delta delta--good'}">${deltaTxt}</span></span
      >
    </div>
    <div class="score__track">
      <div class="score__fill ${bad ? 'is-bad' : ''}" style="width: ${value ?? 0}%"></div>
      ${reference !== undefined ? html`<div class="score__ref" style="left: calc(${reference}% - 1px)"></div>` : ''}
    </div>
  </div>`;
}

export function alertBox(kind, text, extra = '') {
  const glyph = kind === 'ok' ? '✓' : '⚠';
  return html`<div class="alert alert--${kind}">
    <span aria-hidden="true">${glyph}</span><span>${text}</span>${extra}
  </div>`;
}

export function switchButton(on, action, label, attrs = '') {
  return html`<button
    type="button"
    class="switch ${on ? 'is-on' : ''}"
    role="switch"
    aria-checked="${on ? 'true' : 'false'}"
    aria-label="${label}"
    data-action="${action}"
    ${attrs}
  >
    <span class="switch__knob"></span>
  </button>`;
}

export function sparkline(values, color = '#0072B2') {
  if (!values?.length) return '';
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const d = values
    .map(
      (v, i) =>
        `${i ? 'L' : 'M'}${((i / (values.length - 1)) * 200).toFixed(1)} ${(34 - ((v - min) / span) * 28).toFixed(1)}`,
    )
    .join(' ');
  return html`<svg class="spark" viewBox="0 0 200 40" preserveAspectRatio="none" aria-hidden="true">
    <path
      d="${d}"
      fill="none"
      stroke="${color}"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
    ></path>
  </svg>`;
}

/** Length of one loop of the loading animation (the same in components.css). */
const LOADER_LOOP_MS = 3600;

/**
 * Where the loading animations are in their loop, as a CSS delay. The page is drawn again at
 * every change of state: without it, the animation would start over each time.
 */
const loopPhase = () => `--t: -${Date.now() % LOADER_LOOP_MS}ms`;

/**
 * The waiting scene: a little field where four sprouts come up one after the other under a
 * turning sun and a passing cloud. `extra` goes under the text (a « Demander à Rota » button).
 */
export function loading(text = 'Calcul en cours', extra = '') {
  const sprout = (x, i) =>
    // The place of the sprout is on the outer group: the animation transforms the inner one.
    html`<g transform="translate(${x} 52)">
      <g class="loader__sprout" style="--i: ${i}">
        <path d="M0 0V-13" stroke="#3F7A45" stroke-width="2.4" stroke-linecap="round" />
        <path d="M0 -8C-7 -8 -9 -14 -9 -17C-3 -17 0 -13 0 -8Z" fill="#7FB04E" />
        <path d="M0 -11C6 -11 9 -16 9 -20C3 -20 0 -16 0 -11Z" fill="#93C25F" />
      </g>
    </g>`;
  return html`<div class="loader" role="status" style="${loopPhase()}">
    <svg class="loader__scene" viewBox="0 0 120 70" width="180" height="105" aria-hidden="true">
      <g class="loader__sun">
        <circle cx="96" cy="17" r="7" fill="#F2C14E" />
        <path
          d="M96 4v4M96 26v4M83 17h4M105 17h4M86.8 7.8l2.8 2.8M102.4 23.4l2.8 2.8M86.8 26.2l2.8-2.8M102.4 10.6l2.8-2.8"
          stroke="#F2C14E"
          stroke-width="2"
          stroke-linecap="round"
        />
      </g>
      <g class="loader__cloud" fill="#FFFFFF" stroke="#C9D0C2" stroke-width="1">
        <path d="M14 24h20a6 6 0 0 0 .6-12A9 9 0 0 0 17.5 13 5.5 5.5 0 0 0 14 24Z" />
      </g>
      <rect x="4" y="52" width="112" height="14" rx="7" fill="#8A6845" />
      <path d="M12 59h96" stroke="#6C4F33" stroke-width="1.6" stroke-dasharray="3 5" />
      ${[22, 47, 72, 97].map(sprout)}
    </svg>
    <span class="loader__text"
      >${text}<span class="loader__dots" aria-hidden="true"><i></i><i></i><i></i></span
    ></span>
    ${extra}
  </div>`;
}

/** Three small bouncing dots: something is being updated, the page stays usable. */
export function busyDots(label) {
  return html`<span class="busy" role="status" style="${loopPhase()}"
    >${label}<span class="loader__dots" aria-hidden="true"><i></i><i></i><i></i></span
  ></span>`;
}

export function errorBox(message, retryAction = 'retry-plan') {
  return html`<div class="alert alert--bad" role="alert">
    <span aria-hidden="true">⚠</span><span>${message}</span
    ><button type="button" class="btn btn--sm btn--secondary" data-action="${retryAction}">
      Réessayer
    </button>
  </div>`;
}
