/** Linear algebra for the 5 × 5 covariance matrices of step 4. */

/** A pivot smaller than this (relative to the matrix) means the matrix is singular. */
const SINGULAR_PIVOT = 1e-12;
/** Ridge added to the diagonal of a singular covariance (a share of its mean variance). */
const RIDGE_SHARE = 1e-6;

/** Solve A·x = b by Gaussian elimination with partial pivoting; null if A is singular. */
export function solve(matrix, vector) {
  const n = vector.length;
  const a = matrix.map((row, i) => [...row, vector[i]]);
  const scale = Math.max(...matrix.flat().map(Math.abs)) || 1;
  for (let col = 0; col < n; col++) {
    let pivot = col;
    for (let r = col + 1; r < n; r++) if (Math.abs(a[r][col]) > Math.abs(a[pivot][col])) pivot = r;
    if (Math.abs(a[pivot][col]) <= SINGULAR_PIVOT * scale) return null;
    [a[col], a[pivot]] = [a[pivot], a[col]];
    for (let r = col + 1; r < n; r++) {
      const factor = a[r][col] / a[col][col];
      for (let c = col; c <= n; c++) a[r][c] -= factor * a[col][c];
    }
  }
  const x = new Array(n).fill(0);
  for (let r = n - 1; r >= 0; r--) {
    let s = a[r][n];
    for (let c = r + 1; c < n; c++) s -= a[r][c] * x[c];
    x[r] = s / a[r][r];
  }
  return x;
}

/**
 * Solve with a covariance matrix. A cell whose indicator never changes (no hot
 * day in 14 years) has a singular covariance: field_shift.py stops there; we add
 * a tiny ridge to the diagonal instead, so that cell is simply judged very far.
 */
export function solveCovariance(covariance, vector) {
  const direct = solve(covariance, vector);
  if (direct) return direct;
  const n = vector.length;
  const meanVariance = covariance.reduce((s, row, i) => s + row[i], 0) / n || 1;
  const ridged = covariance.map((row, i) =>
    row.map((v, j) => (i === j ? v + RIDGE_SHARE * meanVariance : v)),
  );
  return solve(ridged, vector) ?? new Array(n).fill(Infinity);
}
