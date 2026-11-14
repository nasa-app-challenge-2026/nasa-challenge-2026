/**
 * Application controller: state, engine calls, navigation. Screens never call
 * the engine directly; they go through these helpers.
 */
import { createStore } from './state/store.js';
import { initialState, loadSaved, save } from './state/initialState.js';
import { autoStagger, suggestCycleYears, toSlots } from './lib/rotation.js';
import { getSeeds } from './lib/seeds.js';
import { fetchWeather, weatherKey } from './lib/weather.js';
import { fireController } from './fireController.js';

const WEATHER_TTL_MS = 30 * 60 * 1000;

export function createApp({ engine, storage = globalThis.localStorage }) {
  const store = createStore(initialState(engine.name, loadSaved(storage)));
  store.subscribe((s) => save(storage, s));

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

    /** Change the farm, then recompute the plan (debounced). */
    updateFarm(fn) {
      store.update((s) => fn(s.farm, s));
      app.refreshPlan();
    },

    refreshPlan() {
      clearTimeout(timer);
      timer = setTimeout(evaluate, 120);
    },

    async loadField(sectionId, { force = false } = {}) {
      const cur = store.get().field[sectionId];
      if (!force && (cur?.status === 'ready' || cur?.status === 'loading')) return;
      store.update((s) => {
        s.field[sectionId] = { status: 'loading', data: cur?.data ?? null, error: null };
      });
      try {
        const data = await engine.getFieldData({ farm: store.get().farm, sectionId });
        store.update((s) => {
          s.field[sectionId] = { status: 'ready', data, error: null };
        });
      } catch (err) {
        store.update((s) => {
          s.field[sectionId] = { status: 'error', data: null, error: err.message };
        });
      }
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

    async proposeRotation(sectionId, cycleYears) {
      store.update((s) => {
        s.ui.proposing = true;
      });
      try {
        const res = await engine.proposeRotation({
          farm: store.get().farm,
          sectionId,
          cycleYears,
        });
        app.updateFarm((farm, s) => {
          farm.sections.find((x) => x.id === sectionId).rotation = res.rotation;
          s.ui.proposal = {
            sectionId,
            reasons: res.reasons ?? [],
            missingSeeds: res.missingSeeds ?? [],
          };
        });
      } finally {
        store.update((s) => {
          s.ui.proposing = false;
        });
      }
    },
  };

  /**
   * Ask the engine for a rotation on every section, built from the seed
   * reserve, then stagger the sections. Sections are proposed one after the
   * other so that each request sees the rotations already chosen.
   */
  app.proposeAll = async () => {
    const cycleYears = suggestCycleYears(getSeeds(store.get().farm).crops);
    store.update((s) => {
      s.ui.proposeAll = { status: 'loading', missing: [], error: null };
    });
    const missing = new Set();
    try {
      for (const { id } of store.get().farm.sections) {
        const res = await engine.proposeRotation({
          farm: store.get().farm,
          sectionId: id,
          cycleYears,
        });
        (res.missingSeeds ?? []).forEach((c) => missing.add(c));
        store.update((s) => {
          const sec = s.farm.sections.find((x) => x.id === id);
          if (sec) sec.rotation = res.rotation;
        });
      }
      app.updateFarm((farm, s) => {
        autoStagger(farm.farm, farm.sections);
        s.ui.proposeAll = { status: 'ready', missing: [...missing], error: null };
      });
    } catch (err) {
      store.update((s) => {
        s.ui.proposeAll = { status: 'error', missing: [], error: err.message };
      });
      app.refreshPlan();
    }
  };

  /** Wildfires near the farm and their effect on the sections (see src/fireController.js). */
  Object.assign(app, fireController(store));

  async function evaluate() {
    const farm = store.get().farm;
    const incomplete = farm.sections.some((s) => toSlots(s.rotation).some((x) => !x.crop));
    if (incomplete) {
      store.update((s) => {
        s.plan.status = 'incomplete';
      });
      return;
    }
    const mine = ++seq;
    store.update((s) => {
      s.plan.status = s.plan.data ? 'refreshing' : 'loading';
      s.plan.error = null;
    });
    try {
      const data = await engine.evaluateFarm(farm);
      if (mine !== seq) return;
      store.update((s) => {
        s.plan = { status: 'ready', data, error: null };
        for (const sec of data.sections) {
          if (s.ui.explorerSnap[sec.id] && !s.ui.explorerBase[sec.id]) {
            s.ui.explorerBase[sec.id] = sec.scores;
          }
        }
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
