/**
 * Local save in the browser (localStorage). A demo comfort: nothing is shared
 * between browsers, and the app still works when storage is blocked (private
 * mode, previews). What gets saved is decided by the application layer
 * (`persisted` in application/state/initialState.js).
 */
export const STORAGE_KEY = 'field-shift:v2';

export function loadSaved(storage) {
  try {
    const raw = storage?.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

/**
 * The last plan the server gave, kept beside the farm it was computed for. At the next visit the
 * screens show it at once while the server computes the plan again. Its own key: a plan is
 * ~250 kB, written only when a new one arrives, not at every change of the state.
 */
export const PLAN_STORAGE_KEY = 'field-shift:plan:v3';

/** { key, data } of the last plan saved, or null. */
export function loadPlan(storage) {
  try {
    const raw = storage?.getItem(PLAN_STORAGE_KEY);
    const saved = raw ? JSON.parse(raw) : null;
    return saved?.key && saved?.data ? saved : null;
  } catch {
    return null;
  }
}

export function savePlan(storage, key, data) {
  try {
    storage?.setItem(PLAN_STORAGE_KEY, JSON.stringify({ key, data }));
  } catch {
    /* storage full or unavailable: the plan is simply computed again next time */
  }
}

export function save(storage, snapshot) {
  try {
    storage?.setItem(STORAGE_KEY, JSON.stringify(snapshot));
  } catch {
    /* storage can be unavailable (private mode, previews): the app still works */
  }
}
