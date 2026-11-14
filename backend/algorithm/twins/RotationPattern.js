/**
 * Step 6: reduce the 8 years of crops of a field to its rotation.
 *
 * Cycles of 2, 3 and 4 years are tried, with the most frequent crop at each
 * position of the cycle; at most one atypical year is tolerated. The rotation is
 * written the same way whatever the year it started: "Maïs → Soya",
 * "Luzerne ×3 → Maïs". A field that always grows the same crop is a monoculture;
 * an irregular field has no rotation (null).
 */
import { ATYPICAL_YEARS_ALLOWED, LONGEST_ROTATION_YEARS } from '../config/twins.js';

/** Most frequent value; on a tie, the one seen first. */
function mostFrequent(values) {
  const counts = new Map();
  for (const v of values) counts.set(v, (counts.get(v) ?? 0) + 1);
  let best = null;
  for (const [v, n] of counts) if (best === null || n > counts.get(best)) best = v;
  return best;
}

/** Lexicographic comparison of two lists of strings. */
function compareLists(a, b) {
  for (let i = 0; i < Math.min(a.length, b.length); i++) {
    if (a[i] !== b[i]) return a[i] < b[i] ? -1 : 1;
  }
  return a.length - b.length;
}

/** The rotation of the cycle that starts with the smallest crop name (same start for all). */
function canonicalStart(cycle) {
  let best = cycle;
  for (let i = 1; i < cycle.length; i++) {
    const turned = [...cycle.slice(i), ...cycle.slice(0, i)];
    if (compareLists(turned, best) < 0) best = turned;
  }
  return best;
}

/** "Luzerne, Luzerne, Maïs" → "Luzerne ×2 → Maïs". */
function writeBlocks(cycle) {
  const blocks = [];
  for (const crop of cycle) {
    const last = blocks[blocks.length - 1];
    if (last && last.crop === crop) last.count++;
    else blocks.push({ crop, count: 1 });
  }
  return blocks.map(({ crop, count }) => (count === 1 ? crop : `${crop} ×${count}`)).join(' → ');
}

/**
 * @param {string[]} sequence crops of the successive years
 * @returns {string|null}
 */
export function rotationOf(
  sequence,
  { longest = LONGEST_ROTATION_YEARS, atypicalYears = ATYPICAL_YEARS_ALLOWED } = {},
) {
  if (new Set(sequence).size === 1) return `${sequence[0]} (monoculture)`;
  let best = null;
  for (let period = 2; period <= longest; period++) {
    const cycle = Array.from({ length: period }, (_, j) =>
      mostFrequent(sequence.filter((_, i) => i % period === j)),
    );
    if (new Set(cycle).size === 1) continue;
    const errors = sequence.filter((crop, i) => crop !== cycle[i % period]).length;
    if (best === null || errors < best.errors) best = { errors, cycle }; // tie: shortest cycle
  }
  if (best === null || best.errors > atypicalYears) return null;
  return writeBlocks(canonicalStart(best.cycle));
}
