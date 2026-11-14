/**
 * "What grows now" + "my seed reserve", shared by the onboarding step
 * (screens/cultures.js) and the settings (screens/compte.js).
 *
 * Choosing a current crop adds it to the reserve: if it grows on the farm, the
 * farmer can get its seeds. Everything stays editable.
 */
import { html, plural } from '../lib/html.js';
import { CROPS, CROP_IDS, COVERS, COVER_IDS, ROLES } from '../data/crops.js';
import { addSeeds, getSeeds } from '../lib/seeds.js';
import { cycleLength, suggestCycleYears, toSlots } from '../lib/rotation.js';
import { fieldSwatch } from './textures.js';
import { icon, ICONS } from './icons.js';

export function currentCropsEditor(state) {
  const year = state.farm.farm.startYear - 1;
  return html`<div class="stack-xs">
    ${state.farm.sections.map(
      (s) =>
        html`<div class="now-row">
          <span class="row gap-sm now-row__who"
            ><span class="section-badge">${s.id}</span
            ><span class="stack-0"
              ><strong>Section ${s.id}</strong><span class="muted small">${s.areaHa} ha</span></span
            ></span
          >
          <div
            class="now-row__opts"
            role="radiogroup"
            aria-label="Culture en ${year} sur la section ${s.id}"
          >
            ${CROP_IDS.map((c) => {
              const on = s.currentCrop === c;
              return html`<button
                type="button"
                role="radio"
                aria-checked="${String(on)}"
                class="now-chip ${on ? 'is-on' : ''}"
                style="${on ? `background: ${CROPS[c].color}` : ''}"
                data-action="set-current-crop"
                data-id="${s.id}"
                data-crop="${c}"
              >
                ${fieldSwatch(c, 16)}${CROPS[c].name}
              </button>`;
            })}
            <button
              type="button"
              role="radio"
              aria-checked="${String(!s.currentCrop)}"
              class="now-chip now-chip--none ${s.currentCrop ? '' : 'is-on'}"
              data-action="set-current-crop"
              data-id="${s.id}"
              data-crop=""
            >
              Rien / je ne sais pas
            </button>
          </div>
        </div>`,
    )}
  </div>`;
}

export function seedBank(state) {
  const seeds = getSeeds(state.farm);
  const growing = new Set(state.farm.sections.map((s) => s.currentCrop).filter(Boolean));
  const only = seeds.crops.length === 1;
  return html`<div class="stack-sm">
    <div class="seed-grid">
      ${CROP_IDS.map((c) => {
        const info = CROPS[c];
        const on = seeds.crops.includes(c);
        const role = info.roles[0]
          ? ROLES[info.roles[0]].label
          : `retour après ${info.returnDelay} ans`;
        return html`<button
          type="button"
          class="seed-card ${on ? 'is-on' : ''}"
          aria-pressed="${String(on)}"
          data-action="toggle-seed"
          data-crop="${c}"
          ${on && only ? 'disabled' : ''}
          title="${on && only ? 'Gardez au moins une culture' : `${on ? 'Retirer' : 'Ajouter'} ${info.name}`}"
        >
          <span class="seed-card__swatch">${fieldSwatch(c, 40)}</span>
          <span class="stack-0 grow">
            <strong>${info.name}</strong>
            <span class="muted small">${info.years > 1 ? `occupe ${info.years} ans` : role}</span>
          </span>
          ${growing.has(c) ? html`<span class="pill pill--ok">en culture</span>` : ''}
          <span class="seed-card__check" aria-hidden="true"
            >${on ? icon(ICONS.check, { size: 16, width: 3 }) : ''}</span
          >
        </button>`;
      })}
    </div>
    <div class="stack-xs">
      <span class="eyebrow">Couvertures d’hiver</span>
      <div class="row-wrap gap-sm">
        ${COVER_IDS.map((c) => {
          const on = seeds.covers.includes(c);
          return html`<button
            type="button"
            class="now-chip ${on ? 'is-on is-cover' : ''}"
            aria-pressed="${String(on)}"
            data-action="toggle-cover-seed"
            data-cover="${c}"
          >
            ${icon(ICONS.umbrella, { size: 14, width: 2.2 })}${COVERS[c].name}
          </button>`;
        })}
      </div>
    </div>
  </div>`;
}

