/**
 * Pieces of UI that show the plan of the algorithm: decision, chain, calendar,
 * criteria, status of the plan and where its data come from.
 */
import { html } from '../lib/html.js';
import { CRITERIA, CRITERIA_IDS } from '../../data/reference/criteria.js';
import { CROPS, colorOf, nameOf } from '../../data/reference/crops.js';
import { MONTH_NAMES } from '../../data/reference/calendar.js';
import { alertBox } from './widgets.js';
import { fieldSwatch } from './textures.js';

const PERCENT = 100;

/** Year shown on the screens: the one chosen, kept inside the plan. */
export function selectedYear(state, years) {
  const fallback = new Date().getFullYear() + 1;
  if (!years) return state.ui.year ?? fallback;
  return Math.min(years.last, Math.max(years.first, state.ui.year ?? years.first));
}

export function decisionPill(decision) {
  if (decision === 'garder') return html`<span class="pill pill--info">✓ Garder</span>`;
  if (decision === 'changer') return html`<span class="pill pill--warn">↻ Changer</span>`;
  return html`<span class="pill pill--bad">⚠ Aucune suite possible</span>`;
}

/** "mai 2028" from "2028-05-12". */
export function monthLabel(iso) {
  if (!iso) return '—';
  const [year, month] = iso.split('-').map(Number);
  return `${MONTH_NAMES[month - 1]} ${year}`;
}

/** "~23 avr." from { month, day }. */
export const dayLabel = (d) => (d ? `~${d.day} ${MONTH_NAMES[d.month - 1]}` : 'aucun');

/** Inputs missing, plan refreshing, data that are examples. */
export function planStatus(state) {
  const plan = state.plan;
  const parts = [];
  if (plan.status === 'incomplete') parts.push(alertBox('warn', plan.error));
  if (plan.status === 'refreshing')
    parts.push(html`<span class="muted small" role="status">Mise à jour du plan…</span>`);
  const sources = plan.data?.meta?.sources;
  if (sources) {
    const fake = Object.values(sources).filter((s) => !s.real);
    const real = Object.values(sources).filter((s) => s.real);
    if (fake.length)
      parts.push(
        html`<div class="card card--soft small stack-xs">
          <strong>D’où viennent les chiffres</strong>
          ${real.map((s) => html`<span>✓ ${s.label}</span>`)}
          ${fake.map((s) => html`<span>⚠ ${s.label}</span>`)}
        </div>`,
      );
  }
  return parts;
}

/** A chain as coloured chips, with the covers sown between two crops. */
export function chainChips(chain) {
  return html`<div class="chain">
    ${chain.steps.map((s) => {
      if (s.kind === 'couvert')
        return html`<span class="chain__cover" title="Couvert semé ${monthLabel(s.sowing)}"
          >+ ${CROPS[s.crop].name.toLowerCase()}</span
        >`;
      const span = s.positions[1] - s.positions[0] + 1;
      return html`<span
        class="chain__step ${s.kind === 'jachere' ? 'is-fallow' : ''}"
        style="flex: ${span} 1 0; background: ${colorOf(s.sheet)}"
        >${fieldSwatch(s.sheet, 14)}${nameOf(s.sheet)}${span > 1 ? html`<small> · ${span} pos.</small>` : ''}</span
      >`;
    })}
  </div>`;
}

/** Sowing and harvest of every step. */
export function calendarTable(chain) {
  return html`<div class="table-wrap">
    <table class="table">
      <thead>
        <tr>
          <th>Position</th>
          <th>Culture</th>
          <th>Semis</th>
          <th>Récolte ou fin</th>
        </tr>
      </thead>
      <tbody>
        ${chain.steps.map(
          (s) =>
            html`<tr class="${s.kind === 'couvert' ? 'is-cover' : ''}">
              <td>
                ${s.positions ? (s.positions[0] === s.positions[1] ? s.positions[0] : `${s.positions[0]}–${s.positions[1]}`) : 'entre deux'}
              </td>
              <td class="strong">
                ${nameOf(s.sheet)}${s.kind === 'jachere' ? ' (sol au repos)' : ''}
              </td>
              <td>${s.kind === 'jachere' ? '—' : monthLabel(s.sowing)}</td>
              <td>${s.kind === 'jachere' ? '—' : monthLabel(s.harvest)}</td>
            </tr>`,
        )}
      </tbody>
    </table>
  </div>`;
}

/** The 9 criteria of the chosen chain, with the current rotation as a marker. */
export function criteriaBars(chain, reference, weights) {
  const order = [...CRITERIA_IDS].sort((a, b) => (weights?.[b] ?? 0) - (weights?.[a] ?? 0));
  return html`<div class="stack-sm">
    ${order.map((c) => {
      const v = chain.criteria[c];
      const r = reference?.criteria[c];
      return html`<div class="score">
        <div class="score__row">
          <span class="score__label" title="${CRITERIA[c].text}">${CRITERIA[c].label}</span>
          <span
            ><strong
              >${v === null || v === undefined ? 'inconnu' : Math.round(v * PERCENT)}</strong
            ></span
          >
        </div>
        <div class="score__track">
          <div class="score__fill" style="width: ${(v ?? 0) * PERCENT}%"></div>
          ${r !== null && r !== undefined ? html`<div class="score__ref" style="left: calc(${r * PERCENT}% - 1px)"></div>` : ''}
        </div>
      </div>`;
    })}
    <span class="muted small"
      >Classés par poids pour cette parcelle · trait noir = votre rotation actuelle</span
    >
  </div>`;
}

/** Cycle tabs of a section plan. */
export function cycleTabs(sectionPlan, current) {
  return html`<div class="segmented segmented--inline" role="tablist" aria-label="Cycles">
    ${sectionPlan.cycles.map(
      (c) =>
        html`<button
          type="button"
          role="tab"
          class="${c.index === current ? 'is-on' : ''}"
          aria-selected="${String(c.index === current)}"
          data-action="set-cycle"
          data-cycle="${c.index}"
        >
          Cycle ${c.index} · ${c.years[0]}–${c.years[1]}
        </button>`,
    )}
  </div>`;
}

/** The cycle shown on a section screen (kept inside the plan). */
export const selectedCycle = (sectionPlan, state) =>
  sectionPlan?.cycles.find((c) => c.index === state.ui.cycle) ?? sectionPlan?.cycles[0] ?? null;
