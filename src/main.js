/**
 * Entry point: wires the engine, the store, the router and the screens.
 * Rendering is a full re-render of the current screen on every state change
 * (simple and fast enough here); events are delegated through data-* attributes:
 *   data-action="name"  on click
 *   data-submit="name"  on form submit
 *   data-change="name"  on change (selects, inputs)
 *   data-input="name"   on input (sliders)
 */
import './styles/tokens.css';
import './styles/base.css';
import './styles/components.css';
import './styles/screens.css';

import { createEngine } from './algo/index.js';
import { createApp } from './app.js';
import { parseHash } from './router.js';
import { SCREENS } from './screens/index.js';
import { globalActions } from './actions.js';
import { TEXTURE_DEFS } from './ui/textures.js';
import { rotaai } from './ui/rotaai.js';
import { html } from './lib/html.js';

document.body.insertAdjacentHTML('afterbegin', TEXTURE_DEFS);
const root = document.getElementById('app');
const app = createApp({ engine: createEngine() });

const currentScreen = () => SCREENS[app.state.ui.route.name];

function defaultRoute(s) {
  if (!s.user) return '#/connexion';
  return s.onboarded ? '#/tableau' : '#/type-de-ferme';
}

function onRoute() {
  const s = app.state;
  const route = parseHash(location.hash);
  if (!route.name) return location.replace(defaultRoute(s));
  if (!s.user && route.name !== 'connexion') return location.replace('#/connexion');
  if (route.params.id && !app.section(route.params.id)) return location.replace('#/tableau');

  const screen = SCREENS[route.name];
  app.update((d) => {
    d.ui.route = route;
    if (route.params.id) d.ui.selectedSection = route.params.id;
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

function render() {
  const s = app.state;
  const screen = currentScreen();
  if (!screen) return;

  // Keep what the user is typing in RotaAI across re-renders.
  const input = document.getElementById('rota-input');
  const typed = input ? { value: input.value, focused: document.activeElement === input } : null;

  const ctx = typeof screen.rota === 'function' ? screen.rota(s) : screen.rota;
  const body = screen.render(s, s.ui.route.params, app);
  root.innerHTML = String(html`${body}${ctx ? rotaai(s, ctx) : ''}`);

  const list = document.getElementById('rota-list');
  if (list) list.scrollTop = list.scrollHeight;
  const next = document.getElementById('rota-input');
  if (next && typed) {
    next.value = typed.value;
    if (typed.focused) next.focus();
  }
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
app.store.subscribe(schedule);
onRoute();
app.refreshPlan();
render();
