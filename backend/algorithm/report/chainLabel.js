/**
 * "(seigle) → Jachère → Soya (+ seigle) → Blé d’automne": a chain in one line.
 * "[2 pos.]" = a crop on several positions; "(+ seigle)" = a cover sown after the
 * crop; "(seigle)" at the start = a cover sown before the first crop.
 */
import { SHEETS } from '../../../data/reference/crops.js';
import { COVER_ATTACH_EPSILON } from '../config/calendar.js';
import { cropName } from './messages.js';

export function chainLabel(chain, covers = []) {
  const coverAfter = new Map();
  let coverFirst = null;
  for (const cover of covers) {
    const name = cropName(SHEETS[cover.sheetId].cropId).toLowerCase();
    let before = -1;
    chain.forEach((step, i) => {
      if (step.sowing === null || step.harvest > cover.sowing + COVER_ATTACH_EPSILON) return;
      if (before < 0 || step.harvest > chain[before].harvest) before = i;
    });
    if (before >= 0) coverAfter.set(before, name);
    else coverFirst = name;
  }
  const parts = coverFirst ? [`(${coverFirst})`] : [];
  chain.forEach((step, i) => {
    const span = step.lastPosition - step.firstPosition + 1;
    let text = SHEETS[step.sheetId].name + (span > 1 ? ` [${span} pos.]` : '');
    if (coverAfter.has(i)) text += ` (+ ${coverAfter.get(i)})`;
    parts.push(text);
  });
  return parts.join(' → ');
}