/** Summary + "propose with my seeds" for the whole farm. */
export function proposeAllCard(state) {
  const seeds = getSeeds(state.farm);
  const years = suggestCycleYears(seeds.crops);
  const p = state.ui.proposeAll;
  const busy = p.status === 'loading';
  return html`<div class="card stack-sm">
    <div class="row-between wrap">
      <div class="stack-0">
        <strong>Rotations de départ</strong>
        <span class="muted small"
          >L’appli construit une rotation de ${years} ans par section avec vos
          ${plural(seeds.crops.length, 'culture', 'cultures')}, en tenant compte de ce qui pousse
          maintenant.</span
        >
      </div>
      <button
        type="button"
        class="btn btn--primary"
        data-action="propose-all"
        ${busy ? 'disabled' : ''}
      >
        ${icon(ICONS.magic, { size: 18 })}${busy ? 'Calcul…' : 'Proposer avec mes semences'}
      </button>
    </div>
    ${p.status === 'error' ? html`<div class="alert alert--bad small">⚠ ${p.error}</div>` : ''}
    ${
      p.missing.length
        ? html`<div class="alert alert--warn small row-between wrap">
            <span
              >⚠ Il manque des semences de
              ${p.missing.map((c) => CROPS[c].name.toLowerCase()).join(', ')} pour respecter les
              délais de retour.</span
            >
            <button
              type="button"
              class="btn btn--secondary btn--sm"
              data-action="add-seeds"
              data-crops="${p.missing.join(',')}"
            >
              Ajouter à ma réserve
            </button>
          </div>`
        : ''
    }
    <div class="stack-xs">
      ${state.farm.sections.map((s) => {
        const slots = toSlots(s.rotation);
        return html`<div class="rot-preview">
          <span class="section-badge">${s.id}</span>
          <span class="rot-preview__chips">
            ${slots.map(
              (x) =>
                html`<span
                  class="rot-chip ${seeds.crops.includes(x.crop) ? '' : 'is-missing'}"
                  style="background: ${CROPS[x.crop]?.color ?? '#E5E9E0'}"
                  >${CROPS[x.crop]?.name ?? '—'}</span
                >`,
            )}
          </span>
          <span class="muted small nowrap">${cycleLength(s.rotation)} ans</span>
        </div>`;
      })}
    </div>
    <span class="muted small">Tout reste modifiable ensuite, section par section.</span>
  </div>`;
}

const toggle = (list, v) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);

export const seedActions = {
  'set-current-crop': (app, el) => {
    const crop = el.dataset.crop || null;
    app.updateFarm((farm) => {
      const sec = farm.sections.find((x) => x.id === el.dataset.id);
      if (!sec) return;
      sec.currentCrop = crop;
      if (crop) addSeeds(farm, [crop]);
    });
  },
  'toggle-seed': (app, el) =>
    app.updateFarm((farm) => {
      const seeds = getSeeds(farm);
      const crops = toggle(seeds.crops, el.dataset.crop);
      if (!crops.length) return;
      farm.farm.seeds = { crops: CROP_IDS.filter((c) => crops.includes(c)), covers: seeds.covers };
    }),
  'toggle-cover-seed': (app, el) =>
    app.updateFarm((farm) => {
      const seeds = getSeeds(farm);
      const covers = toggle(seeds.covers, el.dataset.cover);
      farm.farm.seeds = { crops: seeds.crops, covers: COVER_IDS.filter((c) => covers.includes(c)) };
    }),
  'add-seeds': (app, el) => {
    app.updateFarm((farm) => addSeeds(farm, el.dataset.crops.split(',').filter(Boolean)));
    app.update((s) => {
      s.ui.proposeAll.missing = [];
      if (s.ui.proposal) s.ui.proposal.missingSeeds = [];
    });
  },
  'propose-all': (app) => app.proposeAll(),
};
