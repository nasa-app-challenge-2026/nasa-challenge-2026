/**
 * Order of the section cards of the dashboard. The weather and the 3D farm have a fixed place;
 * the farmer can reorder the cards of his sections. A block id is 'sec:<id>'. The saved order
 * (prefs.dashboard) is merged with the current sections: removed sections disappear (and so do
 * the blocks an older version saved), new ones come last.
 */
export const secBlock = (id) => `sec:${id}`;
export const sectionOf = (block) => block.slice('sec:'.length);

/** The sections in the order of the farm. */
export const defaultOrder = (sectionIds) => sectionIds.map(secBlock);

export function dashboardOrder(saved, sectionIds) {
  const blocks = defaultOrder(sectionIds);
  if (!Array.isArray(saved)) return blocks;
  const kept = [...new Set(saved)].filter((block) => blocks.includes(block));
  return [...kept, ...blocks.filter((block) => !kept.includes(block))];
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
export const blockLabel = (block) => `Section ${sectionOf(block)}`;
