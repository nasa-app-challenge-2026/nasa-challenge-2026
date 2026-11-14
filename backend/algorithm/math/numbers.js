/** Small numeric helpers shared by the algorithm. */

export const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
export const clamp01 = (value) => clamp(value, 0, 1);

/** Modulo that stays positive, like Python's `%`. */
export const floorMod = (value, divisor) => ((value % divisor) + divisor) % divisor;

/** Python's round(): halves go to the even neighbour (2036.5 → 2036, 2037.5 → 2038). */
export function roundHalfToEven(value) {
  const floor = Math.floor(value);
  const diff = value - floor;
  if (diff > 0.5) return floor + 1;
  if (diff < 0.5) return floor;
  return floor % 2 === 0 ? floor : floor + 1;
}

/** Change in percent of `value` compared with `reference`. */
export const percentChange = (value, reference) => 100 * (value / reference - 1);

export const sum = (values) => values.reduce((total, v) => total + v, 0);
export const mean = (values) => (values.length ? sum(values) / values.length : NaN);

/** Mean of the finite values, or null when there is none. */
export function meanOfFinite(values) {
  const finite = values.filter((v) => Number.isFinite(v));
  return finite.length ? mean(finite) : null;
}

/** Slope of the least-squares line through (x, y). */
export function linearSlope(xs, ys) {
  const mx = mean(xs);
  const my = mean(ys);
  let num = 0;
  let den = 0;
  for (let i = 0; i < xs.length; i++) {
    num += (xs[i] - mx) * (ys[i] - my);
    den += (xs[i] - mx) ** 2;
  }
  return num / den;
}

/** Mean of each column of a table of rows. */
export function columnMeans(rows) {
  const width = rows[0]?.length ?? 0;
  return Array.from({ length: width }, (_, j) => mean(rows.map((r) => r[j])));
}
