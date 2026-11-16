/**
 * 11 · Climat et jumeaux. Owner: Justin. For each cycle: the climate the farm will
 * have (step 3: NASA POWER trend or climate models), its twins (step 4: places that
 * already had that climate in 2011–2024, one arrow per model on the map) and what
 * the twins grow (steps 5 to 7).
 */
import { html } from '../lib/html.js';
import { formatNumber, getLanguage, t } from '../../data/i18n/index.js';
import { CROPS } from '../../data/reference/crops.js';
import { sectionLayout, pageTitle } from '../ui/layout.js';
import { errorBox, loading } from '../ui/widgets.js';
import { askRota, askRotaIcon } from '../ui/rota.js';
import { cycleTabs, dayLabel, planStatus, selectedCycle } from '../ui/planWidgets.js';
import { destroyMap, ensureMap, L, mapSlot } from '../ui/leafletMap.js';

const KEY = 'jumeaux';
/** Colours of the arrows, one per climate source (colour-blind safe). */
const SOURCE_COLORS = ['#0072B2', '#D55E00', '#009E73', '#CC79A7', '#E69F00'];
const FARM_COLOR = '#FFD27A';
const TWIN_RADIUS_M = 20000;
const MAP_PADDING_PX = 30;

let layer = null;
let drawnKey = null;

const fmt1 = (v) => formatNumber(v, { maximumFractionDigits: 1 });
/** Sigma rounds to 0 for very close twins: say "< 0,1" rather than "0". */
const SMALLEST_SIGMA_SHOWN = 0.05;
const fmtSigma = (v) => (v < SMALLEST_SIGMA_SHOWN ? `< ${fmt1(0.1)}` : fmt1(v));

function climateCard(cycle) {
  const c = cycle.climate;
  return html`<section class="card stack-sm">
    <div class="row-between wrap">
      <h2 class="h2">Climat visé · ${cycle.years[0]}–${cycle.years[1]}</h2>
      ${askRotaIcon('climat-vise')}
    </div>
    <span class="muted small">${c.source}</span>
    <div class="facts">
      <div class="stack-0">
        <span class="muted small">Réchauffement vs 2005–2024</span
        ><strong>${c.warmingC >= 0 ? '+' : ''}${fmt1(c.warmingC)} °C</strong>
      </div>
      <div class="stack-0">
        <span class="muted small">Dernier gel</span><strong>${dayLabel(c.lastSpringFrost)}</strong>
      </div>
      <div class="stack-0">
        <span class="muted small">Premier gel</span><strong>${dayLabel(c.firstFallFrost)}</strong>
      </div>
      <div class="stack-0">
        <span class="muted small">Minimum de janvier</span
        ><strong>${fmt1(c.januaryMinimumC)} °C</strong>
      </div>
      <div class="stack-0">
        <span class="muted small">Pluie d’été</span
        ><strong
          >${c.summerRainChangePct >= 0 ? '+' : ''}${Math.round(c.summerRainChangePct)} %</strong
        >
      </div>
      <div class="stack-0">
        <span class="muted small">Récoltes à date fixe</span
        ><strong>${c.harvestAdvanceDays} j plus tôt</strong>
      </div>
    </div>
  </section>`;
}

function twinsCard(cycle) {
  const t = cycle.twins;
  return html`<section class="card stack-sm">
    <div class="row-between wrap">
      <h2 class="h2 row gap-xs">${t.cells.length} jumeaux climatiques${askRotaIcon('jumeaux')}</h2>
      <span class="pill ${t.reliable ? 'pill--info' : 'pill--warn'}"
        >σ moyen ${t.sigmaMean === null ? '—' : fmtSigma(t.sigmaMean)} ·
        ${t.reliable ? 'bons jumeaux' : 'aucun vrai jumeau'}</span
      >
    </div>
    <span class="small"
      ><strong>Cultivé chez les jumeaux :</strong>
      ${t.crops.map((c) => CROPS[c]?.name ?? c).join(', ')}</span
    >
  </section>`;
}

function drawTwins(map, farm, cycle) {
  layer?.remove();
  layer = L.layerGroup().addTo(map);
  const sources = [...new Set(cycle.twins.cells.flatMap((c) => c.sources))];
  const color = (s) => SOURCE_COLORS[sources.indexOf(s) % SOURCE_COLORS.length];
  const points = [[farm.lat, farm.lon]];
  for (const cell of cycle.twins.cells) {
    points.push([cell.lat, cell.lon]);
    L.circle([cell.lat, cell.lon], {
      radius: TWIN_RADIUS_M,
      color: color(cell.sources[0]),
      weight: 2,
      fillOpacity: 0.25,
    })
      .bindTooltip(`σ ${fmtSigma(cell.sigma)} · ${cell.sources.join(', ')}`)
      .addTo(layer);
  }
  for (const source of sources) {
    const cells = cycle.twins.cells.filter((c) => c.sources.includes(source));
    const lat = cells.reduce((a, c) => a + c.lat, 0) / cells.length;
    const lon = cells.reduce((a, c) => a + c.lon, 0) / cells.length;
    L.polyline(
      [
        [farm.lat, farm.lon],
        [lat, lon],
      ],
      { color: color(source), weight: 4, dashArray: '8 6' },
    )
      .bindTooltip(source)
      .addTo(layer);
  }
  L.circleMarker([farm.lat, farm.lon], {
    radius: 9,
    color: '#18211B',
    fillColor: FARM_COLOR,
    fillOpacity: 1,
  })
    .bindTooltip(t('Votre ferme'))
    .addTo(layer);
  map.fitBounds(points, { padding: [MAP_PADDING_PX, MAP_PADDING_PX], animate: false });
}

export default {
  title: 'Climat et jumeaux',
  rota: 'jumeaux',
  render(state, { id }, app) {
    const section = app.section(id);
    const plan = app.sectionPlan(id);
    const head = pageTitle('Climat et jumeaux');
    if (!plan) {
      const wait =
        state.plan.status === 'error'
          ? errorBox(state.plan.error)
          : loading('Rota cherche vos jumeaux climatiques', askRota('chargement'));
      return sectionLayout(state, section, 'jumeaux', html`${head}${wait}`);
    }
    const cycle = selectedCycle(plan, state);
    const body = html`${head} ${planStatus(state)} ${cycleTabs(plan, cycle.index)}
      <div class="row-wrap align-start gap-lg">
        <div class="grow-1 stack-md">${climateCard(cycle)}${twinsCard(cycle)}</div>
        <div class="card card--flush grow-2 twins-map">
          ${mapSlot(KEY, 'Carte des jumeaux climatiques')}
        </div>
      </div>`;
    return sectionLayout(state, section, 'jumeaux', body);
  },
  mount(app, { id }) {
    const plan = app.sectionPlan(id);
    const farm = app.state.farm.farm.location;
    if (!plan || !farm) return;
    const cycle = selectedCycle(plan, app.state);
    const { map } = ensureMap(KEY, { center: [farm.lat, farm.lon], zoom: 6 });
    const key = `${id}:${cycle.index}:${app.state.plan.data.meta.generatedAt}:${getLanguage()}`;
    if (key !== drawnKey) {
      drawnKey = key;
      drawTwins(map, farm, cycle);
    }
  },
  unmount() {
    destroyMap(KEY);
    layer = null;
    drawnKey = null;
  },
};
