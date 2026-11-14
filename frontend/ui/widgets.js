/** Small reusable pieces of UI (the "base commune"). All return safe HTML. */
import { html } from '../lib/html.js';
import { CROPS, ROLES } from '../../data/reference/crops.js';
import { icon, ICONS } from './icons.js';

export const logo = (size = 36) =>
  html`<span class="brand-mark" style="width: ${size}px; height: ${size}px"
    >${icon(ICONS.sprout, { size: size * 0.56, color: '#FFFFFF' })}</span
  >`;

export function infoButton(action, label, attrs = '') {
  return html`<button
    type="button"
    class="info-btn"
    data-action="${action}"
    ${attrs}
    aria-label="Expliquer ${label}"
  >
    i
  </button>`;
}

export function demoBadge(show) {
  return show ? html`<span class="pill pill--warn">Données d’exemple</span>` : '';
}

export function cropChip(cropId, { current = false, faded = false } = {}) {
  const c = CROPS[cropId];
  if (!c) return html`<span class="crop-chip crop-chip--empty">—</span>`;
  const cls = ['crop-chip', current && 'is-current', faded && 'is-faded'].filter(Boolean).join(' ');
  return html`<span class="${cls}" style="background: ${c.color}">${c.name}</span>`;
}

export function roleTag(roleId, { action, active } = {}) {
  const r = ROLES[roleId];
  const inner = html`${icon(r.icon, { size: 12, width: 2.4 })}${r.label}`;
  if (!action)
    return html`<span class="role-tag" style="background: ${r.bg}; color: ${r.fg}">${inner}</span>`;
  return html`<button
    type="button"
    class="role-tag role-tag--btn ${active ? 'is-active' : ''}"
    data-action="${action}"
    data-role="${roleId}"
  >
    ${inner}
  </button>`;
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

export function switchButton(on, action, label) {
  return html`<button
    type="button"
    class="switch ${on ? 'is-on' : ''}"
    role="switch"
    aria-checked="${on ? 'true' : 'false'}"
    aria-label="${label}"
    data-action="${action}"
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

export function loading(text = 'Calcul en cours…') {
  return html`<div class="loading" role="status"><span class="loading__dot"></span>${text}</div>`;
}

export function errorBox(message, retryAction = 'retry-plan') {
  return html`<div class="alert alert--bad" role="alert">
    <span aria-hidden="true">⚠</span><span>${message}</span
    ><button type="button" class="btn btn--sm btn--secondary" data-action="${retryAction}">
      Réessayer
    </button>
  </div>`;
}
