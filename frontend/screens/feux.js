/**
 * Feux près de la ferme: a sub-page of the dashboard (opened from its "fire"
 * block, not from the main menu). Only the essentials, calm by default:
 *
 *   1. Is there a risk right now (a big fire burning nearby, a high fire danger).
 *   2. Fires of the last 12 months on a map and in a list (25 km around the
 *      farm, NASA MODIS/VIIRS hotspots and CWFIS burned areas); older ones
 *      wait in the folded archives.
 *   3. The chosen fire: did each section burn (dNBR from NASA HLS images just
 *      before and just after the fire).
 *   4. Sections hit: what to do, and a change to the next crop of the current
 *      rotation the farmer can apply (the algorithm then plans again).
 *
 * The page can also run on a real farm fire (data/reference/fireExample.js)
 * without touching the user's farm. Data loading lives in
 * application/fireController.js.
 */
import { escapeHtml, html, plural } from '../lib/html.js';
import { nameOf } from '../../data/reference/crops.js';
import { getSeeds } from '../../application/rules/seeds.js';
import {
  alertAdvice,
  assessSection,
  burntYears,
  eventTitle,
  farmBox,
  farmCenter,
  fireStatus,
  fmtDay,
  fmtKm,
  fmtPeriod,
  fuelInfo,
  isMajorFire,
  isVegetationFire,
  rotationAdvice,
  splitByAge,
  yearsSince,
} from '../../application/rules/wildfire.js';
import { HLS_FIRST_DAY } from '../../application/fireData.js';
import {
  ctxKey,
  fireParams,
  fireSubject,
  severityKey,
  shapeKey,
  tracedSections,
} from '../../application/fireController.js';
import { FIRE_EXAMPLE } from '../../data/reference/fireExample.js';
import { appHeader, pageTitle } from '../ui/layout.js';
import { icon } from '../ui/icons.js';
import { loading } from '../ui/widgets.js';
import { L, destroyMap, ensureMap, mapSlot } from '../ui/leafletMap.js';

const KEY = 'feux';
const MAX_LISTED = 25;
const DAY_MS = 86_400_000;

const FLAME = 'M12 22c4 0 7-3 7-7 0-3-2-6-4-8 0 2-1 4-3 4 0-3-1-6-4-9 0 4-5 7-5 13 0 4 4 7 9 7Z';

/* ---------- Formatting ---------- */

const ha = (n) =>
  typeof n !== 'number'
    ? ''
    : n < 10
      ? `${n.toFixed(1).replace('.', ',')} ha`
      : `${Math.round(n).toLocaleString('fr-CA')} ha`;
const TONE_PILL = { ok: 'pill--ok', info: 'pill--info', warn: 'pill--warn', bad: 'pill--bad' };
const sectionNames = (ids) =>
  ids.length === 1 ? `Section ${ids[0]}` : `Sections ${ids.join(', ')}`;

function severityBadge(sev) {
  if (!sev) return html`<span class="muted small">—</span>`;
  const glyph = sev.level === 0 ? (sev.id === 'repousse' ? '↑' : '✓') : '⚠';
  return html`<span class="sev sev--${sev.id}">${glyph} ${sev.label}</span>`;
}

/* ---------- Derived data shared by render and actions ---------- */

function pageData(state, app) {
  const subject = fireSubject(state);
  const example = subject.id === 'exemple';
  const params = fireParams(state);
  const ctx = app.fireContext(state);
  const events = ctx?.data?.events ?? [];
  const sel = app.selectedFireEvent(state);
  const sk = shapeKey(subject);
  const crops = state.fire.crops[sk] ?? null;
  const soil = state.fire.soil[sk] ?? null;
  const sev = sel?.day ? (state.fire.severity[severityKey(subject, sel)] ?? null) : null;
  const { recent, archived } = splitByAge(events);
  // The example is a 2023 fire: its archives are the point, so they stay open.
  const showArchive = example || state.ui.fire.showArchive;
  // Smoke warnings only for big fires of the last 12 months (all fires in the example).
  const veg = (example ? events : recent.filter(isMajorFire)).filter(isVegetationFire);
  const nearestKm = veg.length ? Math.min(...veg.map((e) => e.km)) : null;
  const w = state.weather;
  const rain7 =
    !example && w.data?.daily ? w.data.daily.reduce((a, d) => a + (d.rain ?? 0), 0) : null;
  // Risk right now (only for the user's farm: the example is a past fire).
  const status = !example && ctx?.data ? fireStatus(events, ctx.data.danger) : null;
  return {
    subject,
    example,
    status,
    params,
    ctx,
    events,
    recent,
    archived,
    showArchive,
    sel,
    crops,
    soil,
    sev,
    nearestKm,
    rain7,
  };
}

