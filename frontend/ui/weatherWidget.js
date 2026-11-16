/**
 * Dashboard band, across the page: weather now and for the week at the farm (Open-Meteo).
 * The forecast is fetched by the application (app.loadWeather, data/access/weather.js).
 */
import { html } from '../lib/html.js';
import { icon } from './icons.js';
import { formatDate, formatNumber, t } from '../../data/i18n/index.js';

/** "2026-11-12" → "jeu." (the first day is "Auj."). */
export function dayLabel(date, i) {
  if (i === 0) return t('Auj.');
  return formatDate(date, { weekday: 'short' });
}

const W_ICONS = {
  sun: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8ZM12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4',
  'cloud-sun':
    'M12 3v1.5M5.6 5.6l1 1M3 12h1.5M18.4 5.6l-1 1M9 11.5A4 4 0 0 1 16 10M7 20h10a4 4 0 0 0 .5-8A5 5 0 0 0 8 13.5 3.3 3.3 0 0 0 7 20Z',
  cloud: 'M7 19h10a4 4 0 0 0 .6-7.95A6 6 0 0 0 6.3 12.1 3.5 3.5 0 0 0 7 19Z',
  fog: 'M4 14h16M6 18h12M8 22h8M7 10h10a4 4 0 0 0 .6-7.95A6 6 0 0 0 6.3 3.1 3.5 3.5 0 0 0 7 10Z',
  drizzle:
    'M7 15h10a4 4 0 0 0 .6-7.95A6 6 0 0 0 6.3 8.1 3.5 3.5 0 0 0 7 15ZM9 18v2M13 18v2M17 18v2',
  rain: 'M7 14h10a4 4 0 0 0 .6-7.95A6 6 0 0 0 6.3 7.1 3.5 3.5 0 0 0 7 14ZM8 17l-1 4M12 17l-1 4M16 17l-1 4',
  snow: 'M7 14h10a4 4 0 0 0 .6-7.95A6 6 0 0 0 6.3 7.1 3.5 3.5 0 0 0 7 14ZM8 18h.01M12 18h.01M16 18h.01M10 21h.01M14 21h.01',
  storm: 'M7 13h10a4 4 0 0 0 .6-7.95A6 6 0 0 0 6.3 6.1 3.5 3.5 0 0 0 7 13ZM13 13l-3 5h4l-3 5',
};

const deg = (n) => (typeof n === 'number' ? `${Math.round(n)}°` : '—');
const mm = (n) =>
  typeof n === 'number' ? `${formatNumber(n, { maximumFractionDigits: 1 })} mm` : '—';

export function weatherWidget(state) {
  const w = state.weather;
  const head = html`<div class="row-between">
    <h2 class="h2">Météo à la ferme</h2>
    <span class="muted small">Open-Meteo</span>
  </div>`;

  if (!w.data) {
    return html`<section class="card stack-sm weather" aria-label="Météo à la ferme">
      ${head}
      ${
        w.status === 'error'
          ? html`<div class="row-between wrap small">
              <span class="muted">⚠ ${w.error}</span>
              <button type="button" class="btn btn--secondary btn--sm" data-action="retry-weather">
                Réessayer
              </button>
            </div>`
          : html`<div class="weather__skeleton" aria-busy="true">
              <span></span><span></span><span></span>
            </div>`
      }
    </section>`;
  }

  const c = w.data.current;
  const today = w.data.daily[0];
  return html`<section class="card stack-sm weather" aria-label="Météo à la ferme">
    ${head}
    <div class="weather__band">
      <div class="weather__now">
        <span class="weather__icon">${icon(W_ICONS[c.icon] ?? W_ICONS.cloud, { size: 44 })}</span>
        <span class="weather__temp">${deg(c.temp)}</span>
        <span class="stack-0">
          <strong>${c.label}</strong>
          <span class="muted small"
            >Ressenti ${deg(c.feelsLike)} ·
            ${today ? `${deg(today.tmin)} / ${deg(today.tmax)}` : ''}</span
          >
        </span>
      </div>
      <dl class="weather__facts">
        <div>
          <dt>Vent</dt>
          <dd>${typeof c.wind === 'number' ? `${Math.round(c.wind)} km/h` : '—'}</dd>
        </div>
        <div>
          <dt>Humidité</dt>
          <dd>${typeof c.humidity === 'number' ? `${c.humidity} %` : '—'}</dd>
        </div>
        <div>
          <dt>Pluie aujourd’hui</dt>
          <dd>${mm(today?.rain)}</dd>
        </div>
      </dl>
      <ol class="weather__week" aria-label="Prévisions sur 7 jours">
        ${w.data.daily.map(
          (d, i) =>
            html`<li title="${d.label} · pluie ${mm(d.rain)}">
              <span class="muted small">${dayLabel(d.date, i)}</span>
              ${icon(W_ICONS[d.icon] ?? W_ICONS.cloud, { size: 20 })}
              <strong class="small">${deg(d.tmax)}</strong>
              <span class="muted small">${deg(d.tmin)}</span>
            </li>`,
        )}
      </ol>
    </div>
  </section>`;
}
