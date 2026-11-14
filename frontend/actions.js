/**
 * Actions available on every screen. A screen can add its own in its `actions`
 * object; they win over these. Signature: (app, element, event).
 */
import { answer } from '../data/reference/rotaaiAnswers.js';

function ask(app, question) {
  const q = String(question ?? '').trim();
  if (!q || app.state.ui.rota.typing) return;
  const reply = answer(q);
  app.update((s) => {
    s.ui.rota.msgs.push({ from: 'me', text: q });
    s.ui.rota.typing = true;
  });
  setTimeout(() => {
    app.update((s) => {
      s.ui.rota.typing = false;
      s.ui.rota.msgs.push({ from: 'bot', text: reply.text, sources: reply.sources });
    });
  }, 600);
}

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
  'set-role': (app, el) =>
    app.update((s) => {
      s.ui.role = el.dataset.role;
    }),
};