/** Effect on one section, from everything known about it. */
function sectionAssessment(d, section) {
  const history = d.crops?.data?.[section.id];
  const burnt = burntYears(history);
  const measured = d.sev?.status === 'ready' ? d.sev.data.sections[section.id] : null;
  const hitBySel = !!d.sel && d.sel.sections.includes(section.id) && isVegetationFire(d.sel);
  const burntYear = d.sel ? burnt.find((y) => y === d.sel.year) : burnt[burnt.length - 1];
  const day = d.sel?.day ?? (burntYear ? `${burntYear}-07-01` : null);
  return assessSection({
    severity: measured?.severity ?? null,
    burnt: !!burntYear,
    hotspots: hitBySel,
    soil: d.soil?.data?.[section.id] ?? null,
    rain7: d.rain7,
    nearestKm: d.nearestKm,
    ageYears: d.example ? 0 : yearsSince(day),
  });
}

/* ---------- Blocks ---------- */

function subjectSwitch(example) {
  return html`<div class="segmented segmented--inline" role="group" aria-label="Ferme analysée">
    ${[
      ['farm', 'Ma ferme'],
      ['exemple', 'Exemple réel'],
    ].map(
      ([id, label]) =>
        html`<button
          type="button"
          class="${(id === 'exemple') === example ? 'is-on' : ''}"
          data-action="fire-subject"
          data-s="${id}"
          aria-pressed="${String((id === 'exemple') === example)}"
        >
          ${label}
        </button>`,
    )}
  </div>`;
}

function exampleNote(d) {
  if (!d.example) return '';
  return html`<div class="card card--soft row-start gap-sm">
    <span class="info-dot">i</span>
    <p class="small">
      <strong>Un vrai feu, pas une simulation.</strong> En mai 2023, près de Melfort (Saskatchewan),
      un feu a brûlé 406 ha de terres agricoles. La section A est dans la zone brûlée, la section B
      juste à côté. Votre ferme n’est pas modifiée.
    </p>
  </div>`;
}

/** One line: is there a risk right now? */
function statusCard(d) {
  if (!d.status) return '';
  const { danger } = d.ctx.data;
  const st = d.status;
  if (st.tone === 'calm') {
    return html`<div class="card row-wrap align-center gap-sm">
      <strong class="text-good">✓ ${st.title}</strong>
      ${danger ? html`<span class="muted small">Danger d’incendie aujourd’hui : ${danger.label.toLowerCase()}</span>` : ''}
    </div>`;
  }
  const alert = st.tone === 'alert';
  return html`<div
    class="alert ${alert ? 'alert--bad' : 'alert--warn'}"
    role="${alert ? 'alert' : 'status'}"
  >
    <span aria-hidden="true">⚠</span><span><strong>${st.title}.</strong> ${st.text}</span>
  </div>`;
}

/* ---------- Active fire: what to do on each section (alertAdvice) ---------- */

const FUEL_WORDS = { faible: 'brûle mal', moyen: 'peut brûler', eleve: 'brûle vite' };
const COVER_WHY = {
  seigle:
    'Le seigle reverdit tôt au printemps : moins de chaume sec pendant la saison des feux, et ses racines tiennent le sol si un feu passe.',
};
const KEEP_TEXT = {
  luzerne: 'La luzerne reste verte tout l’été : un bon coupe-feu de ce côté, gardez-la.',
};
/** Seeds missing from the reserve, in words (empty when none). */
const missingText = (ids) =>
  ids.length
    ? ` (${ids.map((id) => nameOf(id).toLowerCase()).join(', ')} : pas dans votre réserve de semences)`
    : '';

