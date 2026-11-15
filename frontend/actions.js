/**
 * Actions available on every screen. A screen can add its own in its `actions`
 * object; they win over these. Signature: (app, element, event).
 */
import { OUT_OF_MVP, answer, explain } from '../data/reference/rotaAnswers.js';

/** Time Rota "writes" before its answer shows. */
const ROTA_TYPING_MS = 600;

/** Rota opens, shows the question and, a moment later, its answer. */
function say(app, question, reply) {
  const q = String(question ?? '').trim();
  if (!q || app.state.ui.rota.typing) return;
  app.update((s) => {
    s.ui.rota.open = true;
    s.ui.rota.msgs.push({ from: 'me', text: q });
    s.ui.rota.typing = true;
  });
  setTimeout(() => {
    app.update((s) => {
      s.ui.rota.typing = false;
      s.ui.rota.msgs.push({ from: 'bot', text: reply.text, sources: reply.sources });
    });
  }, ROTA_TYPING_MS);
}

const ask = (app, question) => say(app, question, answer(question));

export const globalActions = {
  'rota-toggle': (app) =>
    app.update((s) => {
      s.ui.rota.open = !s.ui.rota.open;
    }),
  'rota-ask': (app, el) => ask(app, el.dataset.q),
  'rota-send': (app, form) => {
    const input = form.querySelector('input[name="q"]');
    ask(app, input?.value);
    if (input) input.value = '';
  },
  /** A « Demander à Rota » button: data-topic is a key of TOPICS. */
  'rota-explain': (app, el) => {
    const topic = explain(el.dataset.topic);
    if (topic) say(app, topic.q, topic);
    else console.warn(`[field-shift] sujet inconnu de Rota : ${el.dataset.topic}`);
  },
  /** Something the MVP does not do: data-what names it. */
  'rota-mvp': (app, el) => say(app, el.dataset.what, { text: OUT_OF_MVP, sources: false }),
  'select-section': (app, el) =>
    app.update((s) => {
      s.ui.selectedSection = el.dataset.id;
    }),
  'retry-plan': (app) => app.refreshPlan(),
  /** Open a settings tab from anywhere: data-tab="semences". */
  'open-settings': (app, el) => {
    app.update((s) => {
      s.ui.settingsTab = el.dataset.tab;
    });
    app.go('#/compte');
  },
  /** Year shown by the dashboard and the section screens. */
  'set-year': (app, el) =>
    app.update((s) => {
      // A year button carries data-year; the slider has a value (a button's value is '').
      s.ui.year = Number(el.dataset.year ?? el.value);
    }),
  /** Cycle shown on the plan and twins screens (the first rotation of the cycle is shown). */
  'set-cycle': (app, el) =>
    app.update((s) => {
      s.ui.cycle = Number(el.dataset.cycle);
      s.ui.option = 0;
    }),
  /** Rotation shown in detail on the plan screen: 0 to 2 (proposals) or "ref" (current one). */
  'set-option': (app, el) =>
    app.update((s) => {
      s.ui.option = el.dataset.option === 'ref' ? 'ref' : Number(el.dataset.option);
    }),
};
