/**
 * 10 · Plan par cycle. Owner: Justin. For each cycle (step 10 of the algorithm), the rotations
 * the algorithm proposes, side by side: the one it recommends and its two best alternatives,
 * each as a wheel with its crops and its four priorities, and the farmer's current rotation to
 * compare. Touching one shows its detail: the crops with their dates, the four priorities, the
 * water, the pests and what to know (seeds to buy, successions not measured, alerts).
 *
 * The screen explains nothing itself: the « Demander à Rota » buttons do.
 */
import { html, plural } from '../lib/html.js';
import { CROPS, nameOf } from '../../data/reference/crops.js';
import {
  REFERENCE_OPTION,
  proposedRotations,
  shownRotation,
} from '../../application/rules/planView.js';
import { sectionLayout, pageTitle } from '../ui/layout.js';
import { alertBox, errorBox, loading } from '../ui/widgets.js';
import { askRota, askRotaIcon } from '../ui/rota.js';
import {
  criteriaBars,
  criteriaMini,
  cycleTabs,
  decisionPill,
  planStatus,
  selectedCycle,
} from '../ui/planWidgets.js';
import {
  rotationLegend,
  rotationStrip,
  rotationText,
  rotationTimeline,
  rotationWheel,
} from '../ui/rotationViews.js';

const PERCENT = 100;
/** Sentences of the pests model shown for a rotation (the most exposed crops first). */
const MAX_PEST_SENTENCES = 3;
const REFERENCE = REFERENCE_OPTION;

const NO_ROTATION =
  'Aucune rotation ne respecte toutes les contraintes pour ce cycle. Essayez un cycle plus long ou plus de semences.';

const score = (chain) => Math.round(chain.score);
const mmPerYear = (v) => `${Math.round(v)} mm par an`;

const optionTitle = (id) => (id === REFERENCE ? 'Votre rotation actuelle' : `Rotation ${id + 1}`);

/** One proposed rotation: its wheel, its crops, its four priorities. */
function rotationCard(chain, id, { cycle, selected, frequencyMonths, positions }) {
  return html`<article class="rot-card ${selected ? 'is-selected' : ''}">
    <button
      type="button"
      class="rot-card__hit"
      data-action="set-option"
      data-option="${id}"
      aria-pressed="${String(selected)}"
      aria-label="${optionTitle(id)} : ${rotationText(chain)}"
    ></button>
    <header class="rot-card__head">
      <strong>${optionTitle(id)}</strong>
      ${id === 0 ? html`<span class="pill pill--ok">★ Recommandée</span>` : ''}
    </header>
    <div class="rot-card__wheel">${rotationWheel(chain, { positions })}</div>
    ${rotationLegend(chain, cycle, frequencyMonths)} ${criteriaMini(chain, cycle.weights)}
  </article>`;
}

/** The farmer's current rotation, to compare with the proposals. */
function referenceRow(cycle, { selected, frequencyMonths }) {
  const reference = cycle.reference;
  if (!reference) return '';
  const delta = cycle.chosen ? score(cycle.chosen) - score(reference) : null;
  const alerts = cycle.referenceAlerts.length;
  return html`<article class="rot-ref ${selected ? 'is-selected' : ''}">
    <button
      type="button"
      class="rot-card__hit"
      data-action="set-option"
      data-option="${REFERENCE}"
      aria-pressed="${String(selected)}"
      aria-label="${optionTitle(REFERENCE)} : ${rotationText(reference)}"
    ></button>
    <span class="stack-0 rot-ref__title">
      <strong>${optionTitle(REFERENCE)}</strong>
      <span class="muted small"
        >${score(reference)} sur
        100${delta === null ? '' : ` · rotation 1 : ${delta >= 0 ? '+' : ''}${delta}`}</span
      >
    </span>
    ${rotationStrip(reference, cycle, frequencyMonths)}
    ${alerts ? html`<span class="pill pill--warn">⚠ ${plural(alerts, 'alerte', 'alertes')}</span>` : ''}
  </article>`;
}

/** The water of a rotation in plain numbers (water_use). */
function waterBlock(chain) {
  const w = chain.water;
  if (!w) return '';
  const facts = [
    ['Demande', mmPerYear(w.demandMmPerYear)],
    ['Manque', mmPerYear(w.shortfallMmPerYear)],
    ...(w.irrigationMmPerYear === null ? [] : [['Irrigation', mmPerYear(w.irrigationMmPerYear)]]),
    ['Pluie gardée', `${Math.round(w.rainKeptPct)} %`],
  ];
  return html`<div class="stack-xs">
    <div class="row-between">
      <h3 class="h3">Eau · ${Math.round(w.note * PERCENT)} sur 100</h3>
      ${askRotaIcon('eau-suite')}
    </div>
    <div class="facts">
      ${facts.map(
        ([label, value]) =>
          html`<div class="stack-0">
            <span class="muted small">${label}</span><strong>${value}</strong>
          </div>`,
      )}
    </div>
    ${w.alerts.map((a) => alertBox('warn', a))}
  </div>`;
}

