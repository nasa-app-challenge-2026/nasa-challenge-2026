import { DEMO_FARM } from '../data/demoFarm.js';
import { GREETING } from '../rotaai/answers.js';
import { deriveSeeds } from '../lib/seeds.js';

export const STORAGE_KEY = 'field-shift:v2';

/** What survives a page reload (per browser, never shared). */
export const persisted = (state) => ({
  user: state.user,
  onboarded: state.onboarded,
  farm: state.farm,
  prefs: state.prefs,
});

/** Bring a farm saved by an older version up to the current model. */
export function migrateFarm(farm) {
  const f = structuredClone(farm);
  for (const s of f.sections ?? []) if (s.currentCrop === undefined) s.currentCrop = null;
  if (!f.farm.seeds) f.farm.seeds = deriveSeeds(f);
  return f;
}

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
    farm: saved?.farm ? migrateFarm(saved.farm) : structuredClone(DEMO_FARM),
    /** Per-browser display preferences. dashboard = order of the dashboard blocks (null = default). */
    prefs: { dashboard: null, ...(saved?.prefs ?? {}) },
    plan: { status: 'idle', data: null, error: null },
    field: {},
    weather: { status: 'idle', data: null, error: null, key: null },
    /** Wildfire caches (see src/fireController.js). Never saved. */
    fire: { ctx: {}, crops: {}, soil: {}, severity: {} },
    ui: {
      /** Fire page: analysed subject ('farm' | 'exemple'), selected fire, archives open. */
      fire: { subject: 'farm', eventId: null, showArchive: false },
      route: { name: 'connexion', params: {} },
      authMode: 'login',
      farmTypeSel: 'grandes-cultures',
      geo: { query: '', results: null, status: 'idle', error: null },
      draw: { target: 'farm', drawing: false },
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
      /** Last answer of the engine's /propose, shown under the rotation: { sectionId, reasons, missingSeeds }. */
      proposal: null,
      proposeAll: { status: 'idle', missing: [], error: null },
      dashAnnounce: '',
      rota: { open: false, typing: false, msgs: [{ from: 'bot', text: GREETING }] },
    },
  };
}
