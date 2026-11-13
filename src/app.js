/**
 * Application controller: state, engine calls, navigation. Screens never call
 * the engine directly; they go through these helpers.
 */
import { createStore } from './state/store.js';
import { initialState, loadSaved, save } from './state/initialState.js';
import { toSlots } from './lib/rotation.js';

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

    async proposeRotation(sectionId, cycleYears) {
      store.update((s) => {
        s.ui.proposing = true;
      });
      try {
        const { rotation } = await engine.proposeRotation({
          farm: store.get().farm,
          sectionId,
          cycleYears,
        });
        app.updateFarm((farm) => {
          farm.sections.find((x) => x.id === sectionId).rotation = rotation;
        });
      } finally {
        store.update((s) => {
          s.ui.proposing = false;
        });
      }
    },
  };

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
