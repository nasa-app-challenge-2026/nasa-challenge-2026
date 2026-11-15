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

export function save(storage, snapshot) {
  try {
    storage?.setItem(STORAGE_KEY, JSON.stringify(snapshot));
  } catch {
    /* storage can be unavailable (private mode, previews): the app still works */
  }
}
