/**
 * 10 · Plan par cycle. Owner: Justin. What the farmer sees for each cycle (step 10
 * of the algorithm): years and climate source, keep or change and the score on
 * 100, the score of his current rotation, the chain with its covers, the calendar,
 * the gaps, the seeds to buy, the warnings, the crops removed, the alerts on his
 * rotation, 2 alternatives, the robustness and the 9 criteria.
 */
import { html } from '../lib/html.js';
import { CROPS, nameOf } from '../../data/reference/crops.js';
import { sectionLayout, pageTitle } from '../ui/layout.js';
import { alertBox, errorBox, loading } from '../ui/widgets.js';
import {
  calendarTable,
  chainChips,
  criteriaBars,
  cycleTabs,
  decisionPill,
  planStatus,
  selectedCycle,
} from '../ui/planWidgets.js';

const score = (chain) => (chain ? Math.round(chain.score) : '—');

function headline(cycle) {
  const delta =
    cycle.chosen && cycle.reference ? Math.round(cycle.chosen.score - cycle.reference.score) : null;
  return html`<section class="row-wrap gap-md align-stretch">
    <div class="card card--dark grow-2 stack-xs">
      <span class="small"
        >Cycle ${cycle.index} · ${cycle.years[0]} à ${cycle.years[1]} ·
        ${cycle.climate.source}</span
      >
      <span class="row gap-sm"
        >${decisionPill(cycle.decision)}<span class="big-number"
          >${score(cycle.chosen)}/100</span
        ></span
      >
      <span class="small"
        >${
          cycle.decision === 'garder'
            ? 'La suite en place reste à 5 points ou moins de la meilleure : on la garde.'
            : 'La meilleure suite de cultures pour ce cycle, avec le climat et les jumeaux de ces années.'
        }</span
      >
    </div>
    <div class="card grow-1 stack-xs justify-center">
      <span class="muted small">Votre rotation actuelle</span>
      <span class="h1">${score(cycle.reference)}/100</span>
      ${delta !== null ? html`<span class="${delta >= 0 ? 'text-good' : 'text-bad'} strong small">${delta >= 0 ? `↑ le plan fait +${delta}` : `↓ le plan fait ${delta}`}</span>` : ''}
    </div>
    <div class="card grow-1 stack-xs justify-center">
      <span class="muted small">Robustesse</span>
      <span class="h1"
        >${cycle.robustness !== null ? Math.round(cycle.robustness) : cycle.decision === 'garder' && cycle.index > 1 ? '—' : '⚠'}</span
      >
      <span class="muted small"
        >${
          cycle.becomesInfeasibleLater
            ? 'Devient infaisable plus tard'
            : cycle.robustness !== null
              ? 'Pire note de cette suite jusqu’à la fin de l’horizon'
              : 'Suite gardée du cycle précédent'
        }</span
      >
    </div>
  </section>`;
}

const MM = (v) => `${Math.round(v)} mm par an`;

/** The water score of the chosen chain in plain numbers (water_use), beside the 9 criteria. */
function waterCard(cycle) {
  const w = cycle.chosen?.water;
  if (!w) return '';
  const facts = [
    ['Note eau', `${Math.round(w.note * 100)} sur 100`],
    ['Demande en eau', MM(w.demandMmPerYear)],
    ['Eau qui manque', MM(w.shortfallMmPerYear)],
    ...(w.irrigationMmPerYear === null
      ? []
      : [['Irrigation nécessaire', MM(w.irrigationMmPerYear)]]),
    ['Pluie gardée', `${Math.round(w.rainKeptPct)} %`],
    ...(w.waterAtSowingMm === null
      ? []
      : [['Eau dans le sol au semis', `${Math.round(w.waterAtSowingMm)} mm`]]),
  ];
  return html`<div class="card stack-sm">
    <div class="row-between wrap">
      <h2 class="h2">L’eau de cette suite</h2>
      <span class="muted small"
        >pression sur l’eau du cycle : ${Math.round(cycle.waterPressure.pressure * 100)} %</span
      >
    </div>
    <div class="row-wrap gap-md">
      ${facts.map(
        ([label, value]) =>
          html`<div class="stack-0">
            <span class="muted small">${label}</span><strong>${value}</strong>
          </div>`,
      )}
    </div>
    ${
      w.byModel.length > 1
        ? html`<span class="muted small"
            >Moyenne de ${w.byModel.length} modèles climatiques · note avec le pire modèle :
            ${Math.round(w.worst * 100)}</span
          >`
        : ''
    }
    ${w.alerts.map((a) => alertBox('warn', a))}
    <span class="muted small"
      >Simulation de l’eau du sol jour par jour, avec les dates de semis et de récolte et les
      couverts de la suite.</span
    >
  </div>`;
}

