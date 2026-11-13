/**
 * 3 · Localisation de la ferme. Owner: Loïc.
 * Real Leaflet map (satellite + plan): drag the pin or click the map, search
 * an address (Nominatim) or use the browser's position.
 */
import { html } from '../lib/html.js';
import { DEMO_PLACES } from '../data/catalog.js';
import { onboardingHeader } from '../ui/layout.js';
import { icon, ICONS } from '../ui/icons.js';
import { mapSlot, ensureMap, getMap, destroyMap, pinIcon, L } from '../ui/leafletMap.js';
import { geocode, reverseGeocode, coordsLabel } from '../lib/geocode.js';

const KEY = 'localisation';
let marker = null;

const round = (n) => Math.round(n * 1e5) / 1e5;
const same = (a, b) => Math.abs(a - b) < 1e-7;

function setLocation(app, lat, lon, label, { fly = true, zoom } = {}) {
  app.update((s) => {
    s.farm.farm.location = { lat, lon, label: label ?? coordsLabel(lat, lon) };
  });
  const map = getMap(KEY);
  if (map && fly) map.flyTo([lat, lon], zoom ?? Math.max(map.getZoom(), 15), { duration: 0.8 });
  if (!label) {
    reverseGeocode(lat, lon).then((found) => {
      if (!found) return;
      app.update((s) => {
        const loc = s.farm.farm.location;
        if (same(loc.lat, lat) && same(loc.lon, lon)) loc.label = found;
      });
    });
  }
}

export default {
  title: 'Localisation',
  render(state) {
    const loc = state.farm.farm.location;
    const geo = state.ui.geo;
    const places = geo.results ?? DEMO_PLACES;
    const isSel = (p) => same(p.lat, loc.lat) && same(p.lon, loc.lon);
    return html`${onboardingHeader(2)}
      <main class="map-screen" id="main">
        ${mapSlot(KEY, 'Carte pour situer la ferme')}
        <div class="map-overlay">
          <div class="floating-card stack-sm">
            <div class="stack-xs">
              <h1 class="h2 h2--lg">Où est votre ferme ?</h1>
              <p class="muted small">
                Cherchez une adresse, un rang ou un village, puis ajustez l’épingle : glissez-la ou
                cliquez sur la carte.
              </p>
            </div>
            <form class="search-form" data-submit="search-place">
              <label class="search"
                ><span class="sr-only">Rechercher une adresse</span
                >${icon(ICONS.search, { size: 18 })}<input
                  id="place-query"
                  data-preserve
                  type="search"
                  name="q"
                  value="${geo.query}"
                  placeholder="Adresse, rang, village…"
                  autocomplete="off"
                  aria-describedby="place-hint"
              /></label>
              <button
                type="submit"
                class="btn btn--primary"
                ${geo.status === 'loading' ? 'disabled' : ''}
              >
                ${geo.status === 'loading' ? 'Recherche…' : 'Chercher'}
              </button>
            </form>
            <span id="place-hint" class="sr-only"
              >Choisissez un résultat dans la liste ci-dessous, ou déplacez l’épingle sur la
              carte.</span
            >
            ${geo.error ? html`<div class="alert alert--bad small">⚠ ${geo.error}</div>` : ''}
            <div class="stack-xs" aria-live="polite">
              <span class="eyebrow"
                >${geo.results ? (places.length ? 'Résultats' : 'Aucun résultat') : 'Suggestions'}</span
              >
              ${places.map(
                (pl) =>
                  html`<button
                    type="button"
                    class="place ${isSel(pl) ? 'is-selected' : ''}"
                    data-action="pick-place"
                    data-lat="${pl.lat}"
                    data-lon="${pl.lon}"
                    data-label="${[pl.label, pl.detail].filter(Boolean).join(', ')}"
                  >
                    ${icon(ICONS.pin, { size: 18, color: '#2E6B3B' })}<span class="stack-0"
                      ><strong>${pl.label}</strong
                      ><span class="muted small">${pl.detail}</span></span
                    >
                  </button>`,
              )}
            </div>
            <button
              type="button"
              class="btn btn--dashed"
              data-action="use-my-position"
              ${geo.status === 'locating' ? 'disabled' : ''}
            >
              ${icon(ICONS.target, { size: 18 })}${
                geo.status === 'locating'
                  ? 'Localisation en cours…'
                  : 'Utiliser ma position actuelle'
              }
            </button>
          </div>
        </div>
        <div class="map-bottom">
          <div class="stack-0">
            <span class="muted small">Ferme sélectionnée</span><strong>${loc.label}</strong
            ><span class="muted small">${coordsLabel(loc.lat, loc.lon)}</span>
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

  mount(app) {
    const loc = app.state.farm.farm.location;
    const { map, created } = ensureMap(KEY, { center: [loc.lat, loc.lon], zoom: 14 });
    if (created) {
      marker = L.marker([loc.lat, loc.lon], {
        draggable: true,
        autoPan: true,
        icon: pinIcon,
        title: 'Votre ferme (glisser pour déplacer)',
      }).addTo(map);
      marker.bindTooltip(loc.label, {
        permanent: true,
        direction: 'top',
        offset: [0, -52],
        className: 'pin-label',
      });
      marker.on('dragend', () => {
        const ll = marker.getLatLng();
        setLocation(app, round(ll.lat), round(ll.lng), null, { fly: false });
      });
      map.on('click', (e) =>
        setLocation(app, round(e.latlng.lat), round(e.latlng.lng), null, { fly: false }),
      );
    }
    const ll = marker.getLatLng();
    if (!same(ll.lat, loc.lat) || !same(ll.lng, loc.lon)) marker.setLatLng([loc.lat, loc.lon]);
    marker.setTooltipContent(loc.label);
  },

  unmount() {
    destroyMap(KEY);
    marker = null;
  },

  actions: {
    'search-place': async (app, form) => {
      const q = form.querySelector('input[name="q"]').value.trim();
      if (!q) return;
      app.update((s) => {
        s.ui.geo = { query: q, results: s.ui.geo.results, status: 'loading', error: null };
      });
      try {
        const results = await geocode(q);
        app.update((s) => {
          s.ui.geo = { query: q, results, status: 'ready', error: null };
        });
        const first = results[0];
        if (first) {
          setLocation(app, first.lat, first.lon, [first.label, first.detail].join(', '), {
            zoom: 15,
          });
        }
      } catch (err) {
        app.update((s) => {
          s.ui.geo = { ...s.ui.geo, status: 'error', error: err.message };
        });
      }
    },
    'pick-place': (app, el) =>
      setLocation(app, Number(el.dataset.lat), Number(el.dataset.lon), el.dataset.label, {
        zoom: 15,
      }),
    'use-my-position': (app) => {
      if (!navigator.geolocation) {
        app.update((s) => {
          s.ui.geo.error = 'Votre navigateur ne donne pas accès à la position.';
        });
        return;
      }
      app.update((s) => {
        s.ui.geo.status = 'locating';
        s.ui.geo.error = null;
      });
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          app.update((s) => {
            s.ui.geo.status = 'ready';
          });
          setLocation(app, round(pos.coords.latitude), round(pos.coords.longitude), null, {
            zoom: 15,
          });
        },
        () =>
          app.update((s) => {
            s.ui.geo.status = 'error';
            s.ui.geo.error = 'Position refusée ou indisponible. Cherchez une adresse à la place.';
          }),
        { enableHighAccuracy: true, timeout: 10_000 },
      );
    },
    'confirm-place': (app) => {
      app.refreshPlan();
      app.go('#/tracer');
    },
  },
};
