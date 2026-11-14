/**
 * The application layer on its own: no screen, a fake engine, an in-memory
 * storage and a stubbed network.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { createApp } from '../application/app.js';
import { STORAGE_KEY } from '../data/access/storage.js';

const engine = {
  name: 'test',
  evaluateFarm: vi.fn(),
  proposeRotation: vi.fn(),
  getFieldData: vi.fn(),
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

  it('keeps a given label without looking up the address', () => {
    const fetch = vi.fn();
    vi.stubGlobal('fetch', fetch);
    const app = createApp({ engine, storage: memoryStorage() });
    app.setFarmLocation(45.6, -72.9, 'Ma ferme');
    expect(app.state.farm.farm.location.label).toBe('Ma ferme');
    expect(fetch).not.toHaveBeenCalled();
  });
});
