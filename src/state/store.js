/**
 * Minimal observable store. `update` receives a draft copy of the state that
 * can be mutated freely; subscribers are notified once per update.
 */
export function createStore(initial) {
  let state = initial;
  const subscribers = new Set();
  return {
    get: () => state,
    update(mutate) {
      const draft = structuredClone(state);
      mutate(draft);
      state = draft;
      subscribers.forEach((fn) => fn(state));
    },
    subscribe(fn) {
      subscribers.add(fn);
      return () => subscribers.delete(fn);
    },
  };
}