/**
 * The fire the advice is about: the alert of fireStatus on the user's farm,
 * or, in the example, the chosen fire as seen on its first day.
 */
function alertFire(d) {
  if (d.status?.tone === 'alert') return { e: d.status.event, now: Date.now() };
  const e = d.sel;
  if (d.example && e?.day && isVegetationFire(e) && isMajorFire(e)) {
    return { e, now: Date.parse(e.day) };
  }
  return null;
}

function alertChange(d, r) {
  if (r.keep) return html`<p class="small text-good">✓ ${KEEP_TEXT[r.keep]}</p>`;
  const c = r.change;
  if (!c) return '';
  const cover = c.changes[0].to;
  return html`<div class="card card--tint stack-xs">
    <strong class="small">Couvert d’hiver proposé</strong>
    <ul class="fire-list small">
      <li>
        ${nameOf(cover)} d’automne après la récolte :
        ${nameOf(c.crop).toLowerCase()}${missingText(c.missingSeeds)}
      </li>
    </ul>
    <p class="muted small">${COVER_WHY[cover]}</p>
    ${
      d.example
        ? ''
        : html`<div class="row-wrap gap-sm">
            <a class="btn btn--secondary btn--sm" href="#/section/${r.id}/plan">Voir mon plan</a>
          </div>`
    }
  </div>`;
}

function alertRow(d, r) {
  const [tone, label] = r.onFire
    ? ['pill--bad', '⚠ Feu sur la section']
    : r.front
      ? ['pill--warn', 'Côté feu']
      : ['pill--neutral', 'Plus loin'];
  const inField =
    r.crop && r.fuel
      ? `Maintenant : ${nameOf(r.crop).toLowerCase()}, ${r.fuel.state} (${FUEL_WORDS[r.fuel.level]})`
      : '';
  return html`<li class="card stack-sm fire-section">
    <div class="row-between">
      <span class="row gap-sm"
        ><span class="section-badge is-dark">${r.id}</span><strong>Section ${r.id}</strong>${
          r.onFire
            ? ''
            : html`<span class="muted small"
                >${r.km < 0.05 ? 'en bordure du feu' : `${fmtKm(r.km)} du feu`}</span
              >`
        }</span
      >
      <span class="pill ${tone}">${label}</span>
    </div>
    ${inField ? html`<span class="muted small">${inField}</span>` : ''}
    <ul class="fire-list small">
      ${r.tips.map((t) => html`<li>${t}</li>`)}
    </ul>
    ${alertChange(d, r)}
  </li>`;
}

/** Shown while a big fire burns within the radius (and on the example's fire). */
function alertCard(d, state) {
  const f = alertFire(d);
  if (!f) return '';
  const advice = alertAdvice(f.e, tracedSections(d.subject), {
    now: f.now,
    seeds: d.example ? null : getSeeds(state.farm),
  });
  const title = d.example
    ? 'Pendant le feu, l’appli aurait conseillé'
    : 'Que faire sur vos sections cette semaine';
  const lead = d.example
    ? `${eventTitle(f.e)} · ${fmtPeriod(f.e.day, f.e.lastDay)} · les sections les plus proches du feu d’abord`
    : `${eventTitle(f.e)} ${fmtKm(f.e.km)} · les sections les plus proches du feu d’abord`;
  const unknownCrop = !d.example && advice.sections.some((r) => !r.crop && !r.onFire);
  return html`<section class="stack-sm" aria-label="Que faire pendant le feu">
    <div class="stack-0">
      <h2 class="h2 h2--lg">${title}</h2>
      <span class="muted small">${lead}</span>
    </div>
    ${
      advice.sections.length
        ? html`<ol class="grid fire-sections fire-advice">
            ${advice.sections.map((r) => alertRow(d, r))}
          </ol>`
        : html`<p class="muted">
            Tracez vos sections pour des conseils section par section.
            <a href="#/tracer">Tracer mes sections</a>
          </p>`
    }
    <div class="card card--soft stack-xs">
      <strong class="small">Pour toute la ferme</strong>
      <ul class="fire-list small">
        ${advice.general.map((t) => html`<li>${t}</li>`)}
      </ul>
    </div>
    ${
      unknownCrop
        ? html`<p class="muted small">
            Indiquez la culture en place de chaque section pour des conseils plus précis.
            <a href="#/cultures">Mes cultures</a>
          </p>`
        : ''
    }
  </section>`;
}

