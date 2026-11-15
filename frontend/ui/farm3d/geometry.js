/**
 * The geometry of the 3D farm, without any 3D library (plain numbers, tested in tests/farm3d.test.js):
 * where each section stands in the scene, and where its plants are sown.
 *
 * Scene units: the farm fits in a square of SCENE_SIZE, centred on the origin. A ground point is
 * { x, y } with x to the east and y to the south (the scene puts y on its Z axis).
 */
import { centroidXY, fitToBox, isClosed } from '../../../application/rules/geo.js';

/** Side of the square the drawn farm fits in. */
export const SCENE_SIZE = 20;
/** A section that is not drawn on the map stands in front of the farm as a square of this side. */
const UNDRAWN_SIDE = 3.2;
const UNDRAWN_GAP = 0.8;
/** Plants stay this far from the edge of their section. */
const EDGE_MARGIN = 0.18;

const square = (cx, cy, side) => {
  const h = side / 2;
  return [
    { x: cx - h, y: cy - h },
    { x: cx + h, y: cy - h },
    { x: cx + h, y: cy + h },
    { x: cx - h, y: cy + h },
  ];
};

/**
 * Where everything stands: { plate, sections: [{ id, ring, centre }] }.
 *
 * plate     the outline of the farm (its boundary when it is drawn), or null
 * sections  one ring of ground points per section, in the order given. Sections drawn on the map
 *           keep their real shape; the others are squares in a row in front of the farm.
 */
export function farmLayout(sections, boundary = null) {
  const drawn = sections.filter((s) => isClosed(s.polygon));
  const hasBoundary = isClosed(boundary);
  const polygons = [hasBoundary ? boundary : [], ...drawn.map((s) => s.polygon)];
  const { shapes } = fitToBox(polygons, { width: SCENE_SIZE, height: SCENE_SIZE });
  const half = SCENE_SIZE / 2;
  const [plate, ...rings] = shapes.map((ring) =>
    ring.map((p) => ({ x: p.x - half, y: p.y - half })),
  );

  const undrawn = sections.filter((s) => !isClosed(s.polygon));
  const rowWidth = undrawn.length * UNDRAWN_SIDE + (undrawn.length - 1) * UNDRAWN_GAP;
  const rowY = drawn.length ? half + UNDRAWN_GAP + UNDRAWN_SIDE / 2 : 0;
  const squares = undrawn.map((_, i) =>
    square(-rowWidth / 2 + UNDRAWN_SIDE / 2 + i * (UNDRAWN_SIDE + UNDRAWN_GAP), rowY, UNDRAWN_SIDE),
  );

  const ringOf = new Map([
    ...drawn.map((s, i) => [s.id, rings[i]]),
    ...undrawn.map((s, i) => [s.id, squares[i]]),
  ]);
  return {
    plate: hasBoundary ? plate : null,
    sections: sections.map((s) => {
      const ring = ringOf.get(s.id);
      return { id: s.id, ring, centre: centroidXY(ring) };
    }),
  };
}

/** Is the ground point inside the ring (ray casting)? */
export function insideRing(point, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const a = ring[i];
    const b = ring[j];
    const crosses =
      a.y > point.y !== b.y > point.y &&
      point.x < ((b.x - a.x) * (point.y - a.y)) / (b.y - a.y) + a.x;
    if (crosses) inside = !inside;
  }
  return inside;
}

/** Direction (radians) of the longest edge of a ring: the rows of a field follow it. */
export function rowDirection(ring) {
  let best = 0;
  let angle = 0;
  ring.forEach((a, i) => {
    const b = ring[(i + 1) % ring.length];
    const length = Math.hypot(b.x - a.x, b.y - a.y);
    if (length > best) {
      best = length;
      angle = Math.atan2(b.y - a.y, b.x - a.x);
    }
  });
  return angle;
}

/** Is the point inside the ring, and at least `margin` away from its edge on four sides? */
function wellInside(point, ring, margin) {
  return (
    insideRing({ x: point.x + margin, y: point.y }, ring) &&
    insideRing({ x: point.x - margin, y: point.y }, ring) &&
    insideRing({ x: point.x, y: point.y + margin }, ring) &&
    insideRing({ x: point.x, y: point.y - margin }, ring)
  );
}

/**
 * Where the plants of a section are sown: points in straight rows that follow its longest edge.
 *
 * spacing  distance between two plants of a row
 * rowGap   distance between two rows
 * limit    most plants returned: a big section is sown wider rather than cut off
 */
export function sowingPoints(ring, { spacing, rowGap, limit }) {
  const angle = rowDirection(ring);
  const cos = Math.cos(angle);
  const sin = Math.sin(angle);
  // The ring in the frame of its rows: u along a row, v across the rows.
  const framed = ring.map((p) => ({ u: p.x * cos + p.y * sin, v: -p.x * sin + p.y * cos }));
  const us = framed.map((p) => p.u);
  const vs = framed.map((p) => p.v);
  const [minU, maxU, minV, maxV] = [
    Math.min(...us),
    Math.max(...us),
    Math.min(...vs),
    Math.max(...vs),
  ];

  const expected = ((maxU - minU) / spacing) * ((maxV - minV) / rowGap);
  const widen = expected > limit ? Math.sqrt(expected / limit) : 1;
  const stepU = spacing * widen;
  const stepV = rowGap * widen;

  const points = [];
  for (let v = minV + stepV / 2; v < maxV; v += stepV) {
    for (let u = minU + stepU / 2; u < maxU; u += stepU) {
      const point = { x: u * cos - v * sin, y: u * sin + v * cos };
      if (wellInside(point, ring, EDGE_MARGIN)) points.push(point);
    }
  }
  return points.slice(0, limit);
}
