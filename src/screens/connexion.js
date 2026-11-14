/** 1 · Connexion et création de compte. Owner: Loïc. */
import { html } from '../lib/html.js';
import { logo } from '../ui/widgets.js';

/**
 * Hero video (public/connexion-champs.mp4): a 12.7 s drone shot of a tractor
 * working a field, played in full and looped. The poster is its first frame.
 */
const VIDEO_SRC = 'connexion-champs.mp4';
const VIDEO_POSTER = 'connexion-champs.jpg';

// The screen is re-rendered with innerHTML on every state change: the <video>
// is created once and moved back into its slot by mount(), so it keeps playing
// when the user switches between « Se connecter » and « Créer un compte ».
let video = null;

const reduceMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

function heroVideo() {
  if (video) return video;
  video = document.createElement('video');
  video.className = 'auth__video';
  video.muted = true;
  video.defaultMuted = true;
  video.loop = true;
  video.playsInline = true;
  video.disablePictureInPicture = true;
  video.preload = reduceMotion() ? 'metadata' : 'auto';
  video.poster = VIDEO_POSTER;
  video.setAttribute('aria-hidden', 'true');
  video.src = VIDEO_SRC;
  return video;
}

export default {
  title: 'Connexion',
  render(state) {
    const signup = state.ui.authMode === 'signup';
    return html`<div class="auth">
      <section class="auth__hero">
        <div class="auth__art" data-video-slot></div>
        <div class="auth__shade" aria-hidden="true"></div>
        <div class="auth__brand">${logo({ height: 48, onDark: true })}</div>
        <div class="auth__pitch">
          <h1>Planifiez vos rotations avec les données des satellites.</h1>
          <p>
            Pluie, humidité du sol, chaleur : Field Shift lit les données de la NASA pour votre
            ferme et vous aide à choisir quoi planter, section par section, année après année.
          </p>
        </div>
      </section>
      <main class="auth__panel" id="main">
        <div class="auth__box">
          <div class="segmented" role="tablist" aria-label="Connexion ou inscription">
            <button
              type="button"
              role="tab"
              aria-selected="${String(!signup)}"
              class="${signup ? '' : 'is-on'}"
              data-action="auth-mode"
              data-mode="login"
            >
              Se connecter
            </button>
            <button
              type="button"
              role="tab"
              aria-selected="${String(signup)}"
              class="${signup ? 'is-on' : ''}"
              data-action="auth-mode"
              data-mode="signup"
            >
              Créer un compte
            </button>
          </div>
          <div class="stack-xs">
            <h2 class="h1">${signup ? 'Créer votre compte' : 'Bon retour'}</h2>
            <p class="muted">
              ${signup ? 'Quelques secondes, puis on place votre ferme sur la carte.' : 'Connectez-vous pour retrouver votre ferme et vos rotations.'}
            </p>
          </div>
          <form class="form" data-submit="auth-submit">
            ${signup ? html`<label class="field">Nom complet<input name="name" type="text" autocomplete="name" placeholder="Prénom Nom" /></label>` : ''}
            <label class="field"
              >Courriel<input
                name="email"
                type="email"
                autocomplete="email"
                required
                value="demo@ferme.ca"
            /></label>
            <label class="field"
              >Mot de passe<input
                name="password"
                type="password"
                autocomplete="${signup ? 'new-password' : 'current-password'}"
                required
                value="demo1234"
            /></label>
            ${signup ? html`<label class="check"><input name="terms" type="checkbox" required />J’accepte les conditions d’utilisation et la politique de confidentialité.</label>` : html`<a class="link-end" href="#/compte">Mot de passe oublié ?</a>`}
            <button type="submit" class="btn btn--primary btn--block">
              ${signup ? 'Créer mon compte et commencer' : 'Se connecter'}
            </button>
          </form>
          <p class="fine">
            Données de la NASA (POWER, GPM, SMAP, ECOSTRESS, HLS). Field Shift aide à décider ; il
            ne remplace pas l’avis d’un agronome.
          </p>
        </div>
      </main>
    </div>`;
  },
  mount() {
    const slot = document.querySelector('[data-video-slot]');
    if (!slot) return;
    const v = heroVideo();
    if (v.parentNode !== slot) slot.appendChild(v);
    if (v.paused && !reduceMotion()) v.play().catch(() => {});
  },
  unmount() {
    video?.pause();
  },
  actions: {
    'auth-mode': (app, el) =>
      app.update((s) => {
        s.ui.authMode = el.dataset.mode;
      }),
    'auth-submit': (app, form) => {
      // Demo only: no real authentication yet (see docs/FRONT_ROADMAP.md).
      const data = new FormData(form);
      const signup = app.state.ui.authMode === 'signup';
      app.update((s) => {
        s.user = { name: data.get('name') || 'Fermier de démo', email: data.get('email') };
        if (signup) s.onboarded = false;
      });
      app.go(signup || !app.state.onboarded ? '#/type-de-ferme' : '#/tableau');
    },
  },
};
