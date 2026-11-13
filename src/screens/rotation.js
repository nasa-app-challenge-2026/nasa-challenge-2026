/**
 * 8 · Rotation d'une section. Owner: Ali.
 * Cycle length → one crop per year (locked when the return delay is not met)
 * → winter covers → soil health → derived number of cycles on the farm horizon.
 */
import { html, plural } from '../lib/html.js';
import { CROPS, CROP_IDS, COVERS, COVER_IDS, ROLES, SOIL_ROLES } from '../data/crops.js';
import {
  cycleLength,
  entryStart,
  lockReason,
  placeCrop,
  rotationErrors,
  setCover,
  setCycleYears,
  toSlots,
} from '../lib/rotation.js';
import { soilByCycleYear, countTrue } from '../lib/soil.js';
import { sectionLayout, pageTitle } from '../ui/layout.js';
import { icon, ICONS } from '../ui/icons.js';
import { fieldStrip, fieldSwatch } from '../ui/textures.js';
import { alertBox, roleTag } from '../ui/widgets.js';

function segments(rotation, selIndex, role) {
  const out = [];
  let i = 0;
  for (const e of rotation) {
    const span = e.years || 1;
    const start = i;
    const sel = selIndex >= start && selIndex < start + span;
    const crop = CROPS[e.crop];
    out.push(
      html`<div
        class="seg ${sel ? 'is-selected' : ''} ${crop ? '' : 'is-empty'}"
        style="flex: ${span} 1 0; ${crop ? `background: ${crop.color}` : ''}"
      >
        ${fieldStrip(e.crop, 72)}
        <button type="button" class="seg__pick" data-action="pick-slot" data-i="${start}">
          <span class="small strong muted-dark"
            >${span === 1 ? `Année ${start + 1}` : `Années ${start + 1} à ${start + span}`}</span
          ><span class="seg__name">${crop?.name ?? 'À choisir'}</span>
        </button>
        <div class="row-wrap gap-xs seg__tags">
          ${(crop?.roles ?? []).map((r) => roleTag(r, { action: 'set-role', active: role === r }))}
        </div>
        ${
          crop && span === 1
            ? html`<button
                type="button"
                class="cover-btn ${e.cover ? 'is-on' : ''}"
                data-action="cycle-cover"
                data-i="${start}"
              >
                ${icon(ICONS.umbrella, { size: 13, width: 2.2 })}${e.cover ? `Hiver : ${COVERS[e.cover].name.toLowerCase()}` : '+ Couverture d’hiver'}
              </button>`
            : crop
              ? html`<span class="small strong">Couvre déjà le sol toute l’année</span>`
              : ''
        }
      </div>`,
    );
    i += span;
  }
  return out;
}

