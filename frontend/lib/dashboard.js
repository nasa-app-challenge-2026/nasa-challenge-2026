/**
 * Order of the dashboard blocks. Ids: 'weather', 'farm3d', 'mix' and one
 * 'sec:<id>' per section. The saved order (prefs.dashboard) is merged with the
 * current sections: removed sections disappear, new ones slot in after the
 * last section already placed.
 */
export const FIXED_BLOCKS = ['weather', 'farm3d', 'mix'];
export const secBlock = (id) => `sec:${id}`;

/** Default layout on a 4-column grid: weather + A B / 3D + C D / 3D + mix / more sections. */
export function defaultOrder(sectionIds) {
  const s = sectionIds.map(secBlock);
  return ['weather', ...s.slice(0, 2), 'farm3d', ...s.slice(2, 4), 'mix', ...s.slice(4)];
}

export function dashboardOrder(saved, sectionIds) {
  if (!Array.isArray(saved) || !saved.length) return defaultOrder(sectionIds);
  const wanted = new Set([...FIXED_BLOCKS, ...sectionIds.map(secBlock)]);
  const order = [...new Set(saved)].filter((b) => wanted.has(b));
  for (const b of FIXED_BLOCKS) if (!order.includes(b)) order.push(b);
  for (const id of sectionIds) {
    const b = secBlock(id);
    if (order.includes(b)) continue;
    let at = -1;
    order.forEach((x, i) => {
      if (x.startsWith('sec:')) at = i;
    });
    order.splice(at + 1, 0, b);
  }
  return order;
}

/** Move one block by `delta` places (keyboard). Returns a new array. */
export function moveBlock(order, id, delta) {
  const i = order.indexOf(id);
  const j = Math.max(0, Math.min(order.length - 1, i + delta));
  if (i < 0 || i === j) return order;
  const next = [...order];
  next.splice(j, 0, ...next.splice(i, 1));
  return next;
}

export const isDefaultOrder = (order, sectionIds) =>
  order.join('|') === defaultOrder(sectionIds).join('|');

/** Human name of a block, for screen readers and handles. */
export function blockLabel(id) {
  if (id.startsWith('sec:')) return `Section ${id.slice(4)}`;
  return { weather: 'Météo à la ferme', farm3d: 'Ma ferme en 3D', mix: 'Toute la ferme' }[id] ?? id;
}