function eventItem(e, selected, archived = false) {
  const facts = [fmtPeriod(e.day, e.lastDay), fmtKm(e.km), e.kind !== 'hotspots' ? ha(e.ha) : ''];
  const warn = !archived && isVegetationFire(e);
  return html`<li>
    <button
      type="button"
      class="fire-event ${selected ? 'is-on' : ''}"
      data-action="fire-select"
      data-id="${e.id}"
      aria-pressed="${String(selected)}"
    >
      <span
        class="fire-event__dot fire-event__dot--${e.kind}${e.active ? ' is-active' : ''}"
        aria-hidden="true"
      ></span>
      <span class="stack-0 grow">
        <strong class="small">${eventTitle(e)}</strong>
        <span class="muted small">${facts.filter(Boolean).join(' · ')}</span>
      </span>
      ${
        e.sections.length
          ? html`<span class="pill ${warn ? 'pill--bad' : 'pill--neutral'}"
              >${warn ? '⚠ ' : ''}${plural(e.sections.length, 'section', 'sections')}
              ${e.sections.join(', ')}</span
            >`
          : ''
      }
    </button>
  </li>`;
}

function eventsCard(d, state) {
  const ctx = d.ctx;
  const head = html`<div class="stack-0">
    <h2 class="h2">Feux des 12 derniers mois</h2>
    <span class="muted small">À moins de ${d.params.radiusKm} km</span>
  </div>`;
  if (!ctx || ctx.status === 'loading') {
    return html`<section class="card stack-sm fire-events">
      ${head}${loading('Recherche des feux autour de la ferme…')}
    </section>`;
  }
  if (ctx.status === 'error') {
    return html`<section class="card stack-sm fire-events">
      ${head}
      <div class="alert alert--bad" role="alert">
        <span aria-hidden="true">⚠</span><span>${ctx.error}</span
        ><button type="button" class="btn btn--sm btn--secondary" data-action="fire-retry">
          Réessayer
        </button>
      </div>
    </section>`;
  }
  const sel = state.ui.fire.eventId;
  const list = d.recent.slice(0, MAX_LISTED);
  const more = d.recent.length - list.length;
  const old = d.archived.slice(0, MAX_LISTED);
  return html`<section class="card stack-sm fire-events">
    ${head}
    <div class="fire-events__scroll stack-sm">
      ${
        list.length
          ? html`<ol class="fire-events__list">
              ${list.map((e) => eventItem(e, e.id === sel))}
            </ol>`
          : html`<p class="muted">✓ Aucun feu cette année.</p>`
      }
      ${more > 0 ? html`<p class="muted small">Et ${plural(more, 'autre feu', 'autres feux')} plus loin.</p>` : ''}
      ${
        d.archived.length
          ? html`<button
                type="button"
                class="fire-archive-toggle"
                data-action="fire-archive"
                aria-expanded="${String(d.showArchive)}"
                aria-controls="fire-archive"
              >
                <span class="stack-0 grow"
                  ><strong class="small">Archives</strong
                  ><span class="muted small"
                    >${plural(d.archived.length, 'feu plus ancien', 'feux plus anciens')}</span
                  ></span
                ><span aria-hidden="true">${d.showArchive ? '−' : '+'}</span>
              </button>
              ${
                d.showArchive
                  ? html`<ol class="fire-events__list fire-events__list--archive" id="fire-archive">
                        ${old.map((e) => eventItem(e, e.id === sel, true))}
                      </ol>
                      ${d.archived.length > old.length ? html`<p class="muted small">Et ${d.archived.length - old.length} autres, plus loin.</p>` : ''}`
                  : ''
              }`
          : ''
      }
    </div>
    ${ctx.data.warnings.map((w) => html`<p class="small text-warn">⚠ ${w}</p>`)}
  </section>`;
}

