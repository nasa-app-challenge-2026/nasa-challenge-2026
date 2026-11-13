/** 7 · Mon champ: NASA data of one section. Owner: Justin. Data comes from engine.getFieldData. */
import { html } from '../lib/html.js';
import { CROPS } from '../data/crops.js';
import { buildCalendar } from '../lib/rotation.js';
import { sectionLayout, pageTitle } from '../ui/layout.js';
import { infoButton, loading, sparkline, switchButton } from '../ui/widgets.js';

function metricCard(state, sectionId, m) {
  const key = `${sectionId}:${m.id}`;
  const open = state.ui.openInfo === key;
  const reported = !!state.ui.reported[key];
  return html`<article class="card metric ${m.fromSensors ? 'is-sensor' : ''}">
    <div class="row-between">
      <span class="strong muted">${m.label}</span
      >${infoButton('toggle-info', m.label, html`data-key="${key}" aria-expanded="${String(open)}"`)}
    </div>
    <div class="metric__value">
      <span>${typeof m.value === 'number' ? String(m.value).replace('.', ',') : m.value}</span
      ><span class="muted">${m.unit}</span>
    </div>
    ${sparkline(m.series)} ${open ? html`<p class="explain">${m.explain}</p>` : ''}
    <div class="row-between divider-top">
      <span class="small ${m.fromSensors ? 'text-brand strong' : 'muted'}">${m.source}</span>
      <button
        type="button"
        class="report-btn ${reported ? 'is-on' : ''}"
        data-action="toggle-report"
        data-key="${key}"
      >
        ${reported ? '✓ Signalé' : '⚑ Signaler'}
      </button>
    </div>
  </article>`;
}

export default {
  title: 'Mon champ',
  rota: 'champ',
  onEnter: (app, { id }) => app.loadField(id),
  render(state, { id }, app) {
    const section = app.section(id);
    const f = state.field[id];
    const yi = state.ui.yearIndex;
    const cal = buildCalendar(section.rotation, {
      offset: section.offset,
      startYear: state.farm.farm.startYear,
      horizonYears: state.farm.farm.horizonYears,
    });
    const now = cal[yi] ?? cal[0];
    const body = html` ${pageTitle(
        'Mon champ',
        `Ce que les satellites de la NASA voient sur la section ${id}, en moyenne sur les 10 dernières années.`,
        html`<div class="toggle-card">
          <span class="stack-0"
            ><strong class="small">J’ai des capteurs</strong
            ><span class="muted small">Option grandes fermes</span></span
          >${switchButton(state.farm.farm.sensors, 'toggle-sensors', 'J’ai des capteurs')}
        </div>`,
      )}
      <div class="row-wrap align-start gap-lg">
        <div class="grid grid--metrics grow-3">
          ${f?.status === 'error' ? html`<div class="alert alert--bad">⚠ ${f.error}</div>` : ''}
          ${f?.data ? f.data.metrics.map((m) => metricCard(state, id, m)) : loading('Lecture des données satellites…')}
        </div>
        <div class="card card--flush grow-1 section-map">
          <svg
            viewBox="0 0 320 300"
            role="img"
            aria-label="Carte de la section ${id}, en ${CROPS[now.crop]?.name ?? '—'} en ${now.year}"
          >
            <rect width="320" height="300" fill="url(#pat-soya)"></rect>
            <rect x="210" y="0" width="110" height="300" fill="url(#pat-orge)"></rect>
            <rect x="0" y="230" width="210" height="70" fill="url(#pat-mais)"></rect>
            <polygon
              points="40,40 200,40 200,220 40,220"
              fill="url(#pat-${now.crop})"
              stroke="#FFFFFF"
              stroke-width="4"
            ></polygon>
            <rect
              x="96"
              y="104"
              width="48"
              height="48"
              rx="12"
              fill="#FFFFFF"
              fill-opacity=".92"
            ></rect>
            <text x="120" y="139" text-anchor="middle" class="map-section__id">${id}</text>
          </svg>
          <div class="pad stack-0">
            <strong
              >Section ${id} · ${section.areaHa} ha · ${CROPS[now.crop]?.name.toLowerCase()} en
              ${now.year}</strong
            ><span class="muted small">${section.note ?? ''}</span>
          </div>
        </div>
      </div>
      <div class="actions-bar">
        <a class="btn btn--secondary" href="#/tableau">Retour</a
        ><a class="btn btn--primary" href="#/section/${id}/rotation">Planifier la rotation →</a>
      </div>`;
    return sectionLayout(state, section, 'champ', body);
  },
  actions: {
    'toggle-info': (app, el) =>
      app.update((s) => (s.ui.openInfo = s.ui.openInfo === el.dataset.key ? null : el.dataset.key)),
    'toggle-report': (app, el) =>
      app.update((s) => (s.ui.reported[el.dataset.key] = !s.ui.reported[el.dataset.key])),
    'toggle-sensors': (app) => {
      app.updateFarm((farm) => (farm.farm.sensors = !farm.farm.sensors));
      app.loadField(app.state.ui.route.params.id, { force: true });
    },
  },
};