function notices(cycle) {
  const c = cycle.chosen;
  return [
    ...(c?.gaps.length
      ? [
          alertBox(
            'warn',
            `Précédent inconnu (moins de 20 champs jumeaux) : ${c.gaps.map((g) => g.message).join(', ')}. Compté neutre.`,
          ),
        ]
      : []),
    ...(c?.seedsToBuy.length
      ? [
          alertBox(
            'warn',
            `Semences à se procurer : ${c.seedsToBuy.map((s) => CROPS[s]?.name ?? s).join(', ')}.`,
          ),
        ]
      : []),
    ...(c?.warnings ?? []).map((w) => alertBox('warn', w.message)),
    ...cycle.removed.map((r) => alertBox('warn', `Retirée : ${r.message}`)),
    ...(cycle.twins.reliable
      ? []
      : [
          alertBox(
            'warn',
            'Aucun vrai jumeau climatique (σ > 2) : la recommandation est moins fiable.',
          ),
        ]),
  ];
}

function referenceCard(cycle) {
  if (!cycle.reference) return '';
  return html`<section class="card stack-sm">
    <div class="row-between wrap">
      <h2 class="h2">Votre rotation actuelle, prolongée</h2>
      <strong>${score(cycle.reference)}/100</strong>
    </div>
    ${chainChips(cycle.reference)} ${cycle.referenceAlerts.map((a) => alertBox('warn', a.message))}
    <span class="muted small"
      >Elle sert de comparaison : ses délais non respectés deviennent des alertes.</span
    >
  </section>`;
}

function alternatives(cycle) {
  if (!cycle.alternatives.length) return '';
  return html`<section class="card stack-sm">
    <h2 class="h2">Deux autres possibilités</h2>
    ${cycle.alternatives.map(
      (a) =>
        html`<div class="stack-xs">
          <div class="row-between">
            <span class="small">${a.label}</span><strong>${score(a)}/100</strong>
          </div>
          ${chainChips(a)}
        </div>`,
    )}
  </section>`;
}

export default {
  title: 'Plan par cycle',
  rota: 'plan',
  render(state, { id }, app) {
    const section = app.section(id);
    const plan = app.sectionPlan(id);
    const head = pageTitle(
      `Plan de la section ${id}`,
      section.currentCrop ? `Part de : ${nameOf(section.currentCrop)} en place` : 'Parcelle libre',
    );
    if (!plan) {
      const wait = state.plan.status === 'error' ? errorBox(state.plan.error) : loading();
      return sectionLayout(state, section, 'plan', html`${head}${planStatus(state)}${wait}`);
    }
    const cycle = selectedCycle(plan, state);
    const body = html`${head} ${planStatus(state)} ${cycleTabs(plan, cycle.index)}
      ${headline(cycle)}
      ${
        cycle.chosen
          ? html`<section class="card stack-md">
              <div class="row-between wrap">
                <h2 class="h2">La suite de cultures</h2>
                <span class="muted small">${cycle.chosen.label}</span>
              </div>
              ${chainChips(cycle.chosen)} ${calendarTable(cycle.chosen)}
            </section>`
          : alertBox(
              'bad',
              'Aucune suite de cultures ne respecte toutes les contraintes pour ce cycle. Essayez un cycle plus long ou plus de semences.',
            )
      }
      ${notices(cycle)}
      <section class="row-wrap gap-md align-start">
        ${
          cycle.chosen
            ? html`<div class="card grow-1 stack-md">
                <h2 class="h2">Les 9 critères</h2>
                ${criteriaBars(cycle.chosen, cycle.reference, cycle.weights)}
              </div>`
            : ''
        }
        <div class="grow-1 stack-md">
          ${waterCard(cycle)}${referenceCard(cycle)}${alternatives(cycle)}
        </div>
      </section>
      <div class="actions-bar">
        <a class="btn btn--secondary" href="#/section/${id}/parcelle">Ma parcelle</a
        ><a class="btn btn--primary" href="#/section/${id}/jumeaux">Climat et jumeaux →</a>
      </div>`;
    return sectionLayout(state, section, 'plan', body);
  },
};
