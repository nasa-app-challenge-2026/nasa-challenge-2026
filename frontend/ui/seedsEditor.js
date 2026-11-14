/**
 * The farmer's inputs that the algorithm needs (step 1), shared by the onboarding
 * (screens/cultures.js), the section screen (screens/parcelle.js) and the settings
 * (screens/compte.js): the crop in place and its harvest month, the current
 * rotation and where the field is in it, the previous years, the seed reserve.
 */
import { html } from '../lib/html.js';
import {
  CROPS,
  OTHER_CROP_IDS,
  SEED_IDS,
  SHEETS,
  SOLD_SHEET_IDS,
  DEFAULT_HARVEST_MONTH,
  colorOf,
  nameOf,
} from '../../data/reference/crops.js';
import { RESERVE_MODES } from '../../data/reference/planning.js';
import { SOIL_DISEASES } from '../../data/reference/diseases.js';
import { getSeeds, setReserveMode, toggleSeed } from '../../application/rules/seeds.js';
import {
  addToRotation,
  historyCropOf,
  historyYearsToAsk,
  moveInRotation,
  removeFromRotation,
  setCurrentCrop,
  setHistoryCrop,
  toggleDisease,
} from '../../application/rules/sectionInputs.js';
import { fieldSwatch } from './textures.js';
import { icon, ICONS } from './icons.js';

/** Month (1–12) a sheet is usually harvested, to prefill the harvest month of the crop in place. */
const usualHarvestMonth = (id) => SHEETS[id]?.usualHarvestMonth ?? DEFAULT_HARVEST_MONTH;
const thisYear = () => new Date().getFullYear();

const option = (value, label, selected) =>
  html`<option value="${value}" ${selected ? 'selected' : ''}>${label}</option>`;

function cropSelect({ id, value, action, sectionId, extra = '', emptyLabel, sheetsOnly = false }) {
  const sold = SOLD_SHEET_IDS;
  const others = OTHER_CROP_IDS;
  return html`<select id="${id}" data-change="${action}" data-id="${sectionId}" ${extra}>
    ${option('', emptyLabel, !value)}
    <optgroup label="Cultures de l’algorithme">
      ${sold.map((c) => option(c, nameOf(c), value === c))}
    </optgroup>
    ${
      sheetsOnly
        ? ''
        : html`<optgroup label="Autres cultures">
            ${others.map((c) => option(c, CROPS[c].name, value === c))}
          </optgroup>`
    }
  </select>`;
}

/** Crop in place + harvest month + current rotation of one section. */
export function inPlaceEditor(section) {
  const id = section.id;
  const rotation = section.currentRotation ?? [];
  return html`<div class="stack-sm">
    <div class="grid grid--2">
      <label class="field"
        >Culture en place
        ${cropSelect({
          id: `now-${id}`,
          value: section.currentCrop,
          action: 'set-current-crop',
          sectionId: id,
          emptyLabel: 'Rien (parcelle libre)',
        })}
      </label>
      <label class="field"
        >Récolte prévue (ou fin pour une prairie)
        <input
          id="harvest-${id}"
          type="month"
          value="${section.currentHarvest ?? ''}"
          data-change="set-harvest"
          data-id="${id}"
          ${section.currentCrop ? '' : 'disabled'}
        />
      </label>
    </div>
    <div class="stack-xs">
      <span class="strong small">Ma rotation actuelle</span>
      <span class="muted small"
        >La suite de cultures que vous suivez. Elle sert de référence : l’appli la compare à ses
        propositions. Cochez la culture en place.</span
      >
      <div class="row-wrap gap-xs" role="list">
        ${rotation.map(
          (sheet, i) =>
            html`<span
              class="rot-edit ${i === section.rotationPosition ? 'is-now' : ''}"
              role="listitem"
            >
              <button
                type="button"
                class="rot-edit__pick"
                style="background: ${colorOf(sheet)}"
                data-action="set-position"
                data-id="${id}"
                data-i="${i}"
                aria-pressed="${String(i === section.rotationPosition)}"
                title="C’est la culture en place"
              >
                ${i === section.rotationPosition ? '● ' : ''}${nameOf(sheet)}
              </button>
              <button
                type="button"
                class="icon-btn icon-btn--sm"
                data-action="move-rotation"
                data-id="${id}"
                data-i="${i}"
                data-d="-1"
                aria-label="Avancer ${nameOf(sheet)}"
                ${i === 0 ? 'disabled' : ''}
              >
                ${icon(ICONS.up, { size: 14 })}
              </button>
              <button
                type="button"
                class="icon-btn icon-btn--sm"
                data-action="remove-rotation"
                data-id="${id}"
                data-i="${i}"
                aria-label="Retirer ${nameOf(sheet)}"
              >
                ${icon(ICONS.close, { size: 14 })}
              </button>
            </span>`,
        )}
        ${cropSelect({
          id: `add-${id}`,
          value: null,
          action: 'add-rotation',
          sectionId: id,
          emptyLabel: '+ Ajouter une culture',
          sheetsOnly: true,
        })}
      </div>
    </div>
  </div>`;
}