function mapCard(d) {
  const legend = [
    ['hs-active', 'Cette semaine'],
    ['hs-recent', '12 derniers mois'],
    ...(d.showArchive ? [['hs-old', 'Plus ancien']] : []),
    ['burn', 'Zone brûlée'],
    ['farm', 'Vos sections'],
  ];
  return html`<section class="card card--flush fire-map-card" aria-label="Carte des feux">
    <div class="fire-map">${mapSlot(KEY, 'Carte des feux autour de la ferme')}</div>
    <ul class="fire-legend">
      ${legend.map(([id, label]) => html`<li><span class="fire-legend__swatch fire-legend__swatch--${id}" aria-hidden="true"></span>${label}</li>`)}
    </ul>
  </section>`;
}

/** Shown once a fire is chosen: did it burn the sections? */
function severityCard(d) {
  if (!d.sel) return '';
  const e = d.sel;
  const traced = tracedSections(d.subject);
  const head = html`<div class="stack-0">
    <h2 class="h2">Vos sections ont-elles brûlé ?</h2>
    <span class="muted small">${eventTitle(e)} · ${fmtDay(e.day)} · ${fmtKm(e.km)}</span>
  </div>`;
  const note = isVegetationFire(e)
    ? ''
    : html`<p class="small text-warn">
        ⚠ Point chaud en ${fuelInfo(e.fuel).label.toLowerCase()} : sans doute un bâtiment, une usine
        ou une torchère, pas un feu de champ.
      </p>`;
  let body;
  if (!traced.length) {
    body = html`<p class="muted">
      Tracez vos sections pour le savoir. <a href="#/tracer">Tracer mes sections</a>
    </p>`;
  } else if (!e.day || e.day < HLS_FIRST_DAY) {
    body = html`<p class="muted">
      Les images satellites utilisées commencent en 2020 : ce feu ne peut pas être mesuré.
    </p>`;
  } else if (!d.sev) {
    body = html`<button type="button" class="btn btn--primary" data-action="fire-measure">
      Mesurer le brûlage sur mes sections
    </button>`;
  } else if (d.sev.status === 'loading') {
    body = loading('Lecture des images satellites avant et après le feu…');
  } else if (d.sev.status === 'error') {
    body = html`<div class="alert alert--bad" role="alert">
      <span aria-hidden="true">⚠</span><span>${d.sev.error}</span
      ><button
        type="button"
        class="btn btn--sm btn--secondary"
        data-action="fire-measure"
        data-force="1"
      >
        Réessayer
      </button>
    </div>`;
  } else {
    const r = d.sev.data;
    body = html`<div class="row-wrap gap-md">
        ${traced.map((s) => html`<span class="row gap-xs"><strong>${s.id}</strong>${severityBadge(r.sections[s.id]?.severity)}</span>`)}
      </div>
      ${
        r.gapDays > 60
          ? html`<p class="small text-warn">
              ⚠ Images prises à ${r.gapDays} jours d’écart : résultat moins fiable.
            </p>`
          : ''
      }`;
  }
  return html`<section class="card stack-sm" aria-live="polite">${head}${note}${body}</section>`;
}

/** Options of rotationAdvice: the farmer's seeds and equipment (none for the example). */
const adviceOptions = (d, farm) =>
  d.example ? {} : { seeds: getSeeds(farm), missingEquipment: farm.farm.missingEquipment ?? [] };

