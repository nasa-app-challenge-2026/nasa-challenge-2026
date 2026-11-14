/**
 * Dashboard block, deliberately small: one line that says whether there is a
 * risk right now (a big fire burning nearby, or a high fire danger today).
 * Everything else is on the fire page (#/feux).
 */
import { html } from '../lib/html.js';
import { fireStatus } from '../../application/rules/wildfire.js';
import { DASH_FIRE, ctxKey, fireSubject } from '../../application/fireController.js';
import { icon } from './icons.js';

const FLAME = 'M12 22c4 0 7-3 7-7 0-3-2-6-4-8 0 2-1 4-3 4 0-3-1-6-4-9 0 4-5 7-5 13 0 4 4 7 9 7Z';

function statusLine(entry) {
  if (!entry?.data) {
    return entry?.status === 'error'
      ? html`<span class="muted small"
          >Données des feux indisponibles.
          <button type="button" class="link-btn small" data-action="retry-fire">
            Réessayer
          </button></span
        >`
      : html`<div class="weather__skeleton" aria-busy="true"><span></span></div>`;
  }
  const st = fireStatus(entry.data.events, entry.data.danger);
  if (st.tone === 'calm') return html`<span class="text-good strong">✓ ${st.title}</span>`;
  return html`<div
    class="alert ${st.tone === 'alert' ? 'alert--bad' : 'alert--warn'} small"
    role="${st.tone === 'alert' ? 'alert' : 'status'}"
  >
    <span aria-hidden="true">⚠</span><span><strong>${st.title}.</strong></span>
  </div>`;
}

export function fireWidget(state) {
  const entry = state.fire.ctx[ctxKey(fireSubject(state, 'farm'), DASH_FIRE)];
  // During an alert, the fire page opens on what to do on each section.
  const alert = !!entry?.data && fireStatus(entry.data.events, entry.data.danger).tone === 'alert';
  return html`<section class="card stack-xs fire-widget" aria-label="Feux près de la ferme">
    <strong class="row gap-xs">${icon(FLAME, { size: 18 })}Feux près de la ferme</strong>
    ${statusLine(entry)}
    <a class="link-btn small strong fire-widget__link" href="#/feux"
      >${alert ? 'Que faire sur mes sections →' : 'Voir les détails →'}</a
    >
  </section>`;
}