/** The previous years of one section (as many as the return delays need). */
export function historyEditor(section, { currentYear, years }) {
  return html`<div class="row-wrap gap-sm">
    ${historyYearsToAsk(section, currentYear, years).map(
      (year) =>
        html`<label class="field field--narrow"
          >${year}
          <select
            id="hist-${section.id}-${year}"
            data-change="set-history"
            data-id="${section.id}"
            data-year="${year}"
          >
            ${option('', '—', !historyCropOf(section, year))}
            ${[...SEED_IDS, ...OTHER_CROP_IDS].map((c) => option(c, CROPS[c].name, historyCropOf(section, year) === c))}
          </select>
        </label>`,
    )}
  </div>`;
}

/** Soil diseases the farmer knows on the section. */
export function diseasesEditor(section) {
  return html`<div class="row-wrap gap-xs">
    ${Object.entries(SOIL_DISEASES).map(([id, d]) => {
      const on = section.diseases.includes(id);
      return html`<button
        type="button"
        class="now-chip ${on ? 'is-on' : ''}"
        aria-pressed="${String(on)}"
        data-action="toggle-disease"
        data-id="${section.id}"
        data-disease="${id}"
        title="${d.latin}"
      >
        ${d.name}
      </button>`;
    })}
  </div>`;
}

/** The seed reserve: seeds owned (no quantities) and the reserve mode. */
export function seedBank(state) {
  const seeds = getSeeds(state.farm);
  return html`<div class="stack-sm">
    <div class="seed-grid">
      ${SEED_IDS.map((c) => {
        const on = seeds.crops.includes(c);
        return html`<button
          type="button"
          class="seed-card ${on ? 'is-on' : ''}"
          aria-pressed="${String(on)}"
          data-action="toggle-seed"
          data-crop="${c}"
          title="${on ? 'Retirer' : 'Ajouter'} ${CROPS[c].name}"
        >
          <span class="seed-card__swatch">${fieldSwatch(c, 40)}</span>
          <span class="stack-0 grow"><strong>${CROPS[c].name}</strong></span>
          <span class="seed-card__check" aria-hidden="true"
            >${on ? icon(ICONS.check, { size: 16, width: 3 }) : ''}</span
          >
        </button>`;
      })}
    </div>
    <div class="segmented segmented--inline" role="group" aria-label="Mode de la réserve">
      ${Object.entries(RESERVE_MODES).map(
        ([mode, m]) =>
          html`<button
            type="button"
            class="${seeds.mode === mode ? 'is-on' : ''}"
            data-action="set-reserve-mode"
            data-mode="${mode}"
            aria-pressed="${String(seeds.mode === mode)}"
            title="${m.text}"
          >
            ${m.label}
          </button>`,
      )}
    </div>
    <span class="muted small">${RESERVE_MODES[seeds.mode].text}</span>
  </div>`;
}

const onSection = (app, el, fn) => app.updateSection(el.dataset.id, fn);

export const seedActions = {
  'set-current-crop': (app, el) =>
    onSection(app, el, (s) => {
      const crop = el.value || null;
      setCurrentCrop(
        s,
        crop,
        crop ? `${thisYear()}-${String(usualHarvestMonth(crop)).padStart(2, '0')}` : null,
      );
    }),
  'set-harvest': (app, el) => onSection(app, el, (s) => (s.currentHarvest = el.value || null)),
  'add-rotation': (app, el) => el.value && onSection(app, el, (s) => addToRotation(s, el.value)),
  'remove-rotation': (app, el) =>
    onSection(app, el, (s) => removeFromRotation(s, Number(el.dataset.i))),
  'move-rotation': (app, el) =>
    onSection(app, el, (s) => moveInRotation(s, Number(el.dataset.i), Number(el.dataset.d))),
  'set-position': (app, el) =>
    onSection(app, el, (s) => {
      s.rotationPosition = Number(el.dataset.i);
      if (!s.currentCrop) s.currentCrop = s.currentRotation[s.rotationPosition];
    }),
  'set-history': (app, el) =>
    onSection(app, el, (s) => setHistoryCrop(s, Number(el.dataset.year), el.value || null)),
  'toggle-disease': (app, el) => onSection(app, el, (s) => toggleDisease(s, el.dataset.disease)),
  'toggle-seed': (app, el) => app.updateFarm((farm) => toggleSeed(farm, el.dataset.crop)),
  'set-reserve-mode': (app, el) => app.updateFarm((farm) => setReserveMode(farm, el.dataset.mode)),
};