function adviceBlock(d, section, a, farm) {
  const adv = rotationAdvice(section, a.level, adviceOptions(d, farm));
  if (!adv) return '';
  return html`<div class="card card--tint stack-xs">
    <strong class="small">Prochaine culture de la rotation</strong>
    <ul class="fire-list small">
      ${adv.changes.map(
        (c) => html`<li>${nameOf(c.from)} → ${nameOf(c.to)}${missingText(adv.missingSeeds)}</li>`,
      )}
    </ul>
    ${
      d.example
        ? ''
        : html`<div class="row-wrap gap-sm">
            <button
              type="button"
              class="btn btn--dark btn--sm"
              data-action="fire-apply"
              data-id="${section.id}"
              data-level="${a.level}"
            >
              Appliquer et voir le plan
            </button>
            <a class="btn btn--secondary btn--sm" href="#/section/${section.id}/parcelle"
              >Ma parcelle</a
            >
          </div>`
    }
  </div>`;
}

function sectionCard(d, s, a, farm) {
  const burnt = burntYears(d.crops?.data?.[s.id]);
  return html`<article class="card stack-sm fire-section">
    <div class="row-between">
      <span class="row gap-sm"
        ><span class="section-badge is-dark">${s.id}</span><strong>Section ${s.id}</strong></span
      >
      <span class="pill ${TONE_PILL[a.tone]}">⚠ ${a.label}</span>
    </div>
    ${burnt.length ? html`<span class="muted small">Vue brûlée par l’inventaire des cultures en ${burnt.join(', ')}</span>` : ''}
    <div class="stack-xs">
      <strong class="small">À faire</strong>
      <ul class="fire-list small">
        ${a.actions.map((t) => html`<li>${t}</li>`)}
      </ul>
    </div>
    ${adviceBlock(d, s, a, farm)}
    <details class="fire-why small">
      <summary>Pourquoi ?</summary>
      <ul class="fire-list">
        ${a.impacts.map((t) => html`<li>${t}</li>`)}
      </ul>
    </details>
  </article>`;
}

/** Sections hit get a card; the others share one calm line. */
function sectionCards(d, state) {
  const all = d.subject.sections;
  if (!all.length || !d.ctx?.data) return '';
  const traced = tracedSections(d.subject);
  const untraced = all.filter((s) => !traced.includes(s)).map((s) => s.id);
  const rows = traced.map((s) => ({ s, a: sectionAssessment(d, s) }));
  const hit = rows.filter((r) => r.a.level > 0);
  const calm = rows.filter((r) => r.a.level === 0);
  const smoke =
    typeof d.nearestKm === 'number' && d.nearestKm <= 10 && calm.some((r) => r.a.burnLevel === 0);
  return html`<section class="stack-sm" aria-label="Effet sur vos sections">
    <h2 class="h2 h2--lg">Effet sur vos sections</h2>
    ${
      hit.length
        ? html`<div class="grid fire-sections">
            ${hit.map(({ s, a }) => sectionCard(d, s, a, state.farm))}
          </div>`
        : ''
    }
    ${calm.length ? html`<p class="text-good strong">✓ ${sectionNames(calm.map((r) => r.s.id))} : aucun dommage.</p>` : ''}
    ${
      smoke
        ? html`<p class="small">
            Un feu est passé à moins de 10 km : après un épisode de fumée, vérifiez les feuilles et
            les fourrages avant de les récolter.
          </p>`
        : ''
    }
    ${
      untraced.length
        ? html`<p class="muted small">
            ${sectionNames(untraced)} pas tracée${untraced.length > 1 ? 's' : ''} sur la carte.
            <a href="#/tracer">Tracer</a>
          </p>`
        : ''
    }
  </section>`;
}

/* ---------- Map ---------- */

const COLORS = {
  hsActive: '#D55E00',
  hsRecent: '#E69F00',
  hsOld: '#8C7A5B',
  burn: '#D55E00',
  perimeter: '#B8002E',
  selected: '#18211B',
  farm: '#FFFFFF',
};
const SEV_FILL = {
  repousse: '#0072B2',
  intact: '#0072B2',
  faible: '#E69F00',
  moderee: '#D55E00',
  elevee: '#9A3D00',
  'tres-elevee': '#5C2400',
};

