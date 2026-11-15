/**
 * Drag-to-reorder for lists rendered with innerHTML, without a library.
 *
 *   <div data-sortable data-commit="reorder-dashboard">
 *     <div data-sort-id="weather"> … <button data-drag-handle>…</button></div>
 *   </div>
 *
 * Pointer events (mouse, pen and touch) on the handle: the block lifts, a copy
 * follows the pointer, the others slide out of the way (FLIP), and on release
 * `onCommit(container, ids)` receives the new order. Escape cancels.
 * While a drag is running the app must not re-render: `isDragging()` tells it,
 * and `onEnd()` is called afterwards so it can catch up.
 *
 * Keyboard: on a focused handle, arrows move the block one place, Home / End
 * to the first / last place. `captureLayout` + `playLayout` animate blocks
 * that moved across a full re-render (keyboard moves, layout reset…).
 */
let active = null;
export const isDragging = () => !!active?.started;

const reduceMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
const itemsOf = (list) => [...list.children].filter((c) => c.matches('[data-sort-id]'));
const idsOf = (list) => itemsOf(list).map((c) => c.dataset.sortId);

/** Move DOM nodes with `mutate`, then animate every item from its old place. */
function flip(list, mutate) {
  const items = itemsOf(list);
  const before = new Map(items.map((el) => [el, el.getBoundingClientRect()]));
  mutate();
  if (reduceMotion()) return;
  for (const el of items) {
    if (el === active?.item) continue;
    const a = before.get(el);
    const b = el.getBoundingClientRect();
    const dx = a.left - b.left;
    const dy = a.top - b.top;
    if (Math.abs(dx) < 1 && Math.abs(dy) < 1) continue;
    el.animate([{ transform: `translate(${dx}px, ${dy}px)` }, { transform: 'none' }], {
      duration: 220,
      easing: 'cubic-bezier(0.2, 0.8, 0.2, 1)',
    });
  }
}

function makeGhost(item, rect) {
  const ghost = item.cloneNode(true);
  ghost.querySelectorAll('[id]').forEach((n) => n.removeAttribute('id'));
  ghost.querySelectorAll('[style*="view-transition-name"]').forEach((n) => {
    n.style.viewTransitionName = 'none';
  });
  ghost.removeAttribute('data-sort-id');
  ghost.setAttribute('aria-hidden', 'true');
  ghost.classList.add('drag-ghost');
  Object.assign(ghost.style, {
    position: 'fixed',
    left: `${rect.left}px`,
    top: `${rect.top}px`,
    width: `${rect.width}px`,
    height: `${rect.height}px`,
    margin: '0',
    zIndex: '3000',
    pointerEvents: 'none',
  });
  document.body.appendChild(ghost);
  return ghost;
}

