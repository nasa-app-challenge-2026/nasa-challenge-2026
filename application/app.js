/**
 * Application controller: state, engine calls, network, navigation. Screens
 * never call the engine or the network directly; they go through these helpers.
 *
 * The engine (back end) is handed in by frontend/main.js: this layer only knows
 * its interface (planFarm, see backend/contract/types.js), never which engine runs.
 */
import { createStore } from './state/store.js';
import { initialState, persisted } from './state/initialState.js';
import { coordsLabel, sameCoord } from './rules/geo.js';
import { sectionInputProblems } from './rules/sectionInputs.js';
import { loadSaved, save } from '../data/access/storage.js';
import { fetchWeather, weatherKey } from '../data/access/weather.js';
import { geocode, reverseGeocode } from '../data/access/geocode.js';
import { fireController } from './fireController.js';

const WEATHER_TTL_MS = 30 * 60 * 1000;
/** Wait this long after the last change before planning again. */
const PLAN_DEBOUNCE_MS = 250;

export function createApp({ engine, storage = globalThis.localStorage }) {
  const store = createStore(initialState(engine.name, loadSaved(storage)));
  store.subscribe((s) => save(storage, persisted(s)));

  let timer = null;
  let seq = 0;

  const app = {
    store,
    engine,
    get state() {
      return store.get();
    },
    update: (fn) => store.update(fn),
    go(path) {
      if (location.hash !== path) location.hash = path;
    },

    section(id) {
      return store.get().farm.sections.find((s) => s.id === id);
    },
    sectionPlan(id) {
      return store.get().plan.data?.sections.find((s) => s.id === id) ?? null;
    },

    /** Change the farm, then plan again (debounced). */
    updateFarm(fn) {
      store.update((s) => fn(s.farm, s));
      app.refreshPlan();
    },

    /** Change one section of the farm. */
    updateSection(id, fn) {
      app.updateFarm((farm, s) => {
        const section = farm.sections.find((x) => x.id === id);
        if (section) fn(section, farm, s);
      });
    },

    refreshPlan() {
      clearTimeout(timer);
      timer = setTimeout(plan, PLAN_DEBOUNCE_MS);
    },

    /** Weather at the farm (Open-Meteo), cached 30 min per location. */
    async loadWeather({ force = false } = {}) {
      const { lat, lon } = store.get().farm.farm.location ?? {};
      if (typeof lat !== 'number' || typeof lon !== 'number') return;
      const key = weatherKey(lat, lon);
      const cur = store.get().weather;
      const fresh = cur.key === key && cur.data && Date.now() - cur.data.fetchedAt < WEATHER_TTL_MS;
      if (!force && (fresh || (cur.status === 'loading' && cur.key === key))) return;
      store.update((s) => {
        s.weather = {
          status: 'loading',
          data: cur.key === key ? cur.data : null,
          error: null,
          key,
        };
      });
      try {
        const data = await fetchWeather(lat, lon);
        store.update((s) => {
          if (s.weather.key === key) s.weather = { status: 'ready', data, error: null, key };
        });
      } catch (err) {
        store.update((s) => {
          if (s.weather.key === key)
            s.weather = { status: 'error', data: null, error: err.message, key };
        });
      }
    },

    /** Address search (Nominatim). Status and results go to `ui.geo`; returns the results. */
    async searchPlaces(query) {
      store.update((s) => {
        s.ui.geo = { query, results: s.ui.geo.results, status: 'loading', error: null };
      });
      try {
        const results = await geocode(query);
        store.update((s) => {
          s.ui.geo = { query, results, status: 'ready', error: null };
        });
        return results;
      } catch (err) {
        store.update((s) => {
          s.ui.geo = { ...s.ui.geo, status: 'error', error: err.message };
        });
        return [];
      }
    },

    /**
     * Move the farm to a point. Without a label, the coordinates are shown
     * until a readable address is found (Nominatim), unless the farm moved again.
     */
    setFarmLocation(lat, lon, label) {
      app.updateFarm((farm) => {
        farm.farm.location = { lat, lon, label: label ?? coordsLabel(lat, lon) };
      });
      if (label) return;
      reverseGeocode(lat, lon).then((found) => {
        if (!found) return;
        store.update((s) => {
          const loc = s.farm.farm.location;
          if (sameCoord(loc.lat, lat) && sameCoord(loc.lon, lon)) loc.label = found;
        });
      });
    },
  };

  /** Wildfires near the farm and their effect on the sections (see application/fireController.js). */
  Object.assign(app, fireController(store));

  /** Ask the engine for the plan of every section (latest request wins). */
  async function plan() {
    const farm = store.get().farm;
    const problems = farm.sections.flatMap((s) =>
      sectionInputProblems(s).map((p) => `Section ${s.id} : ${p}`),
    );
    if (problems.length) {
      store.update((s) => {
        s.plan = { ...s.plan, status: 'incomplete', error: problems.join(' ') };
      });
      return;
    }
    const mine = ++seq;
    store.update((s) => {
      s.plan.status = s.plan.data ? 'refreshing' : 'loading';
      s.plan.error = null;
    });
    try {
      const data = await engine.planFarm(farm);
      if (mine !== seq) return;
      store.update((s) => {
        s.plan = { status: 'ready', data, error: null };
      });
    } catch (err) {
      if (mine !== seq) return;
      store.update((s) => {
        s.plan.status = 'error';
        s.plan.error = err.message;
      });
    }
  }

  return app;
}
