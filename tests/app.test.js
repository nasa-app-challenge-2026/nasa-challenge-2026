/**
 * The application layer on its own: no screen, a fake engine, an in-memory
 * storage and a stubbed network.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { createApp } from '../application/app.js';
import { PLAN_STORAGE_KEY, STORAGE_KEY } from '../data/access/storage.js';
import { DEMO_FARM } from '../data/reference/demoFarm.js';

const engine = {
  name: 'test',
  planFarm: vi.fn(async () => ({ version: '2.0', sections: [] })),
};

function memoryStorage() {
  const data = {};
  return {
    data,
    getItem: (key) => data[key] ?? null,
    setItem: (key, value) => {
      data[key] = String(value);
    },
  };
}

const answer = (body) => vi.fn(async () => ({ ok: true, json: async () => body }));

afterEach(() => vi.unstubAllGlobals());

describe('application', () => {
  it('saves what survives a reload, and only that', () => {
    const storage = memoryStorage();
    const app = createApp({ engine, storage });
    app.update((s) => {
      s.user = { name: 'Fermier de démo', email: null };
      s.ui.rota.open = true;
    });
    const saved = JSON.parse(storage.data[STORAGE_KEY]);
    expect(Object.keys(saved).sort()).toEqual(['farm', 'onboarded', 'prefs', 'user']);
    expect(createApp({ engine, storage }).state.user.name).toBe('Fermier de démo');
  });

  it('searches an address and keeps the results in ui.geo', async () => {
    vi.stubGlobal(
      'fetch',
      answer([
        { display_name: 'Rang Saint-Pierre, Saint-Hyacinthe, QC', lat: '45.63', lon: '-72.95' },
      ]),
    );
    const app = createApp({ engine, storage: memoryStorage() });
    const results = await app.searchPlaces('rang saint-pierre');
    expect(results[0]).toMatchObject({ label: 'Rang Saint-Pierre', lat: 45.63, lon: -72.95 });
    expect(app.state.ui.geo).toMatchObject({ query: 'rang saint-pierre', status: 'ready' });
  });

  it('reports a failed address search in ui.geo instead of throwing', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({ ok: false, status: 503 })),
    );
    const app = createApp({ engine, storage: memoryStorage() });
    expect(await app.searchPlaces('nulle part')).toEqual([]);
    expect(app.state.ui.geo.status).toBe('error');
  });

  it('moves the farm, then fills in the address found for that point', async () => {
    vi.stubGlobal(
      'fetch',
      answer({
        address: { road: 'Rang Saint-Pierre', village: 'Saint-Dominique', state: 'Québec' },
      }),
    );
    const app = createApp({ engine, storage: memoryStorage() });
    app.setFarmLocation(45.5, -72.8);
    expect(app.state.farm.farm.location).toEqual({
      lat: 45.5,
      lon: -72.8,
      label: '45.5000, -72.8000',
    });
    await vi.waitFor(() =>
      expect(app.state.farm.farm.location.label).toBe('Rang Saint-Pierre, Saint-Dominique, Québec'),
    );
  });

  it('asks the engine for a plan and keeps it', async () => {
    const app = createApp({ engine, storage: memoryStorage() });
    app.refreshPlan();
    await vi.waitFor(() => expect(app.state.plan.status).toBe('ready'));
    expect(engine.planFarm).toHaveBeenCalledWith(app.state.farm);
  });

  it('shows the plan of the last visit at once, and still asks the engine for a fresh one', async () => {
    const storage = memoryStorage();
    const first = createApp({ engine, storage });
    first.refreshPlan();
    await vi.waitFor(() => expect(first.state.plan.status).toBe('ready'));
    expect(JSON.parse(storage.data[PLAN_STORAGE_KEY]).data).toEqual(first.state.plan.data);

    const calls = engine.planFarm.mock.calls.length;
    const second = createApp({ engine, storage });
    expect(second.state.plan).toMatchObject({ status: 'ready', data: first.state.plan.data });
    second.refreshPlan();
    await vi.waitFor(() => expect(engine.planFarm.mock.calls.length).toBe(calls + 1));
  });

  it('does not show the plan of the last visit for another farm', () => {
    const storage = memoryStorage();
    storage.setItem(PLAN_STORAGE_KEY, JSON.stringify({ key: '{"another":"farm"}', data: {} }));
    expect(createApp({ engine, storage }).state.plan).toMatchObject({ status: 'idle', data: null });
  });

  it('asks the engine once for a farm already planned in this visit', async () => {
    const planFarm = vi.fn(async (farm) => ({ priorities: farm.farm.priorities }));
    const app = createApp({ engine: { name: 'test', planFarm }, storage: memoryStorage() });
    const swapPriorities = () =>
      app.updateFarm((farm) => {
        const [a, b, ...rest] = farm.farm.priorities;
        farm.farm.priorities = [b, a, ...rest];
      });
    const planned = async (count) => {
      await vi.waitFor(() => expect(app.state.plan.status).toBe('ready'));
      expect(planFarm).toHaveBeenCalledTimes(count);
      expect(app.state.plan.data.priorities).toEqual(app.state.farm.farm.priorities);
    };
    app.refreshPlan();
    await planned(1);
    swapPriorities();
    await vi.waitFor(() => expect(planFarm).toHaveBeenCalledTimes(2));
    await planned(2);
    swapPriorities(); // back to the first farm: its plan is known
    await vi.waitFor(() =>
      expect(app.state.plan.data.priorities).toEqual(app.state.farm.farm.priorities),
    );
    await planned(2);
  });

  it('does not plan while a section misses its harvest month', async () => {
    const app = createApp({ engine, storage: memoryStorage() });
    app.updateSection('A', (s) => (s.currentHarvest = null));
    await vi.waitFor(() => expect(app.state.plan.status).toBe('incomplete'));
    expect(app.state.plan.error).toMatch(/Section A/);
  });

  it('migrates a farm saved by the previous version', () => {
    const storage = memoryStorage();
    storage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        user: null,
        farm: {
          version: '1.0',
          farm: { name: 'Vieille ferme', location: { lat: 45, lon: -73, label: 'X' } },
          sections: [
            {
              id: 'A',
              areaHa: 3,
              offset: 1,
              currentCrop: 'ble',
              rotation: [
                { crop: 'ble', years: 1 },
                { crop: 'patate', years: 1 },
              ],
            },
          ],
        },
      }),
    );
    const farm = createApp({ engine, storage }).state.farm;
    expect(farm.version).toBe('2.0');
    expect(farm.farm.name).toBe('Vieille ferme');
    expect(farm.sections[0]).toMatchObject({
      currentCrop: 'ble-automne',
      currentRotation: ['ble-automne'],
    });
    expect(farm.sections[0].offset).toBeUndefined();
    expect(farm.farm.priorities).toHaveLength(4);
  });

  it('brings a farm saved with the nine criteria to the four priorities', () => {
    const storage = memoryStorage();
    const saved = structuredClone(DEMO_FARM);
    saved.farm.priorities = ['erosion', 'rendement', 'azote', 'reserve', 'matiere_org', 'marche'];
    saved.farm.livestock = true;
    storage.setItem(STORAGE_KEY, JSON.stringify({ user: null, farm: saved }));
    const { farm } = createApp({ engine, storage }).state;
    expect(farm.farm.priorities).toEqual(['protection_sol', 'rendement', 'eau', 'ravageurs']);
    expect(farm.farm.livestock).toBeUndefined();
    expect(farm.sections).toEqual(DEMO_FARM.sections);
  });

  it('keeps a given label without looking up the address', () => {
    const fetch = vi.fn();
    vi.stubGlobal('fetch', fetch);
    const app = createApp({ engine, storage: memoryStorage() });
    app.setFarmLocation(45.6, -72.9, 'Ma ferme');
    expect(app.state.farm.farm.location.label).toBe('Ma ferme');
    expect(fetch).not.toHaveBeenCalled();
  });
});
