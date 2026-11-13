/** 1 · Connexion et création de compte. Owner: Loïc. */
import { html } from '../lib/html.js';
import { logo } from '../ui/widgets.js';

const fieldsArt = html`<svg
  class="auth__art"
  viewBox="0 0 720 900"
  preserveAspectRatio="xMidYMid slice"
  aria-hidden="true"
>
  <g transform="translate(360 470) rotate(-18) translate(-560 -560)">
    <rect width="1120" height="1120" fill="#26462F"></rect>
    <rect x="40" y="60" width="320" height="300" fill="url(#pat-soya)"></rect>
    <rect x="380" y="60" width="300" height="300" fill="url(#pat-ble)"></rect>
    <rect x="700" y="60" width="380" height="300" fill="url(#pat-mais)"></rect>
    <rect x="40" y="380" width="460" height="320" fill="url(#pat-orge)"></rect>
    <rect x="520" y="380" width="260" height="320" fill="url(#pat-patate)"></rect>
    <rect x="800" y="380" width="280" height="320" fill="url(#pat-ble)"></rect>
    <rect x="40" y="720" width="300" height="340" fill="url(#pat-luzerne)"></rect>
    <rect x="360" y="720" width="420" height="340" fill="url(#pat-mais)"></rect>
    <rect x="800" y="720" width="280" height="340" fill="url(#pat-soya)"></rect>
  </g>
  <rect width="720" height="900" fill="#0E1F13" fill-opacity=".58"></rect>
</svg>`;

export default {
  title: 'Connexion',
  render(state) {
    const signup = state.ui.authMode === 'signup';
    return html`<div class="auth">
      <section class="auth__hero">
        ${fieldsArt}
        <div class="auth__brand">${logo(44)}<span class="brand__name">Field Shift</span></div>
        <div class="auth__pitch">
          <h1>Planifiez vos rotations avec les données des satellites.</h1>
          <p>
            Pluie, humidité du sol, chaleur : Field Shift lit les données de la NASA pour votre
            ferme et vous aide à choisir quoi planter, section par section, année après année.
          </p>
          <div class="chips-row">
            <span class="chip chip--glass">Données NASA</span
            ><span class="chip chip--glass">Rotation par section</span
            ><span class="chip chip--glass">Prévisions sur 3 à 30 ans</span>
          </div>
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
  actions: {
    'auth-mode': (app, el) =>
      app.update((s) => {
        s.ui.authMode = el.dataset.mode;
      }),
    'auth-submit': (app, form) => {
      // Demo only: no real authentication yet (see docs/ROADMAP.md).
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