export default {
  title: 'Rotation',
  rota: 'rotation',
  render(state, { id }, app) {
    const section = app.section(id);
    const rot = section.rotation;
    const L = cycleLength(rot);
    const slots = toSlots(rot);
    const sel = Math.min(state.ui.rotSlot, L - 1);
    const H = state.farm.farm.horizonYears;
    const cycles = Math.floor(H / L);
    const rest = H % L;
    const errors = rotationErrors(rot);
    const soil = soilByCycleYear(rot);
    const role = ROLES[state.ui.role] ? state.ui.role : 'azote';
    const tips = [];
    if (!countTrue(soil.racines))
      tips.push('Aucune racine profonde : un radis fourrager en hiver casserait le sol tassé.');
    if (!countTrue(soil.sec) && slots.some((s) => s.crop === 'mais'))
      tips.push(
        'Aucune culture qui tolère le sec : de l’orge à la place du maïs réduirait le risque les années sèches.',
      );

    const body = html` ${pageTitle(
        `Rotation de la section ${id}`,
        'Choisissez la durée, une culture par année et, si vous voulez, une couverture d’hiver.',
        html`<button
          type="button"
          class="btn btn--soft"
          data-action="propose"
          ${state.ui.proposing ? 'disabled' : ''}
        >
          ${icon(ICONS.magic, { size: 18 })}${state.ui.proposing ? 'Calcul…' : 'Laisser l’appli proposer'}
        </button>`,
      )}

      <section class="card stack-sm">
        <div class="step-head">
          <span class="step-num">1</span>
          <h2 class="h2">Durée de la rotation</h2>
        </div>
        <div class="row-wrap gap-sm">
          ${[2, 3, 4, 5, 6].map((n) => html`<button type="button" class="choice ${n === L ? 'is-on' : ''}" data-action="set-length" data-n="${n}" aria-pressed="${String(n === L)}">${n} ans</button>`)}
        </div>
      </section>

      <section class="card stack-md">
        <div class="step-head">
          <span class="step-num">2</span>
          <h2 class="h2">Une culture par année</h2>
          <span class="muted small"
            >Cliquez sur une année pour la changer · sur une étiquette pour comprendre</span
          >
        </div>
        <div class="segs">${segments(rot, sel, role)}</div>
        <div class="card card--tint stack-sm">
          <strong>Culture de l’année ${sel + 1}</strong>
          <div class="row-wrap gap-sm">
            ${CROP_IDS.map((c) => {
              const why = lockReason(rot, sel, c);
              const info = CROPS[c];
              const cur = slots[sel]?.crop === c;
              return html`<button
                type="button"
                class="crop-option ${cur ? 'is-current' : ''} ${why ? 'is-locked' : ''}"
                style="${why ? '' : `background: ${info.color}`}"
                data-action="place-crop"
                data-crop="${c}"
                ${why ? 'disabled' : ''}
                title="${why ?? `Choisir ${info.name}`}"
              >
                <span class="row gap-xs strong"
                  >${fieldSwatch(c)}${why ? icon(ICONS.lock, { size: 14, width: 2.4 }) : ''}${info.name}</span
                >
                <span class="small"
                  >${why ?? (info.years > 1 ? `occupe ${info.years} ans` : info.roles[0] ? ROLES[info.roles[0]].label.toLowerCase() : `retour après ${info.returnDelay} ans`)}</span
                >
              </button>`;
            })}
          </div>
          <span class="muted small"
            >Cadenas = la culture reviendrait avant son délai de retour. Délais à confirmer avec
            l’équipe algo.</span
          >
        </div>
        ${errors.map((e) => alertBox('warn', e))}
      </section>

      <section class="card stack-md">
        <div class="step-head">
          <span class="step-num">3</span>
          <h2 class="h2">Santé du sol de cette rotation</h2>
          <span class="muted small">Sur un cycle de ${L} ans</span>
        </div>
        <div class="grid grid--4">
          ${SOIL_ROLES.map((r) => {
            const n = countTrue(soil[r]);
            const R = ROLES[r];
            return html`<button
              type="button"
              class="soil-card ${role === r ? 'is-active' : ''}"
              data-action="set-role"
              data-role="${r}"
            >
              <span class="row gap-sm strong"
                ><span class="soil-card__icon" style="background: ${R.bg}; color: ${R.fg}"
                  >${icon(R.icon, { size: 16, width: 2.2 })}</span
                >${R.label}</span
              >
              <span class="soil-card__count">${n} ${n > 1 ? 'ans' : 'an'} sur ${L}</span>
              <span class="dots"
                >${soil[r].map((v) => html`<span style="background: ${v ? R.fg : '#E5E9E0'}"></span>`)}</span
              >
            </button>`;
          })}
        </div>
        <div class="card card--soft row-start">
          <span class="soil-card__icon" style="background: #FFFFFF; color: #2E6B3B"
            >${icon(ROLES[role].icon, { size: 18, width: 2.2 })}</span
          >
          <div class="stack-xs">
            <strong>${ROLES[role].label}</strong><span class="small">${ROLES[role].text}</span
            ><span class="muted small"
              >Les études derrière cette phrase sont dans Détail et sources.</span
            >
          </div>
        </div>
        ${tips.map((t) => alertBox('warn', t))}
      </section>

      <section class="card row-wrap align-center gap-lg">
        <div class="step-head grow-1">
          <span class="step-num">4</span>
          <h2 class="h2">Cycles sur la durée de la ferme</h2>
        </div>
        <div class="total-box grow-1">
          <span class="small">Durée totale</span
          ><strong
            >${L} ans ×
            ${plural(cycles, 'cycle', 'cycles')}${rest ? ` + ${rest} an${rest > 1 ? 's' : ''}` : ''}
            = ${H} ans</strong
          >
        </div>
        ${
          rest
            ? alertBox(
                'warn',
                `La ferme est analysée sur ${H} ans : le dernier cycle est coupé après ${rest} an${rest > 1 ? 's' : ''}.`,
              )
            : alertBox('ok', `Remplit exactement la durée d’analyse de la ferme (${H} ans).`)
        }
        <a class="small" href="#/compte">Changer la durée d’analyse</a>
      </section>

      <div class="actions-bar">
        <a class="btn btn--secondary" href="#/section/${id}/champ">Retour</a
        ><a class="btn btn--primary" href="#/section/${id}/resultats">Voir les résultats →</a>
      </div>`;
    return sectionLayout(state, section, 'rotation', body);
  },
  actions: {
    'set-length': (app, el) => {
      const id = app.state.ui.route.params.id;
      app.updateFarm((farm) => {
        const s = farm.sections.find((x) => x.id === id);
        s.rotation = setCycleYears(s.rotation, Number(el.dataset.n));
      });
      app.update((s) => (s.ui.rotSlot = Math.min(s.ui.rotSlot, Number(el.dataset.n) - 1)));
    },
    'pick-slot': (app, el) => app.update((s) => (s.ui.rotSlot = Number(el.dataset.i))),
    'place-crop': (app, el) => {
      const { id } = app.state.ui.route.params;
      const crop = el.dataset.crop;
      app.updateFarm((farm, s) => {
        const sec = farm.sections.find((x) => x.id === id);
        sec.rotation = placeCrop(sec.rotation, s.ui.rotSlot, crop);
        s.ui.rotSlot = entryStart(sec.rotation, s.ui.rotSlot);
        if (CROPS[crop].roles[0] && CROPS[crop].roles[0] !== 'gourmand')
          s.ui.role = CROPS[crop].roles[0];
      });
    },
    'cycle-cover': (app, el) => {
      const { id } = app.state.ui.route.params;
      const i = Number(el.dataset.i);
      app.updateFarm((farm, s) => {
        const sec = farm.sections.find((x) => x.id === id);
        const cur = toSlots(sec.rotation)[i].cover;
        const order = [null, ...COVER_IDS];
        const next = order[(order.indexOf(cur) + 1) % order.length];
        sec.rotation = setCover(sec.rotation, i, next);
        if (next) {
          const roles = COVERS[next].roles;
          s.ui.role = roles.includes('racines')
            ? 'racines'
            : roles.includes('azote')
              ? 'azote'
              : 'couverture';
        }
      });
    },
    propose: (app) => {
      const { id } = app.state.ui.route.params;
      app.proposeRotation(id, cycleLength(app.section(id).rotation));
    },
  },
};
