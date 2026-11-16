/**
 * Leaflet glue for an app that re-renders screens with innerHTML.
 *
 * A map lives in a host <div> that is created once and kept in memory; each
 * render puts a `mapSlot(key)` placeholder in the HTML and `attachSlots()`
 * moves the host back into it. Leaflet's state (tiles, layers, listeners)
 * survives, so the map never flickers or resets when the state changes.
 */
import L from 'leaflet';
import { html } from '../lib/html.js';
import { getLanguage, t } from '../../data/i18n/index.js';

const hosts = new Map();
const maps = new Map();
const controls = new Map();

function localizeControls(key) {
  const data = controls.get(key);
  if (!data || data.language === getLanguage()) return;
  data.widgets.forEach((widget) => widget.remove());
  data.widgets = [
    L.control
      .layers(
        { Satellite: data.satellite, [t('Carte')]: data.plan },
        { [t('Noms de lieux')]: data.names },
        { position: 'topright' },
      )
      .addTo(data.map),
    L.control
      .zoom({ position: 'topright', zoomInTitle: t('Zoomer'), zoomOutTitle: t('Dézoomer') })
      .addTo(data.map),
  ];
  data.language = getLanguage();
}

export const mapSlot = (key, label = 'Carte') =>
  html`<div
    class="leaflet-slot"
    data-map-slot="${key}"
    role="application"
    aria-label="${label}"
  ></div>`;

function host(key) {
  let el = hosts.get(key);
  if (!el) {
    el = document.createElement('div');
    el.className = 'leaflet-host';
    hosts.set(key, el);
  }
  return el;
}

/** Re-attach kept map hosts into the freshly rendered slots. */
export function attachSlots(root) {
  for (const slot of root.querySelectorAll('[data-map-slot]')) {
    const el = host(slot.dataset.mapSlot);
    if (el.parentNode !== slot) slot.appendChild(el);
    maps.get(slot.dataset.mapSlot)?.invalidateSize({ animate: false });
  }
}

export const getMap = (key) => maps.get(key) ?? null;

/** Create (once) a map with the satellite / plan base layers. */
export function ensureMap(key, { center, zoom = 14 }) {
  const existing = maps.get(key);
  if (existing) {
    localizeControls(key);
    return { map: existing, created: false };
  }

  const map = L.map(host(key), {
    center,
    zoom,
    zoomControl: false,
    attributionControl: false,
    doubleClickZoom: false,
  });
  const satellite = L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    { maxZoom: 19, attribution: 'Images © Esri, Maxar, Earthstar Geographics' },
  );
  const plan = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© OpenStreetMap',
  });
  const names = L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
    { maxZoom: 19 },
  );
  satellite.addTo(map);
  names.addTo(map);
  controls.set(key, { map, satellite, plan, names, widgets: [], language: null });
  localizeControls(key);
  L.control.attribution({ position: 'bottomleft', prefix: false }).addTo(map);
  maps.set(key, map);
  return { map, created: true };
}

export function destroyMap(key) {
  maps.get(key)?.remove();
  maps.delete(key);
  hosts.delete(key);
  controls.delete(key);
}

/** The orange pin of the mock-ups, as a Leaflet icon. */
export const pinIcon = L.divIcon({
  className: 'pin-icon',
  iconSize: [40, 52],
  iconAnchor: [20, 50],
  html: `<svg width="40" height="52" viewBox="0 0 40 52" aria-hidden="true"><path d="M20 50S36 32 36 19A16 16 0 0 0 4 19c0 13 16 31 16 31Z" fill="#D55E00" stroke="#FFFFFF" stroke-width="3"></path><circle cx="20" cy="19" r="6" fill="#FFFFFF"></circle></svg>`,
});

export { L };
