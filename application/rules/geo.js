/**
 * Small geometry helpers for polygons given as [latitude, longitude] pairs.
 * Farms are a few kilometres wide at most, so a local flat projection
 * (metres east / north around a reference point) is accurate enough here.
 */

const EARTH_M_PER_DEG = 111_320;

/** Short label for a point, used until a readable address is known: "45.6287, -72.9482". */
export const coordsLabel = (lat, lon) => `${lat.toFixed(4)}, ${lon.toFixed(4)}`;

/** Two coordinates (degrees) are the same point for the app (≈ 1 cm). */
export const sameCoord = (a, b) => Math.abs(a - b) < 1e-7;

/** A polygon is usable when it has at least 3 corners. */
export const isClosed = (points) => Array.isArray(points) && points.length >= 3;

/** Mean of the corners, as [lat, lon]. */
export function center(points) {
  if (!points?.length) return null;
  const n = points.length;
  return [points.reduce((a, p) => a + p[0], 0) / n, points.reduce((a, p) => a + p[1], 0) / n];
}

/** Build a projector lat/lon → {x: metres east, y: metres south} around `origin`. */
export function localProjection(origin) {
  const [lat0, lon0] = origin;
  const kx = EARTH_M_PER_DEG * Math.cos((lat0 * Math.PI) / 180);
  return ([lat, lon]) => ({ x: (lon - lon0) * kx, y: (lat0 - lat) * EARTH_M_PER_DEG });
}

/** Area of a polygon in hectares (0 when it is not closed). */
export function areaHa(points) {
  if (!isClosed(points)) return 0;
  const project = localProjection(center(points));
  const pts = points.map(project);
  let sum = 0;
  for (let i = 0; i < pts.length; i++) {
    const a = pts[i];
    const b = pts[(i + 1) % pts.length];
    sum += a.x * b.y - b.x * a.y;
  }
  return Math.abs(sum) / 2 / 10_000;
}

/** Area rounded the way the app displays it (one decimal). */
export const roundHa = (ha) => Math.round(ha * 10) / 10;

/** [[minLat, minLon], [maxLat, maxLon]] of several polygons, or null. */
export function bounds(polygons) {
  const pts = polygons.flat().filter((p) => Array.isArray(p) && p.length === 2);
  if (!pts.length) return null;
  const lats = pts.map((p) => p[0]);
  const lons = pts.map((p) => p[1]);
  return [
    [Math.min(...lats), Math.min(...lons)],
    [Math.max(...lats), Math.max(...lons)],
  ];
}

/**
 * Fit several polygons into a `width × height` box (metres are scaled uniformly,
 * north stays up). Returns the projected polygons as {x, y} in box units plus
 * the scale used, so callers can draw them in an SVG.
 */
export function fitToBox(polygons, { width, height, padding = 0 }) {
  const b = bounds(polygons);
  if (!b) return { shapes: polygons.map(() => []), scale: 0 };
  const origin = [(b[0][0] + b[1][0]) / 2, (b[0][1] + b[1][1]) / 2];
  const project = localProjection(origin);
  const projected = polygons.map((poly) => poly.map(project));
  const xs = projected.flat().map((p) => p.x);
  const ys = projected.flat().map((p) => p.y);
  const w = Math.max(...xs) - Math.min(...xs) || 1;
  const h = Math.max(...ys) - Math.min(...ys) || 1;
  const scale = Math.min((width - 2 * padding) / w, (height - 2 * padding) / h);
  const ox = width / 2;
  const oy = height / 2;
  return {
    scale,
    shapes: projected.map((poly) =>
      poly.map((p) => ({ x: ox + p.x * scale, y: oy + p.y * scale })),
    ),
  };
}

/** Polygon centroid in projected units ({x, y}), falling back to the mean. */
export function centroidXY(pts) {
  if (pts.length < 3) {
    const n = pts.length || 1;
    return {
      x: pts.reduce((a, p) => a + p.x, 0) / n,
      y: pts.reduce((a, p) => a + p.y, 0) / n,
    };
  }
  let a = 0;
  let cx = 0;
  let cy = 0;
  for (let i = 0; i < pts.length; i++) {
    const p = pts[i];
    const q = pts[(i + 1) % pts.length];
    const f = p.x * q.y - q.x * p.y;
    a += f;
    cx += (p.x + q.x) * f;
    cy += (p.y + q.y) * f;
  }
  if (Math.abs(a) < 1e-9) return centroidXY(pts.slice(0, 2));
  return { x: cx / (3 * a), y: cy / (3 * a) };
}
