/**
 * 9 · Mon champ. Owner: Justin. The weak points of the section (step 8 of the
 * algorithm): erosion and water risks, the satellite measures behind the erosion,
 * what the water pressure is made of, and the soil (step 5). Values come from the
 * plan (FarmPlan.sections[].field). Rota explains each of them.
 */
import { html } from '../lib/html.js';
import { nameOf } from '../../data/reference/crops.js';
import {
  FIELD_MEASURES,
  RISKS,
  SOIL_PROPERTIES,
  WATER_COMPONENTS,
} from '../../data/reference/fieldMeasures.js';
import { cropOfYear, planYears } from '../../application/rules/planView.js';
import { sectionLayout, pageTitle } from '../ui/layout.js';
import { errorBox, loading } from '../ui/widgets.js';
import { askRota, askRotaIcon } from '../ui/rota.js';
import { farmPlan } from '../ui/farmPlan.js';
import { selectedYear } from '../ui/planWidgets.js';

const PERCENT = 100;
/** From this risk (in %), the bar turns to the warning colour. */
const HIGH_RISK_PCT = 50;
/** Values of the data services come with all their decimals: one is enough to read them. */
const ONE_DECIMAL = 10;
const DECIMAL_COMMA = (v) =>
  String(typeof v === 'number' ? Math.round(v * ONE_DECIMAL) / ONE_DECIMAL : v).replace('.', ',');

function riskCard(key, value) {
  const pct = Math.round(value * PERCENT);
  const high = pct >= HIGH_RISK_PCT;
  return html`<div class="card stack-xs">
    <span class="muted small">${RISKS[key].label}</span>
    <span class="h1 ${high ? 'text-warn' : ''}">${pct} %</span>
    <div class="bar">
      <div class="bar__fill ${high ? 'is-bad' : 'is-blue'}" style="width: ${pct}%"></div>
    </div>
  </div>`;
}

/** The satellite measures behind the erosion risk, in one card. */
function measuresCard(measures) {
  const known = Object.entries(measures).filter(([key]) => FIELD_MEASURES[key]);
  return html`<section class="card stack-sm">
    <h2 class="h2">Mesures par satellite</h2>
    <div class="facts">
      ${known.map(([key, value]) => {
        const m = FIELD_MEASURES[key];
        return html`<div class="stack-0">
          <span class="muted small row gap-xs">${m.label}${askRotaIcon(`mesure-${key}`)}</span>
          <strong>${DECIMAL_COMMA(value)} ${m.unit}</strong>
        </div>`;
      })}
    </div>
  </section>`;
}

/** What the water pressure of the farm is made of. */
function waterPressureCard(water) {
  const parts = Object.entries(water.components).filter(([k]) => WATER_COMPONENTS[k]);
  const missing = water.missing.filter((k) => WATER_COMPONENTS[k]);
  return html`<section class="card stack-sm">
    <div class="row-between wrap">
      <h2 class="h2">Pression sur l’eau · ${Math.round(water.pressure * PERCENT)} %</h2>
      ${askRotaIcon('pression-eau')}
    </div>
    <div class="stack-sm">
      ${parts.map(
        ([k, v]) =>
          html`<div class="score">
            <div class="score__row">
              <span class="score__label">${WATER_COMPONENTS[k].label}</span
              ><span><strong>${Math.round(v * PERCENT)}</strong></span>
            </div>
            <div class="score__track">
              <div class="score__fill" style="width: ${v * PERCENT}%"></div>
            </div>
          </div>`,
      )}
    </div>
    ${
      missing.length
        ? html`<span class="muted small"
            >Non mesuré ici :
            ${missing.map((k) => WATER_COMPONENTS[k].label.toLowerCase()).join(', ')}</span
          >`
        : ''
    }
  </section>`;
}

function soilCard(soil, sectionId) {
  return html`<section class="card stack-sm">
    <div class="row-between wrap">
      <h2 class="h2">Sol (0 à 30 cm)</h2>
      ${askRotaIcon('sol')}
    </div>
    <div class="facts">
      ${Object.entries(SOIL_PROPERTIES).map(([k, p]) => html`<div class="stack-0"><span class="muted small">${p.label}</span><strong>${DECIMAL_COMMA(soil[k])} ${p.unit}</strong></div>`)}
    </div>
    <span class="muted small"
      >${soil.source} ·
      <a href="#/section/${sectionId}/parcelle">Saisir mon analyse de sol</a></span
    >
  </section>`;
}

export default {
  title: 'Mon champ',
  rota: 'champ',
  render(state, { id }, app) {
    const section = app.section(id);
    const plan = app.sectionPlan(id);
    const year = selectedYear(state, planYears(state.plan.data));
    const f = state.farm.farm.time.frequencyMonths;
    const cropOf = (sid) => cropOfYear(app.section(sid), app.sectionPlan(sid), year, f).id;
    const crop = cropOf(id);
    const map = farmPlan({
      sections: state.farm.sections,
      boundary: state.farm.farm.boundary,
      cropOf,
      selectedId: id,
      label: `Carte de la section ${id} en ${year}`,
    });
    const field = plan?.field;
    const content = field
      ? html`<div class="grid grid--2">
            ${riskCard('erosion', field.risksToday.erosion)}${riskCard('water', field.risksToday.water)}
          </div>
          ${measuresCard(field.measures)}
          ${field.waterPressure ? waterPressureCard(field.waterPressure) : ''}
          ${soilCard(field.soil, id)}`
      : state.plan.status === 'error'
        ? errorBox(state.plan.error)
        : loading('Rota lit les données du champ', askRota('chargement'));
    const body = html`${pageTitle('Mon champ', '', askRota('risques'))}
      <div class="row-wrap align-start gap-lg">
        <div class="grow-3 stack-md">${content}</div>
        <div class="card card--flush grow-1 section-map">
          ${map ?? html`<div class="pad muted small">Section non tracée. <a href="#/tracer">Tracer cette section</a></div>`}
          <div class="pad">
            <strong
              >Section ${id} · ${section.areaHa} ha · ${crop ? nameOf(crop).toLowerCase() : 'rien'}
              en ${year}</strong
            >
          </div>
        </div>
      </div>`;
    return sectionLayout(state, section, 'champ', body);
  },
};
