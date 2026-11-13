/** RotaAI floating assistant (launcher + chat panel). State lives in state.ui.rota. */
import { html } from '../lib/html.js';
import { SUGGESTED } from '../rotaai/answers.js';
import { icon, ICONS } from './icons.js';

export function rotaai(state, ctx) {
  const r = state.ui.rota;
  const questions = SUGGESTED[ctx] ?? SUGGESTED.tableau;
  return html`<div class="rota">
    ${
      r.open
        ? html`<section class="rota__panel" aria-label="RotaAI, assistant">
            <header class="rota__head">
              <span class="rota__avatar"
                >${icon(ICONS.sprout, { size: 22, color: '#FFFFFF' })}<span
                  class="rota__spark"
                ></span
              ></span>
              <span class="stack-xs"
                ><strong class="rota__name">RotaAI</strong
                ><span class="rota__sub">Explique les chiffres et les choix de l’appli</span></span
              >
              <button
                type="button"
                class="rota__close"
                data-action="rota-toggle"
                aria-label="Fermer RotaAI"
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
              ${r.typing ? html`<div class="rota__row rota__row--bot"><div class="rota__bubble rota__typing">RotaAI écrit…</div></div>` : ''}
            </div>
            <div class="rota__chips">
              ${questions.map((q) => html`<button type="button" class="rota__chip" data-action="rota-ask" data-q="${q}">${q}</button>`)}
            </div>
            <form class="rota__form" data-submit="rota-send">
              <label class="sr-only" for="rota-input">Votre question</label>
              <input
                id="rota-input"
                name="q"
                type="text"
                autocomplete="off"
                placeholder="Posez une question à RotaAI…"
              />
              <button type="submit" class="rota__send" aria-label="Envoyer">
                ${icon(ICONS.arrowRight, { size: 18, color: '#FFFFFF' })}
              </button>
            </form>
            <p class="rota__note">RotaAI explique ; il ne remplace pas l’avis d’un agronome.</p>
          </section>`
        : ''
    }
    <button
      type="button"
      class="rota__launcher"
      data-action="rota-toggle"
      aria-expanded="${r.open ? 'true' : 'false'}"
    >
      <span class="rota__launcher-icon">${icon(ICONS.sprout, { size: 20, color: '#FFFFFF' })}</span>
      <span>${r.open ? 'Fermer' : 'RotaAI'}</span>
    </button>
  </div>`;
}
