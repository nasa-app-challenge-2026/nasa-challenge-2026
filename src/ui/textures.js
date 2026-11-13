/**
 * Field textures, one SVG <pattern> per crop. Injected once in the page, then
 * used anywhere with fill="url(#pat-<cropId>)". The rotation makes the rows
 * follow the edges of the isometric tiles.
 */
import { html } from '../lib/html.js';

const P = (id, w, h, body) =>
  `<pattern id="pat-${id}" width="${w}" height="${h}" patternUnits="userSpaceOnUse" patternTransform="rotate(-27)">${body}</pattern>`;

export const TEXTURE_DEFS = `<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false"><defs>
${P('ble', 10, 14, '<rect width="10" height="14" fill="#D6AE57"/><path d="M2.5 14V6M7.5 14V4" stroke="#A9802D" stroke-width="1.1"/><ellipse cx="2.5" cy="4.5" rx="1.5" ry="2.8" fill="#EDCF7E"/><ellipse cx="7.5" cy="2.8" rx="1.5" ry="2.8" fill="#E4C26C"/>')}
${P('orge', 10, 12, '<rect width="10" height="12" fill="#E3D196"/><path d="M2 12V5M7 12V4M2 5 0.5 2M2 5 3.5 2M7 4 5.5 1M7 4 8.5 1" stroke="#BFA45C" stroke-width="0.9"/>')}
${P('mais', 16, 16, '<rect width="16" height="16" fill="#4F7F33"/><rect y="14.5" width="16" height="1.5" fill="#3B2C1C" fill-opacity=".55"/><path d="M4 13 1 6M4 13 8 7M12 13 9 5M12 13l3-5" stroke="#8DC35A" stroke-width="1.6" stroke-linecap="round"/><circle cx="4" cy="3" r="1.2" fill="#E9D27A"/><circle cx="12" cy="2.5" r="1.2" fill="#E9D27A"/>')}
${P('soya', 12, 12, '<rect width="12" height="12" fill="#6B4E31"/><circle cx="3" cy="3" r="3.2" fill="#7FB04E"/><circle cx="9" cy="3" r="3.2" fill="#93C25F"/><circle cx="6" cy="9" r="3.4" fill="#86B856"/><circle cx="0" cy="9" r="3" fill="#7AAA4A"/><circle cx="12" cy="9" r="3" fill="#7AAA4A"/>')}
${P('patate', 14, 10, '<rect width="14" height="10" fill="#7A5634"/><path d="M0 9.5H14" stroke="#5B3F24" stroke-width="1"/><ellipse cx="4" cy="5" rx="3.6" ry="2.6" fill="#5F8A3B"/><ellipse cx="11" cy="4.5" rx="3.4" ry="2.4" fill="#6E9A45"/><circle cx="4" cy="4" r="0.9" fill="#F2F0E6"/>')}
${P('luzerne', 10, 10, '<rect width="10" height="10" fill="#3F7A45"/><circle cx="2" cy="2" r="1.6" fill="#5E9C55"/><circle cx="7" cy="6" r="1.8" fill="#5E9C55"/><circle cx="7" cy="2" r="1" fill="#9C84D0"/><circle cx="2.5" cy="7.5" r="1" fill="#B39BE0"/>')}
${P('sol', 12, 8, '<rect width="12" height="8" fill="#8A6845"/><path d="M0 7.5H12" stroke="#6C4F33" stroke-width="1.2"/><circle cx="3" cy="3" r="0.8" fill="#A5835E"/><circle cx="9" cy="4" r="0.7" fill="#A5835E"/>')}
</defs></svg>`;

/** A strip of field texture (the "photo" of a crop). */
export function fieldStrip(crop, height = 64, radius = 10) {
  return html`<svg
    class="field-strip"
    width="100%"
    height="${height}"
    preserveAspectRatio="none"
    aria-hidden="true"
    style="border-radius: ${radius}px"
  >
    <rect width="100%" height="100%" fill="url(#pat-${crop || 'sol'})"></rect>
  </svg>`;
}

/** Small square swatch of a crop texture. */
export function fieldSwatch(crop, size = 18) {
  return html`<svg class="field-swatch" width="${size}" height="${size}" aria-hidden="true">
    <rect width="${size}" height="${size}" rx="4" fill="url(#pat-${crop || 'sol'})"></rect>
  </svg>`;
}
