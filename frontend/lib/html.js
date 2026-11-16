/**
 * Tiny, safe HTML templating.
 *
 *   html`<p>${userText}</p>`      → userText is escaped
 *   html`<ul>${items.map(i => html`<li>${i}</li>`)}</ul>`   → nested templates are kept
 *   raw('<b>trusted</b>')          → inserted as is (only for trusted strings)
 */
import { localizeHtml } from './localizeHtml.js';
import { formatNumber, pluralText } from '../../data/i18n/index.js';

class SafeHtml {
  constructor(value) {
    this.value = value;
  }
  toString() {
    return this.value;
  }
}

const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

export function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => ESC[c]);
}

function toHtml(value) {
  if (value === null || value === undefined || value === false) return '';
  if (value instanceof SafeHtml) return value.value;
  if (Array.isArray(value)) return value.map(toHtml).join('');
  return escapeHtml(value);
}

export function html(strings, ...values) {
  let out = '';
  strings.forEach((s, i) => {
    out += s;
    if (i < values.length) out += toHtml(values[i]);
  });
  return new SafeHtml(localizeHtml(out));
}

export const raw = (value) => new SafeHtml(String(value));
/** Preserve user names, addresses and free-form messages exactly as entered. */
export const verbatim = (value) =>
  new SafeHtml(`<!--i18n:off-->${escapeHtml(value ?? '')}<!--i18n:on-->`);

/** Join CSS declarations, skipping falsy ones: style('a: 1', cond && 'b: 2'). */
export const style = (...parts) => parts.filter(Boolean).join('; ');

/** Format a number with French spacing: 1 015. */
export const fmt = (n) => formatNumber(Math.round(n));
export const plural = pluralText;
