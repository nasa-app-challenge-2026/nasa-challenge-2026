/**
 * How a rotation is drawn, so that it is recognised at a glance. One chain of the plan
 * (FarmPlan…chosen, alternatives, reference), three views:
 *
 *   rotationWheel     the wheel: one slice per crop, read clockwise from the arrow at the top;
 *                     the size of a slice is the time the crop holds the field, a green dot is a
 *                     cover crop sown between two crops, the score is in the middle
 *   rotationLegend    the same crops as a short list: years, picture, name
 *   rotationStrip     one small tile per crop in a row (dashboard cards, the current rotation)
 *   rotationTimeline  the detail: one large tile per crop with its field texture and its dates
 *
 * Nothing is computed here: the chain, its dates and its score come from the algorithm.
 */
import { html } from '../lib/html.js';
import { CROPS, colorOf, nameOf, symbolOf } from '../../data/reference/crops.js';
import { formatDate, t } from '../../data/i18n/index.js';
import { positionYear } from '../../application/rules/planView.js';
import { fieldStrip } from './textures.js';

const TURN = Math.PI * 2;
/** The wheel is drawn in a 100 × 100 box. */
const CENTER = 50;
const OUTER_RADIUS = 44;
const INNER_RADIUS = 26;
const MIDDLE_RADIUS = (OUTER_RADIUS + INNER_RADIUS) / 2;
/** A slice that goes all the way round stops just before its start (an arc needs two points). */
const ALMOST_FULL_TURN = 0.9999;
const HALF_TURN = 0.5;
/** Size of the picture of a crop on its slice: it follows the room there is, within limits. */
const SYMBOL_SIZE = { min: 7, max: 14, shareOfArc: 0.5 };
const COVER_DOT_RADIUS = 3.4;
const COVER_COLOR = '#5E9C55';

const round = (n) => Math.round(n * 100) / 100;

/** Point of the wheel at `turn` (0 = top, clockwise, 1 = a full turn) on a circle. */
function wheelPoint(radius, turn) {
  return [
    round(CENTER + radius * Math.sin(turn * TURN)),
    round(CENTER - radius * Math.cos(turn * TURN)),
  ];
}

/** Path of the slice of the ring between two turns. */
function slicePath(from, to) {
  const end = Math.min(to, from + ALMOST_FULL_TURN);
  const large = end - from > HALF_TURN ? 1 : 0;
  const [x0, y0] = wheelPoint(OUTER_RADIUS, from);
  const [x1, y1] = wheelPoint(OUTER_RADIUS, end);
  const [x2, y2] = wheelPoint(INNER_RADIUS, end);
  const [x3, y3] = wheelPoint(INNER_RADIUS, from);
  return `M${x0} ${y0}A${OUTER_RADIUS} ${OUTER_RADIUS} 0 ${large} 1 ${x1} ${y1}L${x2} ${y2}A${INNER_RADIUS} ${INNER_RADIUS} 0 ${large} 0 ${x3} ${y3}Z`;
}

/** Positions of a cycle: given by the plan, else the last position a step of the chain holds. */
const positionCount = (chain, positions) =>
  positions ?? Math.max(1, ...chain.steps.filter((s) => s.positions).map((s) => s.positions[1]));

const isCover = (step) => step.kind === 'couvert';
const coverName = (step) => CROPS[step.crop]?.name.toLowerCase() ?? step.crop;

/** "Soya, puis Blé d’automne, puis Jachère": the chain in words, for screen readers. */
export const rotationText = (chain) =>
  chain.steps
    .filter((s) => !isCover(s))
    .map((s) => nameOf(s.sheet))
    .join(t('rotation.then'));

/**
 * The wheel of a rotation.
 *
 * positions  positions of a cycle (FarmPlan.settings.positionsPerCycle)
 * score      false hides the score in the middle (small wheels)
 */
export function rotationWheel(chain, { positions, size = 168, score = true } = {}) {
  const count = positionCount(chain, positions);
  let turn = 0; // where the last crop placed ends: a cover crop is drawn there
  const slices = [];
  const covers = [];
  for (const step of chain.steps) {
    if (isCover(step)) {
      const [x, y] = wheelPoint(OUTER_RADIUS, turn);
      covers.push(
        html`<circle
          cx="${x}"
          cy="${y}"
          r="${COVER_DOT_RADIUS}"
          fill="${COVER_COLOR}"
          stroke="#FFFFFF"
          stroke-width="1.2"
        >
          <title>Couvert : ${coverName(step)}</title>
        </circle>`,
      );
      continue;
    }
    const from = (step.positions[0] - 1) / count;
    const to = step.positions[1] / count;
    const [x, y] = wheelPoint(MIDDLE_RADIUS, (from + to) / 2);
    const arc = (to - from) * TURN * MIDDLE_RADIUS;
    const symbolSize = Math.max(
      SYMBOL_SIZE.min,
      Math.min(SYMBOL_SIZE.max, arc * SYMBOL_SIZE.shareOfArc),
    );
    slices.push(
      html`<path d="${slicePath(from, to)}" fill="${colorOf(step.sheet)}" class="wheel__slice">
          <title>${nameOf(step.sheet)}</title>
        </path>
        <text
          x="${x}"
          y="${y}"
          font-size="${round(symbolSize)}"
          text-anchor="middle"
          dominant-baseline="central"
          >${symbolOf(step.sheet)}</text
        >`,
    );
    turn = to;
  }
  return html`<svg
    class="wheel"
    viewBox="0 0 100 100"
    width="${size}"
    height="${size}"
    role="img"
    aria-label="Rotation : ${rotationText(chain)}"
  >
    ${slices}${covers}
    <path d="M47.5 0.6 54.5 3.4 47.5 6.2Z" class="wheel__start"></path>
    ${
      score
        ? html`<text x="50" y="50" class="wheel__score" text-anchor="middle"
              >${Math.round(chain.score)}</text
            ><text x="50" y="61" class="wheel__unit" text-anchor="middle">sur 100</text>`
        : ''
    }
  </svg>`;
}