/** The pests of a rotation: the most exposed crops (the team's pests model). */
function pestsBlock(chain) {
  const p = chain.pests;
  if (!p) return '';
  return html`<div class="stack-xs">
    <div class="row-between">
      <h3 class="h3">Ravageurs · ${Math.round(p.score * PERCENT)} sur 100</h3>
      ${askRotaIcon('ravageurs-suite')}
    </div>
    ${
      p.sentences.length
        ? html`<ul class="plain-list small">
            ${p.sentences.slice(0, MAX_PEST_SENTENCES).map((s) => html`<li>${s}</li>`)}
          </ul>`
        : html`<span class="small">Aucune culture exposée.</span>`
    }
    ${
      p.cropsWithoutData.length
        ? html`<span class="muted small"
            >Sans donnée :
            ${p.cropsWithoutData.map((c) => nameOf(c).toLowerCase()).join(', ')}</span
          >`
        : ''
    }
  </div>`;
}

/** What to know about the rotation shown: gaps, seeds to buy, warnings, alerts. */
function notices(cycle, chain, id) {
  const list = [];
  if (chain.gaps.length)
    list.push(
      alertBox(
        'warn',
        `Précédent pas mesuré : ${chain.gaps.map((g) => g.message).join(', ')}.`,
        askRotaIcon('precedent'),
      ),
    );
  if (chain.seedsToBuy.length)
    list.push(
      alertBox(
        'warn',
        `Semences à se procurer : ${chain.seedsToBuy.map((s) => CROPS[s]?.name ?? s).join(', ')}.`,
      ),
    );
  list.push(...chain.warnings.map((w) => alertBox('warn', w.message)));
  if (id === REFERENCE) list.push(...cycle.referenceAlerts.map((a) => alertBox('warn', a.message)));
  return list;
}

/** The rotation the farmer touched, in detail. */
function rotationDetail(cycle, chain, id, frequencyMonths) {
  const isReference = id === REFERENCE;
  return html`<section class="card stack-md" aria-live="polite">
    <div class="row-between wrap">
      <h2 class="h2">${optionTitle(id)} · ${score(chain)} sur 100</h2>
      ${askRota('calendrier')}
    </div>
    ${rotationTimeline(chain, cycle, frequencyMonths)} ${notices(cycle, chain, id)}
    <div class="detail-grid">
      <div class="stack-sm">
        <div class="row-between">
          <h3 class="h3">Les 4 priorités</h3>
          ${askRotaIcon('barres-priorites')}
        </div>
        ${criteriaBars(chain, isReference ? null : cycle.reference, cycle.weights)}
      </div>
      <div class="stack-md">${waterBlock(chain)}${pestsBlock(chain)}</div>
    </div>
  </section>`;
}

/** Robustness of the chain adopted: its worst score in the cycles that follow. */
function robustnessChip(cycle) {
  const text = cycle.becomesInfeasibleLater
    ? 'Robustesse : devient infaisable plus tard'
    : cycle.robustness === null
      ? null
      : `Robustesse : ${Math.round(cycle.robustness)} sur 100`;
  return text ? html`<span class="chip">${text}${askRotaIcon('robustesse')}</span>` : '';
}

/** What the whole cycle says, whatever the rotation shown. */
function cycleNotices(cycle) {
  return [
    ...cycle.removed.map((r) => alertBox('warn', `Retirée : ${r.message}`)),
    ...(cycle.twins.reliable
      ? []
      : [alertBox('warn', 'Aucun vrai jumeau climatique : la recommandation est moins fiable.')]),
  ];
}

export default {
  title: 'Rotations proposées',
  rota: 'plan',
  render(state, { id }, app) {
    const section = app.section(id);
    const plan = app.sectionPlan(id);
    const head = pageTitle(`Plan de la section ${id}`);
    if (!plan) {
      const wait =
        state.plan.status === 'error'
          ? errorBox(state.plan.error)
          : loading('Rota prépare votre plan', askRota('chargement'));
      return sectionLayout(state, section, 'plan', html`${head}${planStatus(state)}${wait}`);
    }
    const cycle = selectedCycle(plan, state);
    const frequencyMonths = state.plan.data.settings.frequencyMonths;
    const positions = state.plan.data.settings.positionsPerCycle;
    const proposals = proposedRotations(cycle);
    const shown = shownRotation(cycle, state.ui.option);
    const body = html`${head} ${planStatus(state)} ${cycleTabs(plan, cycle.index)}
    ${
      shown
        ? html`<section class="stack-md">
              <div class="row-between wrap">
                <h2 class="h2 h2--lg">
                  ${plural(proposals.length, 'rotation proposée', 'rotations proposées')}
                </h2>
                ${askRota('trois-rotations')}
              </div>
              <div class="row-wrap gap-sm align-center">
                ${decisionPill(cycle.decision)}${askRotaIcon('garder-changer')}
                ${robustnessChip(cycle)}
              </div>
              ${proposals.length ? '' : alertBox('bad', NO_ROTATION)} ${cycleNotices(cycle)}
              <div class="rot-cards">
                ${proposals.map((chain, i) =>
                  rotationCard(chain, i, {
                    cycle,
                    selected: shown.id === i,
                    frequencyMonths,
                    positions,
                  }),
                )}
              </div>
              ${referenceRow(cycle, { selected: shown.id === REFERENCE, frequencyMonths })}
            </section>
            ${rotationDetail(cycle, shown.chain, shown.id, frequencyMonths)}`
        : html`${alertBox('bad', NO_ROTATION)} ${cycleNotices(cycle)}`
    }`;
    return sectionLayout(state, section, 'plan', body);
  },
};
