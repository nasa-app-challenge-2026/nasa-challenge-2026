/**
 * Sections are drawn corner by corner inside the farm outline (Tracer screen),
 * and their corners snap to it. When a corner of the outline is dragged, the
 * sections come along: a section corner sitting on that outline corner moves
 * with it, and one sitting on the two outline edges touching it slides so it
 * stays on them. Mutates the farm it receives (a store draft).
 */
import { areaHa, followCorner, isClosed, roundHa } from './geo.js';

/** Index of the only corner that moved, or -1 (nothing moved, or corners added / removed). */
function movedCorner(before, after) {
  if (before.length !== after.length) return -1;
  const moved = before.flatMap((p, i) => (p[0] === after[i][0] && p[1] === after[i][1] ? [] : [i]));
  return moved.length === 1 ? moved[0] : -1;
}

/** The outline changed from `before` to its current value. Returns true when a section moved. */
export function followOutline(farm, before) {
  const after = farm.farm.boundary ?? [];
  const i = movedCorner(before ?? [], after);
  if (i < 0 || !isClosed(after)) return false;
  let moved = false;
  for (const s of farm.sections) {
    if (!isClosed(s.polygon)) continue;
    const next = followCorner(s.polygon, before, i, after[i]);
    if (next.every((p, k) => p === s.polygon[k])) continue;
    s.polygon = next;
    s.areaHa = Math.max(0.1, roundHa(areaHa(next)));
    moved = true;
  }
  return moved;
}