/** "2027" or "2029–2030": the years of the positions a step holds. */
function stepYears(step, cycle, frequencyMonths) {
  const first = positionYear(cycle, step.positions[0], frequencyMonths);
  const last = positionYear(cycle, step.positions[1], frequencyMonths);
  return first === last ? String(first) : `${first}–${last}`;
}

/** "mai 2028" from "2028-05-12". */
function monthOf(iso) {
  if (!iso) return '—';
  return formatDate(iso, { month: 'short', year: 'numeric' });
}

/**
 * The steps that hold a position, each with the cover crop sown after it (`coverAfter`). A cover
 * sown before the first crop is `leadingCover`.
 */
function cropsWithCovers(chain) {
  const crops = [];
  let leadingCover = null;
  for (const step of chain.steps) {
    if (!isCover(step)) crops.push({ step, coverAfter: null });
    else if (crops.length) crops[crops.length - 1].coverAfter = step;
    else leadingCover = step;
  }
  return { crops, leadingCover };
}

/** The crops of a rotation as a short list: years, picture, name, cover crop. */
export function rotationLegend(chain, cycle, frequencyMonths) {
  const { crops, leadingCover } = cropsWithCovers(chain);
  return html`<ol class="rot-legend">
    ${leadingCover ? html`<li class="rot-legend__cover">+ ${coverName(leadingCover)} avant</li>` : ''}
    ${crops.map(
      ({ step, coverAfter }) =>
        html`<li>
          <span class="rot-legend__years">${stepYears(step, cycle, frequencyMonths)}</span>
          <span class="rot-legend__dot" style="background: ${colorOf(step.sheet)}"
            >${symbolOf(step.sheet)}</span
          >
          <span class="rot-legend__name"
            >${nameOf(step.sheet)}${coverAfter ? html`<small> + ${coverName(coverAfter)}</small>` : ''}</span
          >
        </li>`,
    )}
  </ol>`;
}

/**
 * One small tile per crop, in a row. `year` rings the crop of that year (the dashboard slider).
 */
export function rotationStrip(chain, cycle, frequencyMonths, { year = null } = {}) {
  return html`<div
    class="rot-strip ${year === null ? '' : 'has-now'}"
    role="img"
    aria-label="Rotation : ${rotationText(chain)}"
  >
    ${chain.steps
      .filter((s) => !isCover(s))
      .map((step) => {
        const first = positionYear(cycle, step.positions[0], frequencyMonths);
        const last = positionYear(cycle, step.positions[1], frequencyMonths);
        const now = year !== null && year >= first && year <= last;
        return html`<span
          class="rot-strip__tile ${now ? 'is-now' : ''}"
          style="flex: ${step.positions[1] - step.positions[0] + 1} 1 0; background: ${colorOf(step.sheet)}"
          title="${nameOf(step.sheet)} · ${stepYears(step, cycle, frequencyMonths)}"
        >
          <span class="rot-strip__symbol">${symbolOf(step.sheet)}</span>
          <span class="rot-strip__name">${nameOf(step.sheet)}</span>
        </span>`;
      })}
  </div>`;
}

/** The detail of a rotation: one large tile per crop with its field texture and its dates. */
export function rotationTimeline(chain, cycle, frequencyMonths) {
  const tile = (step) => {
    if (isCover(step))
      return html`<li class="rot-line__cover">
        <strong>+ ${coverName(step)}</strong>
        <span>${monthOf(step.sowing)} → ${monthOf(step.harvest)}</span>
      </li>`;
    const span = step.positions[1] - step.positions[0] + 1;
    return html`<li class="rot-line__step" style="flex: ${span} 1 0">
      <span class="rot-line__photo"
        >${fieldStrip(step.sheet, 56)}<span class="rot-line__symbol"
          >${symbolOf(step.sheet)}</span
        ></span
      >
      <span class="rot-line__years">${stepYears(step, cycle, frequencyMonths)}</span>
      <strong>${nameOf(step.sheet)}</strong>
      <span class="rot-line__dates"
        >${
          step.kind === 'jachere'
            ? 'sol au repos'
            : html`${monthOf(step.sowing)} → ${monthOf(step.harvest)}`
        }</span
      >
    </li>`;
  };
  return html`<ol class="rot-line">
    ${chain.steps.map(tile)}
  </ol>`;
}
