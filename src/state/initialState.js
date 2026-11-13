import { DEMO_FARM } from '../data/demoFarm.js';
import { GREETING } from '../rotaai/answers.js';

export const STORAGE_KEY = 'field-shift:v2';

/** What survives a page reload (per browser, never shared). */
export const persisted = (state) => ({
  user: state.user,
  onboarded: state.onboarded,
  farm: state.farm,
});

export function loadSaved(storage) {
  try {
    const raw = storage?.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function save(storage, state) {
  try {
    storage?.setItem(STORAGE_KEY, JSON.stringify(persisted(state)));
  } catch {
    /* storage can be unavailable (private mode, previews): the app still works */
  }
}

export function initialState(engineName, saved) {
  return {
    engineName,
    user: saved?.user ?? null,
    onboarded: saved?.onboarded ?? false,
    farm: saved?.farm ?? structuredClone(DEMO_FARM),
    plan: { status: 'idle', data: null, error: null },
    field: {},
    ui: {
      route: { name: 'connexion', params: {} },
      authMode: 'login',
      farmTypeSel: 'grandes-cultures',
      placeSel: 0,
      selectedSection: 'A',
      yearIndex: 1,
      prevOffsets: null,
      rotSlot: 0,
      role: 'azote',
      compare: 'mais-continu',
      stressScenario: 'sec',
      sourcesFilter: 'all',
      openSources: { 0: true },
      openInfo: null,
      reported: {},
      settingsTab: 'ferme',
      explorerSnap: {},
      explorerBase: {},
      proposing: false,
      rota: { open: false, typing: false, msgs: [{ from: 'bot', text: GREETING }] },
    },
  };
}
