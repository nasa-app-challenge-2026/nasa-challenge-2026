/**
 * Polygon editor on a Leaflet map, without extra dependencies.
 *
 *   const editor = createPolygonEditor(map, { onChange, onFinish });
 *   editor.sync({ shapes: [{ id, points, color, label, dashed, fill }], activeId, drawing });
 *
 * - While `drawing`, a click on the map appends a corner to the active shape;
 *   a double-click, or a click on the first corner, closes it (`onFinish`).
 *   A dashed line follows the pointer from the last corner.
 * - Corners snap to the corners and edges of the other shapes (a section to the
 *   farm outline and to its neighbours), so shapes meet without gaps; a ring
 *   under the pointer shows when a click will snap.
 * - The active shape's corners are draggable (they snap too); right-click removes one.
 * - Shapes never catch clicks: a click inside the farm must reach the map.
 * `sync` is idempotent: call it after every render with the current state.
 */
import { L } from './leafletMap.js';
import { t, translateText } from '../../data/i18n/index.js';

const FILL_ON = 0.35;
const FILL_OFF = 0.12;
const SNAP_CORNER_PX = 14;
const SNAP_EDGE_PX = 10;

export function createPolygonEditor(map, { onChange, onFinish }) {
  const shapesLayer = L.layerGroup().addTo(map);
  const cornersLayer = L.layerGroup().addTo(map);
  const guideLayer = L.layerGroup().addTo(map);
  let current = { shapes: [], activeId: null, drawing: false };
  let guide = null; // dashed line from the last corner to the pointer
  let ring = null; // shown when the pointer snaps

  const active = () => current.shapes.find((s) => s.id === current.activeId) ?? null;
  const drawn = () => (current.drawing ? active() : null);

  map.on('click', (e) => {
    const shape = drawn();
    if (!shape) return;
    onChange(shape.id, [...shape.points, snap(e.latlng, shape.id).point]);
  });

  map.on('dblclick', () => {
    const shape = drawn();
    if (!shape) return;
    // The two clicks of a double-click usually each added a corner: drop the duplicate.
    const n = shape.points.length;
    const dup = n >= 2 && samePoint(shape.points[n - 1], shape.points[n - 2]);
    const pts = dup ? shape.points.slice(0, -1) : shape.points;
    if (pts.length >= 3) onFinish(shape.id, pts);
    else onChange(shape.id, pts);
  });

  map.on('mousemove', (e) => {
    const shape = drawn();
    if (shape) showGuide(shape, snap(e.latlng, shape.id));
  });
  map.on('mouseout', clearGuide);

  /** The point, pulled onto a nearby corner or edge of another shape. */
  function snap(latlng, skipId) {
    const others = current.shapes.filter((s) => s.id !== skipId);
    const at = map.latLngToContainerPoint(latlng);
    let best = null;
    let bestD = SNAP_CORNER_PX;
    for (const s of others) {
      for (const p of s.points) {
        const d = at.distanceTo(map.latLngToContainerPoint(p));
        if (d < bestD) [best, bestD] = [p, d];
      }
    }
    if (best) return { point: [best[0], best[1]], snapped: true };
    bestD = SNAP_EDGE_PX;
    for (const s of others) {
      const pts = s.points;
      const edges = pts.length >= 3 ? pts.length : pts.length - 1;
      for (let i = 0; i < edges; i++) {
        const p = pts[i];
        const q = pts[(i + 1) % pts.length];
        const a = map.latLngToContainerPoint(p);
        const ab = map.latLngToContainerPoint(q).subtract(a);
        const len2 = ab.x * ab.x + ab.y * ab.y;
        if (!len2) continue;
        const t = Math.max(0, Math.min(1, ((at.x - a.x) * ab.x + (at.y - a.y) * ab.y) / len2));
        const d = at.distanceTo(a.add(ab.multiplyBy(t)));
        if (d < bestD) {
          best = [p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])];
          bestD = d;
        }
      }
    }
    if (best) return { point: best, snapped: true };
    return { point: [round(latlng.lat), round(latlng.lng)], snapped: false };
  }

  function showGuide(shape, { point, snapped }) {
    if (!ring) {
      ring = L.circleMarker(point, {
        radius: 8,
        color: '#FFFFFF',
        weight: 2,
        fill: false,
        interactive: false,
      }).addTo(guideLayer);
    }
    ring.setLatLng(point).setStyle({ opacity: snapped ? 1 : 0 });
    const last = shape.points.at(-1);
    if (!last) return;
    if (!guide) {
      guide = L.polyline([last, point], {
        color: '#FFFFFF',
        weight: 2,
        dashArray: '6 6',
        interactive: false,
      }).addTo(guideLayer);
    } else guide.setLatLngs([last, point]);
  }

  function clearGuide() {
    guideLayer.clearLayers();
    guide = null;
    ring = null;
  }

  function render() {
    shapesLayer.clearLayers();
    cornersLayer.clearLayers();
    map.getContainer().classList.toggle('is-drawing', !!drawn());

    for (const shape of current.shapes) {
      const isActive = shape.id === current.activeId;
      if (shape.points.length === 0) continue;
      const open = shape.points.length < 3 || (isActive && current.drawing);
      const style = {
        color: isActive ? '#FFFFFF' : shape.color,
        weight: isActive ? 4 : 2.5,
        dashArray: shape.dashed || open ? '10 8' : null,
        fill: shape.fill !== false,
        fillColor: shape.color,
        fillOpacity: isActive ? FILL_ON : FILL_OFF,
        // A filled shape (even transparent) would catch the click meant to
        // place a corner inside it.
        interactive: false,
      };
      const layer = open
        ? L.polyline(shape.points, { ...style, fill: false })
        : L.polygon(shape.points, style);
      layer.addTo(shapesLayer);

      if (shape.label && shape.points.length >= 3) {
        L.tooltip({
          permanent: true,
          direction: 'center',
          className: `poly-label ${isActive ? 'is-active' : ''}`,
          interactive: false,
        })
          .setLatLng(layer.getBounds().getCenter())
          .setContent(translateText(shape.label))
          .addTo(shapesLayer);
      }

      if (isActive) addCorners(shape, layer);
    }
  }

  function addCorners(shape, layer) {
    shape.points.forEach((p, i) => {
      const first = i === 0 && current.drawing && shape.points.length >= 3;
      const marker = L.marker(p, {
        draggable: true,
        keyboard: false,
        icon: L.divIcon({
          className: `vtx ${first ? 'vtx--first' : ''}`,
          iconSize: first ? [20, 20] : [14, 14],
        }),
        title: t(first ? 'Cliquer pour fermer le tracé' : 'Glisser pour déplacer ce coin'),
      });
      marker.on('drag', (e) => {
        const ll = e.target.getLatLng();
        const pts = shape.points.map((q, j) => (j === i ? [ll.lat, ll.lng] : q));
        layer.setLatLngs(pts);
      });
      marker.on('dragend', (e) => {
        const to = snap(e.target.getLatLng(), shape.id).point;
        onChange(
          shape.id,
          shape.points.map((q, j) => (j === i ? to : q)),
        );
      });
      marker.on('click', (e) => {
        L.DomEvent.stop(e);
        if (first) onFinish(shape.id, shape.points);
      });
      marker.on('contextmenu', (e) => {
        L.DomEvent.stop(e);
        onChange(
          shape.id,
          shape.points.filter((_, j) => j !== i),
        );
      });
      marker.addTo(cornersLayer);
    });
  }

  return {
    sync(next) {
      current = { ...current, ...next };
      clearGuide(); // redrawn from the new last corner on the next pointer move
      render();
    },
    destroy() {
      shapesLayer.remove();
      cornersLayer.remove();
      guideLayer.remove();
    },
  };
}

const round = (n) => Math.round(n * 1e6) / 1e6;
const samePoint = (a, b) => Math.abs(a[0] - b[0]) < 2e-5 && Math.abs(a[1] - b[1]) < 2e-5;