let layers = null;
let lastSig = null;
let lastView = null;
let lastFocus = null;

function hotspotColor(day, now) {
  const age = now - Date.parse(day);
  if (age <= 7 * DAY_MS) return COLORS.hsActive;
  if (age <= 365 * DAY_MS) return COLORS.hsRecent;
  return COLORS.hsOld;
}

function drawLayers(app, map) {
  const s = app.state;
  const d = pageData(s, app);
  const now = Date.now();
  layers.clearLayers();
  const select = (id) => () => app.selectFireEvent(id);
  const tip = (e) =>
    escapeHtml(`${eventTitle(e)} · ${fmtPeriod(e.day, e.lastDay)} · ${fmtKm(e.km)}`);
  const center = farmCenter(d.subject);
  const box = farmBox(d.subject);

  if (center) {
    const half = box ? Math.hypot(box[1][0] - box[0][0], box[1][1] - box[0][1]) * 55_660 : 0;
    L.circle(center, {
      radius: d.params.radiusKm * 1000 + half,
      color: '#FFFFFF',
      weight: 1.5,
      dashArray: '6 6',
      fill: false,
      interactive: false,
    }).addTo(layers);
  }

  const shown = d.showArchive
    ? d.events
    : [...d.recent, ...d.archived.filter((e) => e.id === s.ui.fire.eventId)];
  for (const e of shown) {
    const on = e.id === s.ui.fire.eventId;
    if (e.kind === 'burn' || e.kind === 'perimeter') {
      const color = e.kind === 'burn' ? COLORS.burn : COLORS.perimeter;
      L.polygon(e.rings, {
        color: on ? COLORS.selected : color,
        weight: on ? 3 : 1.5,
        fillColor: color,
        fillOpacity: on ? 0.45 : 0.28,
        dashArray: e.kind === 'perimeter' ? '4 4' : null,
      })
        .bindTooltip(tip(e), { sticky: true })
        .on('click', select(e.id))
        .addTo(layers);
    } else {
      for (const [lat, lon] of e.points) {
        L.circleMarker([lat, lon], {
          radius: on ? 8 : 5,
          color: on ? COLORS.selected : '#FFFFFF',
          weight: on ? 3 : 1,
          fillColor: hotspotColor(e.lastDay ?? e.day, now),
          fillOpacity: 0.95,
        })
          .bindTooltip(tip(e))
          .on('click', select(e.id))
          .addTo(layers);
      }
    }
  }

  if (d.subject.boundary?.length >= 3) {
    L.polygon(d.subject.boundary, {
      color: COLORS.farm,
      weight: 2,
      dashArray: '8 6',
      fill: false,
      interactive: false,
    }).addTo(layers);
  }
  const measured = d.sev?.status === 'ready' ? d.sev.data.sections : {};
  for (const sec of tracedSections(d.subject)) {
    const sev = measured[sec.id]?.severity;
    L.polygon(sec.polygon, {
      color: COLORS.farm,
      weight: 2,
      fillColor: sev ? SEV_FILL[sev.id] : '#FFFFFF',
      fillOpacity: sev ? 0.55 : 0.12,
    })
      .bindTooltip(escapeHtml(sev ? `${sec.id} · ${sev.label}` : sec.id), {
        permanent: true,
        direction: 'center',
        className: 'fire-sec-label',
      })
      .addTo(layers);
  }

  // Frame the search area when the farm changes, the fire when one is chosen.
  const view = `${ctxKey(d.subject, d.params)}`;
  if (view !== lastView && center) {
    lastView = view;
    const r = d.params.radiusKm * 1000;
    map.fitBounds(L.latLng(center).toBounds(2 * r), { animate: false });
  }
  const focus = s.ui.fire.eventId;
  if (focus && focus !== lastFocus && d.sel && box) {
    const pts = d.sel.rings ? d.sel.rings.flat() : d.sel.points;
    map.fitBounds(L.latLngBounds([...box, ...pts]).pad(0.25), { maxZoom: 15 });
  }
  lastFocus = focus;
}

/* ---------- Screen ---------- */

