/**
 * Step 1, block C: cycle (2 to 6 years), then frequency (only those that divide
 * the cycle), then horizon (C, 2C, 3C… up to 2060). Shared by the onboarding
 * (screens/temps.js) and the settings (screens/compte.js).
 */
import { html } from '../lib/html.js';
import { CYCLE_YEARS } from '../../data/reference/planning.js';
import {
  TimeSettings,
  allowedFrequencies,
  allowedHorizons,
  nearestHorizon,
} from '../../application/rules/timeSettings.js';

const nextYear = () => new Date().getFullYear() + 1;
const range = (from, to) => Array.from({ length: to - from + 1 }, (_, i) => from + i);

export function timeSettingsEditor(state) {
  const time = state.farm.farm.time;
  const positions = new TimeSettings(time).positionsPerCycle;
  const start = nextYear();
  return html`<div class="stack-md">
    <div class="stack-xs">
      <strong>Durée du cycle</strong>
      <div class="row-wrap gap-sm">
        ${range(CYCLE_YEARS.min, CYCLE_YEARS.max).map(
          (n) =>
            html`<button
              type="button"
              class="choice ${n === time.cycleYears ? 'is-on' : ''}"
              data-action="set-cycle-years"
              data-n="${n}"
              aria-pressed="${String(n === time.cycleYears)}"
            >
              ${n} ans
            </button>`,
        )}
      </div>
    </div>
    <div class="stack-xs">
      <strong>Une culture tous les…</strong>
      <div class="row-wrap gap-sm">
        ${allowedFrequencies(time.cycleYears).map(
          (f) =>
            html`<button
              type="button"
              class="choice ${f.months === time.frequencyMonths ? 'is-on' : ''}"
              data-action="set-frequency"
              data-n="${f.months}"
              aria-pressed="${String(f.months === time.frequencyMonths)}"
            >
              ${f.months} mois · ${f.label}
            </button>`,
        )}
      </div>
      <span class="muted small">${positions} positions par cycle</span>
    </div>
    <label class="field field--narrow"
      >Horizon
      <select data-change="set-horizon">
        ${allowedHorizons(time.cycleYears, start).map(
          (h) =>
            html`<option value="${h}" ${h === time.horizonYears ? 'selected' : ''}>
              ${h} ans · ${h / time.cycleYears} cycle${h / time.cycleYears > 1 ? 's' : ''} (jusqu’en
              ${start + h - 1} environ)
            </option>`,
        )}
      </select>
    </label>
  </div>`;
}

export const timeActions = {
  'set-cycle-years': (app, el) =>
    app.updateFarm((farm) => {
      const cycleYears = Number(el.dataset.n);
      const t = farm.farm.time;
      const frequencyMonths = allowedFrequencies(cycleYears).some(
        (f) => f.months === t.frequencyMonths,
      )
        ? t.frequencyMonths
        : allowedFrequencies(cycleYears)[0].months;
      farm.farm.time = {
        cycleYears,
        frequencyMonths,
        horizonYears: nearestHorizon(cycleYears, t.horizonYears, nextYear()),
      };
    }),
  'set-frequency': (app, el) =>
    app.updateFarm((farm) => {
      farm.farm.time = { ...farm.farm.time, frequencyMonths: Number(el.dataset.n) };
    }),
  'set-horizon': (app, el) =>
    app.updateFarm((farm) => {
      farm.farm.time = { ...farm.farm.time, horizonYears: Number(el.value) };
    }),
};