export function initDragSort(root, { onCommit, onEnd }) {
  const start = (d) => {
    d.started = true;
    d.rect = d.item.getBoundingClientRect();
    d.ghost = makeGhost(d.item, d.rect);
    d.original = idsOf(d.list);
    d.item.classList.add('is-drag-source');
    document.documentElement.classList.add('is-sorting');
    tick();
  };

  const place = (d) => {
    d.ghost.style.transform = `translate(${d.x - d.x0}px, ${d.y - d.y0}px) rotate(0.6deg) scale(1.02)`;
    const under = document.elementFromPoint(d.x, d.y)?.closest('[data-sort-id]');
    if (!under || under === d.item || under.parentElement !== d.list) {
      if (!under || under === d.item) d.last = null;
      return;
    }
    if (under === d.last) return; // wait until the pointer leaves the block we just swapped with
    const items = itemsOf(d.list);
    const from = items.indexOf(d.item);
    const to = items.indexOf(under);
    flip(d.list, () => (from < to ? under.after(d.item) : under.before(d.item)));
    d.last = under;
  };

  // Scroll the page when the pointer nears the top or bottom edge.
  const tick = () => {
    const d = active;
    if (!d?.started) return;
    const edge = 72;
    const v =
      d.y < edge
        ? -(edge - d.y) / 4
        : d.y > innerHeight - edge
          ? (d.y - innerHeight + edge) / 4
          : 0;
    if (v) {
      scrollBy(0, v);
      place(d);
    }
    d.raf = requestAnimationFrame(tick);
  };

  const finish = (commit) => {
    const d = active;
    if (!d) return;
    removeEventListener('pointermove', onMove);
    removeEventListener('pointerup', onUp);
    removeEventListener('pointercancel', onCancel);
    removeEventListener('keydown', onKey, true);
    cancelAnimationFrame(d.raf);
    if (!d.started) {
      active = null;
      return;
    }
    if (!commit)
      flip(d.list, () =>
        d.original.forEach((id) =>
          d.list.append(d.list.querySelector(`[data-sort-id="${CSS.escape(id)}"]`)),
        ),
      );

    const to = d.item.getBoundingClientRect();
    const ghost = d.ghost;
    const done = () => {
      ghost.remove();
      d.item.classList.remove('is-drag-source');
    };
    if (reduceMotion()) done();
    else {
      ghost
        .animate(
          [
            { transform: ghost.style.transform },
            { transform: `translate(${to.left - d.rect.left}px, ${to.top - d.rect.top}px)` },
          ],
          { duration: 180, easing: 'cubic-bezier(0.2, 0.8, 0.2, 1)', fill: 'forwards' },
        )
        .finished.then(done, done);
    }
    document.documentElement.classList.remove('is-sorting');
    const ids = idsOf(d.list);
    active = null;
    if (commit && ids.join('|') !== d.original.join('|'))
      onCommit(d.list, ids, d.item.dataset.sortId);
    onEnd();
  };

  function onMove(e) {
    const d = active;
    if (!d || e.pointerId !== d.pointerId) return;
    d.x = e.clientX;
    d.y = e.clientY;
    if (!d.started) {
      if (Math.hypot(d.x - d.x0, d.y - d.y0) < 5) return;
      start(d);
    }
    e.preventDefault();
    place(d);
  }
  const onUp = (e) => e.pointerId === active?.pointerId && finish(true);
  const onCancel = (e) => e.pointerId === active?.pointerId && finish(false);
  function onKey(e) {
    if (e.key === 'Escape' && active?.started) {
      e.preventDefault();
      e.stopPropagation();
      finish(false);
    }
  }

  root.addEventListener('keydown', (e) => {
    const handle = e.target.closest?.('[data-drag-handle]');
    if (!handle || active) return;
    const item = handle.closest('[data-sort-id]');
    const list = item?.parentElement;
    if (!item || !list?.matches('[data-sortable]')) return;
    const ids = idsOf(list);
    const i = ids.indexOf(item.dataset.sortId);
    const j = {
      ArrowLeft: i - 1,
      ArrowUp: i - 1,
      ArrowRight: i + 1,
      ArrowDown: i + 1,
      Home: 0,
      End: ids.length - 1,
    }[e.key];
    if (j === undefined) return;
    e.preventDefault();
    const k = Math.max(0, Math.min(ids.length - 1, j));
    if (k === i) return;
    ids.splice(k, 0, ...ids.splice(i, 1));
    onCommit(list, ids, item.dataset.sortId);
  });

  root.addEventListener('pointerdown', (e) => {
    const handle = e.target.closest('[data-drag-handle]');
    if (!handle || active || (e.pointerType === 'mouse' && e.button !== 0)) return;
    const item = handle.closest('[data-sort-id]');
    const list = item?.parentElement;
    if (!item || !list?.matches('[data-sortable]')) return;
    e.preventDefault();
    active = {
      item,
      list,
      pointerId: e.pointerId,
      x0: e.clientX,
      y0: e.clientY,
      x: e.clientX,
      y: e.clientY,
      started: false,
      last: null,
    };
    addEventListener('pointermove', onMove, { passive: false });
    addEventListener('pointerup', onUp);
    addEventListener('pointercancel', onCancel);
    addEventListener('keydown', onKey, true);
  });
}

/** Positions of every sortable block, keyed by id (call before a re-render). */
export function captureLayout(root) {
  const map = new Map();
  root.querySelectorAll('[data-sortable] > [data-sort-id]').forEach((el) => {
    map.set(el.dataset.sortId, el.getBoundingClientRect());
  });
  return map;
}

/** After a re-render, slide the blocks that moved from their old place. */
export function playLayout(root, before) {
  if (!before?.size || reduceMotion()) return;
  root.querySelectorAll('[data-sortable] > [data-sort-id]').forEach((el) => {
    const a = before.get(el.dataset.sortId);
    if (!a) return;
    const b = el.getBoundingClientRect();
    const dx = a.left - b.left;
    const dy = a.top - b.top;
    if (Math.abs(dx) < 1 && Math.abs(dy) < 1) return;
    el.animate([{ transform: `translate(${dx}px, ${dy}px)` }, { transform: 'none' }], {
      duration: 240,
      easing: 'cubic-bezier(0.2, 0.8, 0.2, 1)',
    });
  });
}
