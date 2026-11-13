import { html } from '../lib/html.js';

/** Stroke icon from a 24×24 SVG path. Decorative by default. */
export function icon(d, { size = 20, color = 'currentColor', width = 2, label } = {}) {
  const a11y = label ? html`role="img" aria-label="${label}"` : html`aria-hidden="true"`;
  return html`<svg
    width="${size}"
    height="${size}"
    viewBox="0 0 24 24"
    fill="none"
    stroke="${color}"
    stroke-width="${width}"
    stroke-linecap="round"
    stroke-linejoin="round"
    ${a11y}
  >
    <path d="${d}"></path>
  </svg>`;
}

export const ICONS = {
  sprout: 'M12 21V11M12 11C12 7 9 4 4 4c0 5 3 7 8 7ZM12 14c0-3 2.5-6 8-6 0 4-3 6-8 6Z',
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM4 21c1.5-4 4.5-6 8-6s6.5 2 8 6',
  search: 'M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14ZM20 20l-3.5-3.5',
  pin: 'M12 21s7-6.2 7-11.5A7 7 0 0 0 5 9.5C5 14.8 12 21 12 21ZM12 12a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z',
  target: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM12 2v3M12 19v3M2 12h3M19 12h3',
  calendar: 'M3 5h18v16H3ZM3 10h18M8 3v4M16 3v4',
  up: 'm6 15 6-6 6 6',
  down: 'm6 9 6 6 6-6',
  check: 'M20 6 9 17l-5-5',
  warn: 'M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z',
  lock: 'M5 11h14v10H5ZM8 11V7a4 4 0 0 1 8 0v4',
  magic:
    'M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1',
  umbrella: 'M3 12a9 9 0 0 1 18 0ZM12 12v7a2 2 0 0 0 4 0',
  draw: 'M4 20 8 6l9 3 3 9ZM4 20h.01M8 6h.01M17 9h.01',
  undo: 'M9 14 4 9l5-5M4 9h11a5 5 0 0 1 0 10h-3',
  plus: 'M12 5v14M5 12h14',
  trash: 'M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3',
  edit: 'M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z',
  arrowRight: 'M5 12h14M13 6l6 6-6 6',
  close: 'M6 6l12 12M18 6 6 18',
  dash: 'M3 12h18',
  alert: 'M12 8v4M12 16h.01M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20Z',
};
