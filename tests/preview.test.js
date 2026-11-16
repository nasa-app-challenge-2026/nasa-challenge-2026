import { afterEach, expect, it, vi } from 'vitest';
import { createApp } from '../application/app.js';

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});
it('isolates sample data from saved farms, calculations and late real responses', async () => {
  vi.useFakeTimers();
  vi.stubGlobal('location', { hash: '#/tableau' });
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
  const values = new Map();
  const storage = { getItem: (k) => values.get(k), setItem: (k, v) => values.set(k, v) };
  let resolve;
  const engine = {
    name: 'test',
    planFarm: vi.fn(
      () =>
        new Promise((r) => {
          resolve = r;
        }),
    ),
  };
  const app = createApp({ engine, storage });
  app.update((s) => {
    s.farm.farm.name = 'My real farm';
  });
  const saved = [...values];
  app.refreshPlan();
  await vi.advanceTimersByTimeAsync(300);
  app.enterDemo();
  expect(app.state.ui.demo).toBe(true);
  expect(app.state.plan.data.sections.length).toBeGreaterThan(0);
  app.updateFarm((f) => {
    f.farm.name = 'Changed';
  });
  app.refreshPlan();
  await app.loadWeather();
  resolve({ version: '2.0', sections: [] });
  await vi.advanceTimersByTimeAsync(300);
  expect(app.state.plan.data.sections.length).toBeGreaterThan(0);
  expect([...values]).toEqual(saved);
  expect(engine.planFarm).toHaveBeenCalledTimes(1);
  expect(fetch).not.toHaveBeenCalled();
  app.exitDemo();
  expect(app.state.ui.demo).toBe(false);
  expect(app.state.farm.farm.name).toBe('My real farm');
  vi.clearAllTimers();
});