export default {
  title: 'Feux près de la ferme',
  rota: 'feux',
  onEnter(app) {
    app.loadFirePage();
    if (app.state.ui.fire.subject === 'farm') app.loadWeather();
  },
  mount(app) {
    const s = app.state;
    const center = farmCenter(fireSubject(s));
    if (!center) return;
    const { map, created } = ensureMap(KEY, { center, zoom: 11 });
    if (created) layers = L.layerGroup().addTo(map);
    const ctx = app.fireContext(s);
    const d = pageData(s, app);
    const sig = [
      ctxKey(d.subject, d.params),
      ctx?.status,
      ctx?.at,
      s.ui.fire.eventId,
      d.showArchive,
      d.sev?.status,
      shapeKey(d.subject),
    ].join('|');
    if (sig === lastSig) return;
    lastSig = sig;
    drawLayers(app, map);
  },
  unmount() {
    destroyMap(KEY);
    layers = null;
    lastSig = null;
    lastView = null;
    lastFocus = null;
  },
  render(state, _params, app) {
    const d = pageData(state, app);
    const noPlace = !farmCenter(d.subject);
    const lead = d.example
      ? `${FIRE_EXAMPLE.location.label} · un feu agricole réel, vu par les satellites.`
      : `Les feux à moins de ${d.params.radiusKm} km de votre ferme et leur effet sur vos sections.`;
    return html`${appHeader(state, 'tableau')}
      <main class="page stack-lg" id="main">
        <a class="back-link" href="#/tableau">← Tableau de bord</a>
        ${pageTitle(
          html`<span class="row gap-sm">${icon(FLAME, { size: 28 })}Feux près de la ferme</span>`,
          lead,
          subjectSwitch(d.example),
        )}
        ${exampleNote(d)}
        ${
          noPlace
            ? html`<div class="alert alert--warn">
                <span aria-hidden="true">⚠</span><span>Placez d’abord la ferme sur la carte.</span
                ><a class="btn btn--sm btn--secondary" href="#/localisation">Situer la ferme</a>
              </div>`
            : html`${statusCard(d)} ${d.example ? '' : alertCard(d, state)}
                <div class="fire-top">${mapCard(d)} ${eventsCard(d, state)}</div>
                ${d.example ? alertCard(d, state) : ''} ${severityCard(d)} ${sectionCards(d, state)}`
        }
        <p class="small muted">
          Satellites de la NASA (MODIS, VIIRS, HLS), Ressources naturelles Canada, Agriculture
          Canada, SoilGrids. Une récolte ou un labour peut ressembler à un brûlage : vérifiez sur le
          terrain avant de changer la rotation.
          <a class="strong" href="#/sources">Sources →</a>
        </p>
      </main>`;
  },
  actions: {
    'fire-subject': (app, el) => {
      const which = el.dataset.s === 'exemple' ? 'exemple' : 'farm';
      if (app.state.ui.fire.subject === which) return;
      app.update((s) => {
        s.ui.fire.subject = which;
        s.ui.fire.eventId = null;
      });
      app.loadFirePage();
      if (which === 'farm') app.loadWeather();
    },
    'fire-select': (app, el) => app.selectFireEvent(el.dataset.id),
    'fire-archive': (app) =>
      app.update((s) => {
        s.ui.fire.showArchive = !s.ui.fire.showArchive;
      }),
    'fire-measure': (app, el) => app.measureFire({ force: !!el.dataset.force }),
    'fire-retry': (app) => app.loadFirePage({ force: true }),
    'fire-apply': (app, el) => {
      const id = el.dataset.id;
      const sec = app.section(id);
      if (!sec) return;
      const farm = app.state.farm;
      const adv = rotationAdvice(sec, Number(el.dataset.level), {
        seeds: getSeeds(farm),
        missingEquipment: farm.farm.missingEquipment ?? [],
      });
      if (!adv) return;
      app.updateSection(id, (s) => {
        s.currentRotation = adv.rotation;
      });
      app.go(`#/section/${id}/plan`);
    },
  },
};
