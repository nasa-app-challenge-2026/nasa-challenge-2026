/**
 * Entry point, and the only place where the layers are wired together (see
 * docs/ARCHITECTURE.md): the engine (backend/) is handed to the application
 * controller (application/app.js); the router and the screens render its state.
 * Rendering is a full re-render of the current screen on every state change
 * (simple and fast enough here); events are delegated through data-* attributes:
 *   data-action="name"  on click
 *   data-submit="name"  on form submit
 *   data-change="name"  on change (selects, inputs)
 *   data-input="name"   on input (sliders)
 *
 * Two things survive a re-render:
 *   - inputs marked `data-preserve` (with an id) keep their value and focus;
 *   - Leaflet maps, kept in detached hosts and re-attached into `mapSlot()`
 *     placeholders (frontend/ui/leafletMap.js). A screen with a map implements
 *     `mount(app, params)` (called after every render, must be idempotent)
 *     and `unmount(app)` (called when leaving the screen).
 */
import 'leaflet/dist/leaflet.css';
import './styles/tokens.css';
import './styles/base.css';
import './styles/components.css';
import './styles/screens.css';

import { createEngine } from '../backend/index.js';
import { createApp } from '../application/app.js';
import { parseHash } from './router.js';
import { SCREENS } from './screens/index.js';
import { globalActions } from './actions.js';
import { TEXTURE_DEFS } from './ui/textures.js';
import { rota } from './ui/rota.js';
import { attachSlots } from './ui/leafletMap.js';
import { captureLayout, initDragSort, isDragging, playLayout } from './ui/dragSort.js';
import { html } from './lib/html.js';

document.body.insertAdjacentHTML('afterbegin', TEXTURE_DEFS);
const root = document.getElementById('app');
const app = createApp({ engine: createEngine() });

const currentScreen = () => SCREENS[app.state.ui.route.name];

function defaultRoute(s) {
  if (!s.user) return '#/connexion';
  return s.onboarded ? '#/tableau' : '#/type-de-ferme';
}

/**
 * Page changes are animated with the View Transitions API (a short fade; a
 * slide along the onboarding steps). Elements that share a
 * `view-transition-name` on both pages (the section letter, the header) travel
 * or stay put. Older browsers and "reduce motion" users get an instant swap.
 */
const ONBOARDING = ['type-de-ferme', 'localisation', 'tracer', 'cultures', 'temps', 'priorites'];
let lastRouteName = null;
let pendingNav = null; // 'forward' | 'back' | 'fade' | null

function navDirection(from, to) {
  const a = ONBOARDING.indexOf(from);
  const b = ONBOARDING.indexOf(to);
  if (a >= 0 && b >= 0) return b > a ? 'forward' : 'back';
  return 'fade';
}

function onRoute() {
  const s = app.state;
  const route = parseHash(location.hash);
  if (!route.name) return location.replace(defaultRoute(s));
  if (!s.user && route.name !== 'connexion') return location.replace('#/connexion');
  if (route.params.id && !app.section(route.params.id)) return location.replace('#/tableau');

  if (lastRouteName && lastRouteName !== route.name) {
    pendingNav = navDirection(lastRouteName, route.name);
  }
  lastRouteName = route.name;

  const screen = SCREENS[route.name];
  const leavesScreen = s.ui.route.name !== route.name;
  app.update((d) => {
    d.ui.route = route;
    if (route.params.id) d.ui.selectedSection = route.params.id;
    // Rota answered on the screen we leave: the next one starts without the panel over it.
    if (leavesScreen) d.ui.rota.open = false;
  });
  document.title = `${screen.title} · Field Shift`;
  window.scrollTo(0, 0);
  screen.onEnter?.(app, route.params);
}

let scheduled = false;
function schedule() {
  if (scheduled) return;
  scheduled = true;
  requestAnimationFrame(() => {
    scheduled = false;
    render();
  });
}

/** Snapshot of what the user is typing, restored after the re-render. */
function snapshotInputs() {
  return [...root.querySelectorAll('[data-preserve][id]')].map((el) => ({
    id: el.id,
    value: el.value,
    focused: document.activeElement === el,
    start: el.selectionStart,
    end: el.selectionEnd,
  }));
}
function restoreInputs(saved) {
  for (const t of saved) {
    const el = document.getElementById(t.id);
    if (!el) continue;
    el.value = t.value;
    if (t.focused) {
      el.focus();
      try {
        el.setSelectionRange(t.start, t.end);
      } catch {
        /* not every input type supports selection ranges */
      }
    }
  }
}

let mounted = null;
let deferred = false;

function render() {
  if (isDragging()) {
    deferred = true; // never rebuild the DOM under the user's finger
    return;
  }
  deferred = false;
  const nav = pendingNav;
  pendingNav = null;
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (nav && typeof document.startViewTransition === 'function' && !reduce) {
    document.documentElement.dataset.nav = nav;
    const transition = document.startViewTransition(draw);
    transition.finished.finally(() => delete document.documentElement.dataset.nav);
  } else {
    draw();
  }
}

function draw() {
  const s = app.state;
  const screen = currentScreen();
  if (!screen) return;

  const name = s.ui.route.name;
  const sameScreen = mounted === name;
  if (mounted && !sameScreen) SCREENS[mounted]?.unmount?.(app);
  mounted = name;

  const typed = snapshotInputs();
  const refocus = document.activeElement?.closest?.('[data-refocus][id]')?.id;
  const layout = sameScreen ? captureLayout(root) : null;
  // Rota is on every screen: with its launcher where the screen names its questions
  // (`rota: 'plan'`), else only once a « Demander à Rota » button has opened it.
  const body = screen.render(s, s.ui.route.params, app);
  root.innerHTML = String(html`${body}${rota(s, screen.rota, { launcher: !!screen.rota })}`);

  const list = document.getElementById('rota-list');
  if (list) list.scrollTop = list.scrollHeight;
  restoreInputs(typed);
  if (refocus) document.getElementById(refocus)?.focus({ preventScroll: true });
  playLayout(root, layout);
  attachSlots(root);
  screen.mount?.(app, s.ui.route.params);
}

function run(name, el, event) {
  const fn = currentScreen()?.actions?.[name] ?? globalActions[name];
  if (!fn) {
    console.warn(`[field-shift] action inconnue : ${name}`);
    return;
  }
  fn(app, el, event);
}

root.addEventListener('click', (e) => {
  const el = e.target.closest('[data-action]');
  if (!el || !root.contains(el) || el.disabled) return;
  if (el.tagName === 'A') e.preventDefault();
  run(el.dataset.action, el, e);
});
root.addEventListener('submit', (e) => {
  const form = e.target.closest('form[data-submit]');
  if (!form) return;
  e.preventDefault();
  run(form.dataset.submit, form, e);
});
root.addEventListener('change', (e) => {
  const el = e.target.closest('[data-change]');
  if (el) run(el.dataset.change, el, e);
});
root.addEventListener('input', (e) => {
  const el = e.target.closest('[data-input]');
  if (el) run(el.dataset.input, el, e);
});

window.addEventListener('hashchange', onRoute);
initDragSort(root, {
  onCommit: (list, ids, moved) => run(list.dataset.commit, list, { ids, moved }),
  onEnd: () => deferred && schedule(),
});
app.store.subscribe(schedule);
onRoute();
app.refreshPlan();
render();
