import { html } from '../lib/html.js';
import { explain } from '../../data/reference/rotaAnswers.js';

let current = null;
let context = null;
const duration = () => (matchMedia('(prefers-reduced-motion: reduce)').matches ? 140 : 450);
const focusable = 'button:not([disabled]), a[href], input, select, textarea, [tabindex="0"]';

/** A native modal supplies inert background semantics; geometry comes from the actual card. */
export function openRotationDialog(trigger) {
  if (current) return;
  const card = trigger.closest('.rot-card');
  const template = card.querySelector('template');
  const origin = card.getBoundingClientRect();
  const dialog = document.createElement('dialog');
  dialog.className = 'rotation-dialog';
  dialog.setAttribute('role', 'dialog');
  dialog.setAttribute('aria-modal', 'true');
  dialog.setAttribute('aria-labelledby', 'rotation-dialog-title');
  dialog.innerHTML = String(
    html`<div class="rotation-dialog__shell">
      <div class="rotation-dialog__turn">
        <div class="rotation-dialog__front" aria-hidden="true"></div>
        <div class="rotation-dialog__back">
          <button type="button" class="rotation-dialog__close" aria-label="Fermer la rotation">
            ×
          </button>
          <div class="rotation-dialog__scroll" tabindex="0">
            ${html`<h2 class="h2" id="rotation-dialog-title">${trigger.dataset.title}</h2>`}
            <div class="rotation-dialog__content"></div>
            <div class="rotation-dialog__answer" aria-live="polite"></div>
          </div>
        </div>
      </div>
    </div>`,
  );
  const front = card.cloneNode(true);
  front.querySelectorAll('button, template').forEach((el) => el.remove());
  front.removeAttribute('id');
  dialog.querySelector('.rotation-dialog__front').append(front);
  dialog.querySelector('.rotation-dialog__content').append(template.content.cloneNode(true));
  document.body.append(dialog);
  const overflow = document.body.style.overflow;
  document.body.style.overflow = 'hidden';
  dialog.showModal();
  const shell = dialog.querySelector('.rotation-dialog__shell');
  const turn = dialog.querySelector('.rotation-dialog__turn');
  const target = shell.getBoundingClientRect();
  const transformFor = (r) =>
    `translate(${r.left - target.left}px, ${r.top - target.top}px) scale(${r.width / target.width}, ${r.height / target.height})`;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const options = { duration: duration(), easing: 'cubic-bezier(.2,.7,.2,1)', fill: 'both' };
  const animations = reduced
    ? [shell.animate([{ opacity: 0 }, { opacity: 1 }], options)]
    : [
        shell.animate([{ transform: transformFor(origin) }, { transform: 'none' }], options),
        turn.animate([{ transform: 'rotateY(0deg)' }, { transform: 'rotateY(180deg)' }], options),
      ];
  card.classList.add('is-open');
  const state = { dialog, triggerId: trigger.id, card, overflow, closing: false, animations };
  current = state;
  state.close = async (immediate = false) => {
    if (state.closing && !immediate) return;
    state.closing = true;
    animations.forEach((a) => a.cancel());
    if (!immediate) {
      const source = document.getElementById(state.triggerId)?.closest('.rot-card');
      const frames =
        reduced || !source
          ? [{ opacity: 1 }, { opacity: 0 }]
          : [{ transform: 'none' }, { transform: transformFor(source.getBoundingClientRect()) }];
      const closing = [shell.animate(frames, options)];
      if (!reduced)
        closing.push(
          turn.animate([{ transform: 'rotateY(180deg)' }, { transform: 'rotateY(0deg)' }], options),
        );
      state.animations.push(...closing);
      await Promise.allSettled(closing.map((a) => a.finished));
    }
    if (current !== state) return;
    current = null;
    dialog.close();
    dialog.remove();
    card.classList.remove('is-open');
    document.body.style.overflow = overflow;
    document.getElementById(state.triggerId)?.focus({ preventScroll: true });
  };
  dialog.addEventListener('cancel', (event) => {
    event.preventDefault();
    state.close();
  });
  dialog.addEventListener('click', (event) => {
    if (event.target === dialog || event.target.closest('.rotation-dialog__close')) state.close();
    const ask = event.target.closest('[data-topic]');
    if (ask) {
      const answer = explain(ask.dataset.topic);
      const area = dialog.querySelector('.rotation-dialog__answer');
      area.innerHTML = String(
        html`<aside class="alert alert--info">
          <strong>Rota</strong>
          <p>${answer?.text ?? ''}</p>
          ${answer?.sources ? html`<a href="#/sources">Voir les sources →</a>` : ''}
        </aside>`,
      );
      area.scrollIntoView({ block: 'nearest', behavior: 'instant' });
    }
  });
  dialog.addEventListener('keydown', (event) => {
    if (event.key !== 'Tab') return;
    const elements = [
      ...dialog.querySelector('.rotation-dialog__back').querySelectorAll(focusable),
    ];
    const first = elements[0];
    const last = elements.at(-1);
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });
  dialog.querySelector('.rotation-dialog__close').focus({ preventScroll: true });
}

export const closeRotationDialog = () => current?.close(true);
/** Redraws (cycle, language, route, fresh plan) must never leave a stale modal behind. */
export function beforeRotationRender(next) {
  if (next !== context) closeRotationDialog();
  context = next;
}
