/**
 * Pure rotation helpers: the *structure* of a rotation (years, cycles, return
 * delays, offsets between sections). No agronomy numbers here: scores, yields
 * and revenues come from the engine (see src/algo).
 *
 * A rotation is a list of entries `{ crop, years, cover }` (the contract format).
 * For editing, it is often easier to work on "slots": one slot per year.
 */
import { CROPS, COVERS } from '../data/crops.js';

/** Number of years in one cycle. */
export function cycleLength(rotation) {
  return rotation.reduce((n, e) => n + (e.years || 1), 0);
}

/** Entries → one slot per year: `{ crop, cover }`. The cover sits on the last year of an entry. */
export function toSlots(rotation) {
  const slots = [];
  for (const e of rotation) {
    const n = e.years || 1;
    for (let i = 0; i < n; i++) {
      slots.push({ crop: e.crop ?? null, cover: i === n - 1 ? (e.cover ?? null) : null });
    }
  }
  return slots;
}

/** Slots → entries. Consecutive slots of a multi-year crop are grouped by its length. */
export function fromSlots(slots) {
  const out = [];
  for (let i = 0; i < slots.length;) {
    const { crop, cover } = slots[i];
    const span = crop && CROPS[crop] ? CROPS[crop].years : 1;
    if (span > 1) {
      out.push({ crop, years: span, cover: null });
      i += span;
    } else {
      out.push({ crop, years: 1, cover: cover ?? null });
      i += 1;
    }
  }
  return out;
}

/** Index of the first year of the entry that covers `index`. */
export function entryStart(rotation, index) {
  let start = 0;
  for (const e of rotation) {
    const n = e.years || 1;
    if (index < start + n) return start;
    start += n;
  }
  return Math.max(0, start - 1);
}

function cleanBlocks(slots) {
  // A multi-year crop must occupy its full length; partial blocks are cleared.
  for (let i = 0; i < slots.length;) {
    const c = slots[i].crop;
    const span = c && CROPS[c] ? CROPS[c].years : 1;
    if (span > 1) {
      let run = 0;
      while (i + run < slots.length && slots[i + run].crop === c && run < span) run++;
      if (run < span) for (let k = 0; k < run; k++) slots[i + k] = { crop: null, cover: null };
      i += run;
    } else i += 1;
  }
  return slots;
}

/** Change the cycle length to `n` years (pads with empty years or truncates). */
export function setCycleYears(rotation, n) {
  const slots = toSlots(rotation).slice(0, n);
  while (slots.length < n) slots.push({ crop: null, cover: null });
  return fromSlots(cleanBlocks(slots));
}

/** Why `crop` cannot go at year `index` of the cycle, or null if it can. */
export function lockReason(rotation, index, crop) {
  const info = CROPS[crop];
  if (!info) return 'Culture inconnue';
  const slots = toSlots(rotation);
  const L = slots.length;
  if (info.years > 1) {
    return index + info.years > L ? `Il faut ${info.years} années libres à partir d’ici` : null;
  }
  if (L > 1 && L < info.returnDelay) {
    return `Le cycle est plus court que le délai de retour (${info.returnDelay} ans)`;
  }
  for (let j = 0; j < L; j++) {
    if (j === index || slots[j].crop !== crop) continue;
    const d = Math.abs(index - j);
    if (Math.min(d, L - d) < info.returnDelay) {
      return `Délai de retour : ${info.returnDelay} ans minimum`;
    }
  }
  return null;
}

/** Put `crop` at year `index` (a multi-year crop fills its whole block). */
export function placeCrop(rotation, index, crop) {
  const slots = toSlots(rotation);
  const old = slots[index]?.crop;
  if (old && CROPS[old]?.years > 1) {
    const start = entryStart(rotation, index);
    for (let k = 0; k < CROPS[old].years; k++) slots[start + k] = { crop: null, cover: null };
  }
  const span = CROPS[crop]?.years || 1;
  for (let k = 0; k < span && index + k < slots.length; k++) {
    slots[index + k] = { crop, cover: span > 1 ? null : (slots[index + k]?.cover ?? null) };
  }
  return fromSlots(cleanBlocks(slots));
}

/** Set (or remove with null) the winter cover after year `index`. */
export function setCover(rotation, index, cover) {
  if (cover !== null && !COVERS[cover]) throw new Error(`Unknown cover: ${cover}`);
  const slots = toSlots(rotation);
  if (!slots[index] || CROPS[slots[index].crop]?.years > 1) return rotation;
  slots[index] = { ...slots[index], cover };
  return fromSlots(slots);
}

