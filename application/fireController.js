/**
 * Fire data in the app state: loading, caching and the selected fire.
 * Merged into the app object by application/app.js, so screens call app.loadFirePage(),
 * app.selectFireEvent(id)… and never fetch by themselves.
 *
 * state.fire holds four caches keyed by what was asked:
 *   ctx       fires and danger around a farm      (subject, centre, radius, years)
 *   crops     crop inventory per section           (subject, section outlines)
 *   soil      SoilGrids per section                 (same key)
 *   severity  dNBR per section for one fire date    (same key + day)
 * Each entry is { status: 'loading' | 'ready' | 'error', data, error, at }.
 */
import { FIRE_EXAMPLE } from '../data/reference/fireExample.js';
import {
  HLS_FIRST_DAY,
  fetchCropHistory,
  fetchFireContext,
  fetchSoils,
  measureSeverity,
} from './fireData.js';
import { isClosed } from './rules/geo.js';
import { burnWindow, farmCenter, isRecent, isVegetationFire } from './rules/wildfire.js';

const TTL_MS = 30 * 60 * 1000;

/** Fixed search around the user's farm, shared by the dashboard block and the fire page. */
export const DASH_FIRE = { which: 'farm', radiusKm: 25, years: 10 };

/** What is analysed: the user's farm, or the real example. */
export function fireSubject(state, which = state.ui.fire.subject) {
  if (which === 'exemple') return FIRE_EXAMPLE;
  const f = state.farm;
  return {
    id: 'farm',
    name: f.farm.name,
    location: f.farm.location,
    boundary: f.farm.boundary,
    sections: f.sections,
  };
}

/** Radius and period: the example has its own, the farm uses the fixed search. */
export function fireParams(state, which = state.ui.fire.subject) {
  if (which === 'exemple') return { radiusKm: FIRE_EXAMPLE.radiusKm, years: FIRE_EXAMPLE.years };
  return { radiusKm: DASH_FIRE.radiusKm, years: DASH_FIRE.years };
}

function hash(text) {
  let h = 0;
  for (let i = 0; i < text.length; i++) h = (Math.imul(31, h) + text.charCodeAt(i)) | 0;
  return (h >>> 0).toString(36);
}

export function ctxKey(subject, { radiusKm, years }) {
  const c = farmCenter(subject);
  return `${subject.id}|${c ? c.map((n) => n.toFixed(3)).join(',') : '-'}|${radiusKm}|${years}`;
}

export const shapeKey = (subject) =>
  `${subject.id}|${hash(JSON.stringify(subject.sections.map((s) => [s.id, s.polygon])))}`;

export const severityKey = (subject, e) => `${shapeKey(subject)}|${burnWindow(e).join('|')}`;

/** Traced sections only (the others have no outline to measure). */
export const tracedSections = (subject) => subject.sections.filter((s) => isClosed(s.polygon));

export function fireController(store) {
  /** Load into state.fire[slice][key] unless a fresh or pending answer is there. */
  async function load(slice, key, fn, { force = false, ttl = TTL_MS, keep = [] } = {}) {
    const cur = store.get().fire[slice][key];
    const fresh = cur?.status === 'ready' && Date.now() - cur.at < ttl;
    if (!force && (cur?.status === 'loading' || fresh)) return;
    store.update((s) => {
      // Only a few entries are kept: the state is copied on every update.
      for (const k of Object.keys(s.fire[slice])) {
        if (k !== key && !keep.includes(k)) delete s.fire[slice][k];
      }
      s.fire[slice][key] = { status: 'loading', data: cur?.data ?? null, error: null, at: 0 };
    });
    try {
      const data = await fn();
      store.update((s) => {
        s.fire[slice][key] = { status: 'ready', data, error: null, at: Date.now() };
      });
    } catch (err) {
      store.update((s) => {
        s.fire[slice][key] = { status: 'error', data: null, error: err.message, at: Date.now() };
      });
    }
  }

  const dashKey = () => ctxKey(fireSubject(store.get(), 'farm'), DASH_FIRE);

  const api = {
    /** Fires around the farm (or the example). `which`/`radiusKm`/`years` override the defaults. */
    async loadFire({ force = false, which, radiusKm, years } = {}) {
      const s = store.get();
      const subject = fireSubject(s, which);
      const params = {
        ...fireParams(s, which),
        ...(radiusKm ? { radiusKm } : {}),
        ...(years ? { years } : {}),
      };
      if (!farmCenter(subject)) return;
      const key = ctxKey(subject, params);
      const pageKey = ctxKey(fireSubject(s), fireParams(s));
      await load('ctx', key, () => fetchFireContext(subject, params), {
        force,
        keep: [pageKey, dashKey()],
      });
    },

    async loadFireCrops({ force = false } = {}) {
      const subject = fireSubject(store.get());
      const traced = tracedSections(subject);
      if (!traced.length) return;
      await load('crops', shapeKey(subject), () => fetchCropHistory(traced), {
        force,
        ttl: Infinity,
      });
    },

    async loadFireSoil({ force = false } = {}) {
      const subject = fireSubject(store.get());
      const traced = tracedSections(subject);
      if (!traced.length) return;
      await load('soil', shapeKey(subject), () => fetchSoils(traced), { force, ttl: Infinity });
    },

    /** Current fire context of the page (or null). */
    fireContext(state = store.get()) {
      return state.fire.ctx[ctxKey(fireSubject(state), fireParams(state))] ?? null;
    },

    selectedFireEvent(state = store.get()) {
      const events = api.fireContext(state)?.data?.events ?? [];
      return events.find((e) => e.id === state.ui.fire.eventId) ?? null;
    },

    /** Measure the burn severity of the sections for the selected fire. */
    async measureFire({ force = false } = {}) {
      const s = store.get();
      const e = api.selectedFireEvent(s);
      if (!e?.day) return;
      const subject = fireSubject(s);
      await load(
        'severity',
        severityKey(subject, e),
        () => {
          const [day, lastDay] = burnWindow(e);
          return measureSeverity(subject.sections, day, { lastDay });
        },
        {
          force,
          ttl: Infinity,
        },
      );
    },

    selectFireEvent(id) {
      store.update((s) => {
        s.ui.fire.eventId = id;
      });
      api.measureFire();
    },

    /**
     * Everything the page needs. Once the fires are known, the first fire that
     * touches a section (and that HLS can see) is selected and measured.
     */
    async loadFirePage({ force = false } = {}) {
      await Promise.all([
        api.loadFire({ force }),
        api.loadFireCrops({ force }),
        api.loadFireSoil({ force }),
      ]);
      const s = store.get();
      const events = api.fireContext(s)?.data?.events ?? [];
      if (!api.selectedFireEvent(s)) {
        // On the user's farm, only a fire of the last 12 months opens by itself:
        // older ones wait in the archives, so the page does not alarm for nothing.
        const example = s.ui.fire.subject === 'exemple';
        const hit = events.find(
          (e) =>
            e.sections.length &&
            isVegetationFire(e) &&
            e.day >= HLS_FIRST_DAY &&
            (example || isRecent(e)),
        );
        if (hit) api.selectFireEvent(hit.id);
      }
    },
  };
  return api;
}
