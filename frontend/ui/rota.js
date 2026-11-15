/**
 * Rota, the assistant: the launcher, the chat panel, and the small « Demander à Rota » button the
 * screens put where an explanation would be. State lives in state.ui.rota; the answers are in
 * data/reference/rotaAnswers.js.
 */
import { html } from '../lib/html.js';
import { SUGGESTED } from '../../data/reference/rotaAnswers.js';
import { icon, ICONS } from './icons.js';

/**
 * The button that replaces an explanation on a screen: Rota opens and explains `topic` (a key of
 * TOPICS). The screens write no "how it works" text themselves.
 */
export function askRota(topic, label = 'Demander à Rota') {
  return html`<button
    type="button"
    class="ask-rota"
    data-action="rota-explain"
    data-topic="${topic}"
  >
    ${icon(ICONS.sprout, { size: 14 })}<span>${label}</span>
  </button>`;
}

/** The same button as a small round icon, where a label would not fit (a chip, a sub-title). */
export function askRotaIcon(topic) {
  return html`<button
    type="button"
    class="ask-rota ask-rota--icon"
    data-action="rota-explain"
    data-topic="${topic}"
    aria-label="Demander à Rota"
    title="Demander à Rota"
  >
    ${icon(ICONS.sprout, { size: 14 })}
  </button>`;
}

function typingDots() {
  return html`<div class="rota__row rota__row--bot">
    <div class="rota__bubble rota__typing" role="status" aria-label="Rota écrit">
      <span></span><span></span><span></span>
    </div>
  </div>`;
}

/**
 * `ctx` chooses the suggested questions. `launcher: false` (screens of the first visit, where
 * the corner belongs to the map buttons) shows Rota only once a button has opened it.
 */
export function rota(state, ctx, { launcher = true } = {}) {
  const r = state.ui.rota;
  if (!r.open && !launcher) return '';
  const questions = SUGGESTED[ctx] ?? SUGGESTED.general;
  return html`<div class="rota">
    ${
      r.open
        ? html`<section class="rota__panel" aria-label="Rota, assistant">
            <header class="rota__head">
              <span class="rota__avatar"
                >${icon(ICONS.sprout, { size: 22, color: '#FFFFFF' })}<span
                  class="rota__spark"
                ></span
              ></span>
              <strong class="rota__name">Rota</strong>
              <button
                type="button"
                class="rota__close"
                data-action="rota-toggle"
                aria-label="Fermer Rota"
              >
                ${icon(ICONS.close, { size: 18 })}
              </button>
            </header>
            <div class="rota__list" id="rota-list" aria-live="polite">
              ${r.msgs.map(
                (m) =>
                  html`<div class="rota__row rota__row--${m.from}">
                    <div class="rota__bubble">
                      ${m.text}${m.sources ? html`<a class="rota__src" href="#/sources">Voir les sources →</a>` : ''}
                    </div>
                  </div>`,
              )}
              ${r.typing ? typingDots() : ''}
            </div>
            <div class="rota__chips">
              ${questions.map((q) => html`<button type="button" class="rota__chip" data-action="rota-ask" data-q="${q}">${q}</button>`)}
            </div>
            <form class="rota__form" data-submit="rota-send">
              <label class="sr-only" for="rota-input">Votre question</label>
              <input
                id="rota-input"
                data-preserve
                name="q"
                type="text"
                autocomplete="off"
                placeholder="Posez une question à Rota…"
              />
              <button type="submit" class="rota__send" aria-label="Envoyer">
                ${icon(ICONS.arrowRight, { size: 18, color: '#FFFFFF' })}
              </button>
            </form>
          </section>`
        : ''
    }
    ${
      launcher
        ? html`<button
            type="button"
            class="rota__launcher"
            data-action="rota-toggle"
            aria-expanded="${r.open ? 'true' : 'false'}"
          >
            <span class="rota__launcher-icon"
              >${icon(ICONS.sprout, { size: 20, color: '#FFFFFF' })}</span
            >
            <span>${r.open ? 'Fermer' : 'Rota'}</span>
          </button>`
        : ''
    }
  </div>`;
}
