/**
 * Pieces of UI that show the plan of the algorithm: decision, the four priorities, status of the
 * plan and where its data come from. The rotations themselves are drawn by rotationViews.js.
 */
import { html } from '../lib/html.js';
import { CRITERIA, CRITERIA_IDS } from '../../data/reference/criteria.js';
import { formatDate, t } from '../../data/i18n/index.js';
import { alertBox, busyDots } from './widgets.js';

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
  return html`<span class="pill pill--bad">⚠ Aucune rotation possible</span>`;
}

/** "~23 avr." from { month, day }. */
export const dayLabel = (d) =>
  d
    ? `~${formatDate(new Date(Date.UTC(2000, d.month - 1, d.day)), { month: 'short', day: 'numeric' })}`
    : t('aucun');

/** Inputs missing, plan refreshing, data that are examples. */
export function planStatus(state) {
  const plan = state.plan;
  const parts = [];
  if (plan.status === 'incomplete') parts.push(alertBox('warn', plan.error));
  if (plan.status === 'refreshing') parts.push(busyDots('Mise à jour du plan'));
  const sources = plan.data?.meta?.sources;
  if (sources) {
    const fake = Object.values(sources).filter((s) => !s.real);
    if (fake.length)
      parts.push(
        html`<div class="card card--soft small stack-xs">
          <strong>Données d’exemple</strong>
          ${fake.map((s) => html`<span>⚠ ${s.label}</span>`)}
        </div>`,
      );
  }
  return parts;
}

/** Priorities by weight for this parcel, the heaviest first. */
const byWeight = (weights) =>
  [...CRITERIA_IDS].sort((a, b) => (weights?.[b] ?? 0) - (weights?.[a] ?? 0));

/** The 4 priorities of a chain, with the current rotation as a marker. */
export function criteriaBars(chain, reference, weights) {
  return html`<div class="stack-sm">
    ${byWeight(weights).map((c) => {
      const v = chain.criteria[c];
      const r = reference?.criteria[c];
      return html`<div class="score">
        <div class="score__row">
          <span class="score__label">${CRITERIA[c].label}</span>
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
  </div>`;
}

/** The 4 priorities of a chain in four small bars (the cards that compare the rotations). */
export function criteriaMini(chain, weights) {
  return html`<div class="mini-bars">
    ${byWeight(weights).map((c) => {
      const v = chain.criteria[c];
      const known = v !== null && v !== undefined;
      return html`<div class="mini-bar" title="${CRITERIA[c].label}">
        <span class="mini-bar__label">${CRITERIA[c].short}</span>
        <span class="mini-bar__track"
          ><span class="mini-bar__fill" style="width: ${known ? v * PERCENT : 0}%"></span
        ></span>
        <span class="mini-bar__value">${known ? Math.round(v * PERCENT) : '?'}</span>
      </div>`;
    })}
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
