/**
 * Application controller: state, engine calls, network, navigation. Screens
 * never call the engine or the network directly; they go through these helpers.
 *
 * The engine (back end) is handed in by frontend/main.js: this layer only knows
 * its interface (planFarm, see backend/contract/types.js), never which engine runs.
 *
 * A plan takes the server several seconds, so it is asked for as rarely as possible, without
 * ever showing a plan that is not the one of the farm on screen:
 *   - the last plan is kept in the browser with the farm it was computed for: at the next visit
 *     it shows at once, while the server computes it again;
 *   - the plans of this visit are kept by farm: going back to a setting already planned (a
 *     priority moved up, then down) shows its plan without asking the server again.
 */
import { createStore } from './state/store.js';
import { DEMO_FARM } from '../data/reference/demoFarm.js';
import demoPlan from '../data/reference/demoPlan.json';
import { initialState, persisted } from './state/initialState.js';
import { coordsLabel, sameCoord } from './rules/geo.js';
import { sectionInputProblems } from './rules/sectionInputs.js';
import { loadPlan, loadSaved, save, savePlan } from '../data/access/storage.js';
import { fetchWeather, weatherKey } from '../data/access/weather.js';
import { geocode, reverseGeocode } from '../data/access/geocode.js';

const WEATHER_TTL_MS = 30 * 60 * 1000;
/** Wait this long after the last change before planning again. */
const PLAN_DEBOUNCE_MS = 250;
/** Plans of this visit kept in memory, one per farm planned. */
const MAX_RECENT_PLANS = 8;

/** What a plan depends on: the whole farm, as it is sent to the engine. */
const planKey = (farm) => JSON.stringify(farm);

export function createApp({ engine, storage = globalThis.localStorage }) {
  const store = createStore(initialState(engine.name, loadSaved(storage)));
  store.subscribe((s) => {
    if (!s.ui.demo) save(storage, persisted(s));
  });
  let realSnapshot = null;

  let timer = null;
  let seq = 0;
  const recentPlans = new Map();

  const lastPlan = loadPlan(storage);
  if (lastPlan?.key === planKey(store.get().farm))
    store.update((s) => {
      s.plan = { status: 'ready', data: lastPlan.data, error: null };
    });

  function keepPlan(key, data) {
    recentPlans.delete(key);
    recentPlans.set(key, data);
    while (recentPlans.size > MAX_RECENT_PLANS) recentPlans.delete(recentPlans.keys().next().value);
    savePlan(storage, key, data);
  }

  const app = {
    store,
    engine,
    get state() {
      return store.get();
    },
    update: (fn) => store.update(fn),
    enterDemo() {
      if (store.get().ui.demo) return;
      clearTimeout(timer);
      seq++;
      realSnapshot = structuredClone(store.get());
      store.update((s) => {
        s.ui.demo = true;
        s.ui.route = { name: 'tableau', params: {} };
        s.farm = structuredClone(DEMO_FARM);
        s.plan = { status: 'ready', data: structuredClone(demoPlan), error: null };
        s.weather = { status: 'idle', data: null, error: null, key: null };
        s.ui.year = null;
        s.ui.cycle = 1;
        s.ui.selectedSection = 'A';
      });
      app.go('#/tableau');
    },
    exitDemo() {
      if (!realSnapshot) return;
      const language = store.get().prefs.language;
      store.update((s) => {
        Object.assign(s, realSnapshot);
        s.ui.demo = false;
        s.ui.route = { name: 'tableau', params: {} };
        s.prefs.language = language;
      });
      realSnapshot = null;
      app.go('#/tableau');
      app.refreshPlan();
      app.loadWeather();
    },
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
      if (store.get().ui.demo) return;
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
      if (store.get().ui.demo) return;
      clearTimeout(timer);
      timer = setTimeout(plan, PLAN_DEBOUNCE_MS);
    },

    /** Weather at the farm (Open-Meteo), cached 30 min per location. */
    async loadWeather({ force = false } = {}) {
      if (store.get().ui.demo) return;
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
          if (!s.ui.demo && s.weather.key === key)
            s.weather = { status: 'ready', data, error: null, key };
        });
      } catch (err) {
        store.update((s) => {
          if (!s.ui.demo && s.weather.key === key)
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

  /** Ask the engine for the plan of every section (latest request wins). */
  async function plan() {
    if (store.get().ui.demo) return;
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
    const key = planKey(farm);
    const known = recentPlans.get(key);
    if (known) {
      store.update((s) => {
        s.plan = { status: 'ready', data: known, error: null };
      });
      return;
    }
    store.update((s) => {
      s.plan.status = s.plan.data ? 'refreshing' : 'loading';
      s.plan.error = null;
    });
    try {
      const data = await engine.planFarm(farm);
      if (mine !== seq) return;
      keepPlan(key, data);
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
