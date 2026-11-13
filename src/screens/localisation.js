/** 3 · Localisation de la ferme. Owner: Loïc. Demo places until a geocoder is plugged in. */
import { html } from '../lib/html.js';
import { DEMO_PLACES } from '../data/catalog.js';
import { onboardingHeader } from '../ui/layout.js';
import { icon, ICONS } from '../ui/icons.js';
import { fakeSatellite } from '../ui/fakeMap.js';

export default {
  title: 'Localisation',
  render(state) {
    const sel = state.ui.placeSel;
    const p = DEMO_PLACES[sel];
    return html`${onboardingHeader(2)}
      <main class="map-screen" id="main">
        ${fakeSatellite()}
        <div class="map-overlay">
          <div class="floating-card stack-sm">
            <div class="stack-xs">
              <h1 class="h2 h2--lg">Où est votre ferme ?</h1>
              <p class="muted small">
                Cherchez une adresse, une ville ou un rang. On centre la carte dessus.
              </p>
            </div>
            <label class="search"
              ><span class="sr-only">Rechercher une adresse</span
              >${icon(ICONS.search, { size: 18 })}<input
                type="search"
                value="Saint-Hyacinthe"
                aria-describedby="place-hint"
            /></label>
            <span id="place-hint" class="sr-only"
              >Choisissez un résultat dans la liste ci-dessous.</span
            >
            <div class="stack-xs">
              ${DEMO_PLACES.map(
                (pl, i) =>
                  html`<button
                    type="button"
                    class="place ${i === sel ? 'is-selected' : ''}"
                    data-action="pick-place"
                    data-i="${i}"
                  >
                    ${icon(ICONS.pin, { size: 18, color: '#2E6B3B' })}<span class="stack-0"
                      ><strong>${pl.label}</strong
                      ><span class="muted small">${pl.detail}</span></span
                    >
                  </button>`,
              )}
            </div>
            <button type="button" class="btn btn--dashed">
              ${icon(ICONS.target, { size: 18 })}Utiliser ma position actuelle
            </button>
          </div>
        </div>
        <div class="map-pin" style="left: ${p.x}%; top: ${p.y}%">
          <span class="map-pin__label">${p.label}</span>
          <svg width="40" height="52" viewBox="0 0 40 52" aria-hidden="true">
            <path
              d="M20 50S36 32 36 19A16 16 0 0 0 4 19c0 13 16 31 16 31Z"
              fill="#D55E00"
              stroke="#FFFFFF"
              stroke-width="3"
            ></path>
            <circle cx="20" cy="19" r="6" fill="#FFFFFF"></circle>
          </svg>
        </div>
        <div class="map-bottom">
          <div class="stack-0">
            <span class="muted small">Ferme sélectionnée</span
            ><strong>${p.label} · ${p.detail}</strong>
          </div>
          <div class="row-wrap gap-sm">
            <a class="btn btn--secondary" href="#/type-de-ferme">Retour</a>
            <button type="button" class="btn btn--primary" data-action="confirm-place">
              C’est ici, tracer ma ferme →
            </button>
          </div>
        </div>
      </main>`;
  },
  actions: {
    'pick-place': (app, el) =>
      app.update((s) => {
        s.ui.placeSel = Number(el.dataset.i);
      }),
    'confirm-place': (app) => {
      const p = DEMO_PLACES[app.state.ui.placeSel];
      app.updateFarm((farm) => {
        farm.farm.location = { lat: p.lat, lon: p.lon, label: p.detail };
      });
      app.go('#/tracer');
    },
  },
};
