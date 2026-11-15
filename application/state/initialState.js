import { DEMO_FARM } from '../../data/reference/demoFarm.js';
import { GREETING } from '../../data/reference/rotaAnswers.js';
import { migrateFarm } from './migrate.js';

/** What survives a page reload (per browser, never shared; see data/access/storage.js). */
export const persisted = (state) => ({
  user: state.user,
  onboarded: state.onboarded,
  farm: state.farm,
  prefs: state.prefs,
});

export { migrateFarm };

export function initialState(engineName, saved) {
  return {
    engineName,
    user: saved?.user ?? null,
    onboarded: saved?.onboarded ?? false,
    farm: saved?.farm ? migrateFarm(saved.farm) : structuredClone(DEMO_FARM),
    /** Per-browser display preferences. dashboard = order of the dashboard blocks (null = default). */
    prefs: { dashboard: null, ...(saved?.prefs ?? {}) },
    plan: { status: 'idle', data: null, error: null },
    weather: { status: 'idle', data: null, error: null, key: null },
    ui: {
      route: { name: 'connexion', params: {} },
      authMode: 'login',
      geo: { query: '', results: null, status: 'idle', error: null },
      draw: { target: 'farm', drawing: false },
      selectedSection: 'A',
      /** Year shown by the dashboard and the field screens (null = first year of the plan). */
      year: null,
      /** Cycle shown on the plan and twins screens of a section (index from 1). */
      cycle: 1,
      /** Rotation shown in detail on the plan screen: rank of a proposal (0 = chosen) or 'ref'. */
      option: 0,
      sourcesFilter: 'all',
      openSources: { 0: true },
      settingsTab: 'ferme',
      dashAnnounce: '',
      rota: { open: false, typing: false, msgs: [{ from: 'bot', text: GREETING }] },
    },
  };
}
