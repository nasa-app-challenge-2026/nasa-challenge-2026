/**
 * Polygon editor on a Leaflet map, without extra dependencies.
 *
 *   const editor = createPolygonEditor(map, { onChange, onSelect, onFinish });
 *   editor.sync({ shapes: [{ id, points, color, label, dashed }], activeId, drawing });
 *
 * - While `drawing`, a click on the map appends a corner to the active shape;
 *   a double-click, or a click on the first corner, closes it (`onFinish`).
 * - The active shape's corners are draggable; right-click removes one.
 * - Clicking another shape calls `onSelect(id)`.
 * `sync` is idempotent: call it after every render with the current state.
 */
import { L } from './leafletMap.js';

const FILL_ON = 0.35;
const FILL_OFF = 0.12;

export function createPolygonEditor(map, { onChange, onSelect, onFinish }) {
  const shapesLayer = L.layerGroup().addTo(map);
  const cornersLayer = L.layerGroup().addTo(map);
  let current = { shapes: [], activeId: null, drawing: false };

  const active = () => current.shapes.find((s) => s.id === current.activeId) ?? null;

  map.on('click', (e) => {
    const shape = active();
    if (!current.drawing || !shape) return;
    onChange(shape.id, [...shape.points, [round(e.latlng.lat), round(e.latlng.lng)]]);
  });

  map.on('dblclick', () => {
    const shape = active();
    if (!current.drawing || !shape) return;
    // The two clicks of a double-click usually each added a corner: drop the duplicate.
    const n = shape.points.length;
    const dup = n >= 2 && samePoint(shape.points[n - 1], shape.points[n - 2]);
    const pts = dup ? shape.points.slice(0, -1) : shape.points;
    if (pts.length >= 3) onFinish(shape.id, pts);
    else onChange(shape.id, pts);
  });

  function render() {
    shapesLayer.clearLayers();
    cornersLayer.clearLayers();
    map.getContainer().classList.toggle('is-drawing', current.drawing && !!active());

    for (const shape of current.shapes) {
      const isActive = shape.id === current.activeId;
      if (shape.points.length === 0) continue;
      const open = shape.points.length < 3 || (isActive && current.drawing);
      const style = {
        color: isActive ? '#FFFFFF' : shape.color,
        weight: isActive ? 4 : 2.5,
        dashArray: shape.dashed || open ? '10 8' : null,
        fillColor: shape.color,
        fillOpacity: shape.fill === false ? 0 : isActive ? FILL_ON : FILL_OFF,
        interactive: !isActive,
        // a click on another shape selects it and must not also add a corner
        bubblingMouseEvents: false,
      };
      const layer = open
        ? L.polyline(shape.points, { ...style, fill: false })
        : L.polygon(shape.points, style);
      if (!isActive) layer.on('click', () => onSelect(shape.id));
      layer.addTo(shapesLayer);

      if (shape.label && shape.points.length >= 3) {
        L.tooltip({
          permanent: true,
          direction: 'center',
          className: `poly-label ${isActive ? 'is-active' : ''}`,
          interactive: false,
        })
          .setLatLng(layer.getBounds().getCenter())
          .setContent(shape.label)
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
        title: first ? 'Cliquer pour fermer le contour' : 'Glisser pour déplacer ce coin',
      });
      marker.on('drag', (e) => {
        const ll = e.target.getLatLng();
        const pts = shape.points.map((q, j) => (j === i ? [ll.lat, ll.lng] : q));
        layer.setLatLngs(pts);
      });
      marker.on('dragend', (e) => {
        const ll = e.target.getLatLng();
        onChange(
          shape.id,
          shape.points.map((q, j) => (j === i ? [round(ll.lat), round(ll.lng)] : q)),
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
      render();
    },
    destroy() {
      shapesLayer.remove();
      cornersLayer.remove();
    },
  };
}

const round = (n) => Math.round(n * 1e6) / 1e6;
const samePoint = (a, b) => Math.abs(a[0] - b[0]) < 2e-5 && Math.abs(a[1] - b[1]) < 2e-5;