/** Problems that prevent evaluating a rotation. Empty list = ready. */
export function rotationErrors(rotation) {
  const errors = [];
  const slots = toSlots(rotation);
  if (slots.length === 0) errors.push('La rotation est vide.');
  slots.forEach((s, i) => {
    if (!s.crop) errors.push(`L’année ${i + 1} n’a pas de culture.`);
    else if (CROPS[s.crop].years === 1 && lockReason(rotation, i, s.crop)) {
      errors.push(`${CROPS[s.crop].name} revient trop tôt (année ${i + 1}).`);
    }
  });
  return errors;
}

/**
 * Year-by-year calendar of one section over the analysis horizon.
 * `offset` = position in the cycle in the first year (staggering between sections).
 */
export function buildCalendar(rotation, { offset = 0, startYear, horizonYears }) {
  const slots = toSlots(rotation);
  const L = slots.length;
  if (L === 0) return [];
  const lastCycle = Math.floor((horizonYears - 1 + offset) / L);
  const endsCut = (horizonYears + offset) % L !== 0;
  return Array.from({ length: horizonYears }, (_, t) => {
    const pos = (t + offset) % L;
    const cycle = Math.floor((t + offset) / L);
    return {
      year: startYear + t,
      crop: slots[pos].crop,
      cover: slots[pos].cover,
      posInCycle: pos,
      isCycleStart: pos === 0,
      cut: endsCut && cycle === lastCycle,
    };
  });
}

/** What the whole farm grows each year, and which years are unbalanced. */
export function farmMix(farm, sections, offsets) {
  const { startYear, horizonYears } = farm;
  const cals = sections.map((s) =>
    buildCalendar(s.rotation, {
      offset: offsets?.[s.id] ?? s.offset ?? 0,
      startYear,
      horizonYears,
    }),
  );
  return Array.from({ length: horizonYears }, (_, t) => {
    const bySection = {};
    const areaByCrop = {};
    const count = {};
    sections.forEach((s, i) => {
      const crop = cals[i][t]?.crop;
      bySection[s.id] = crop;
      if (!crop) return;
      areaByCrop[crop] = (areaByCrop[crop] || 0) + s.areaHa;
      count[crop] = (count[crop] || 0) + 1;
    });
    const duplicates = Object.keys(count).filter((c) => count[c] > 1);
    return {
      year: startYear + t,
      bySection,
      areaByCrop,
      sectionsByCrop: count,
      duplicates,
      balanced: duplicates.length === 0,
    };
  });
}

export function imbalancedYears(farm, sections, offsets) {
  return farmMix(farm, sections, offsets).filter((y) => !y.balanced).length;
}

/**
 * Offsets that minimise the number of unbalanced years. The first section keeps
 * offset 0. Exhaustive search for small farms, greedy beyond that.
 */
export function bestOffsets(farm, sections) {
  const current = Object.fromEntries(sections.map((s) => [s.id, s.offset ?? 0]));
  let best = { ...current };
  let bestBad = imbalancedYears(farm, sections, best);
  const lengths = sections.map((s) => Math.max(1, cycleLength(s.rotation)));
  const combos = lengths.slice(1).reduce((a, b) => a * b, 1);

  if (combos <= 20000) {
    const offs = new Array(sections.length).fill(0);
    const walk = (i) => {
      if (i === sections.length) {
        const o = Object.fromEntries(sections.map((s, k) => [s.id, offs[k]]));
        const bad = imbalancedYears(farm, sections, o);
        if (bad < bestBad) {
          bestBad = bad;
          best = o;
        }
        return;
      }
      for (let v = 0; v < lengths[i]; v++) {
        offs[i] = v;
        walk(i + 1);
      }
    };
    offs[0] = 0;
    walk(1);
  } else {
    const o = { ...current, [sections[0].id]: 0 };
    for (let i = 1; i < sections.length; i++) {
      let bestV = o[sections[i].id];
      let bestLocal = imbalancedYears(farm, sections, o);
      for (let v = 0; v < lengths[i]; v++) {
        const bad = imbalancedYears(farm, sections, { ...o, [sections[i].id]: v });
        if (bad < bestLocal) {
          bestLocal = bad;
          bestV = v;
        }
      }
      o[sections[i].id] = bestV;
    }
    const bad = imbalancedYears(farm, sections, o);
    if (bad < bestBad) {
      bestBad = bad;
      best = o;
    }
  }
  return { offsets: best, imbalanced: bestBad };
}
