/**
 * Step 4: how far the target climate of the farm is from the observed climate of
 * a place, in "sigmas" (Fitzpatrick & Dunn 2019).
 *
 * The gap between the mean indicators is judged against the normal year-to-year
 * variations of the place, taking into account that the 5 indicators vary together
 * (Mahalanobis distance). That distance in 5 dimensions becomes a percentile of the
 * chi distribution with 5 degrees of freedom, then the distance with the same
 * percentile in one dimension. 0 = identical, < 2 = good twin, > 2 = no real twin.
 */
import { chiCdf, chiOneQuantile } from '../math/distributions.js';
import { solveCovariance } from '../math/linearAlgebra.js';
import { columnMeans } from '../math/numbers.js';

/** Covariance of the yearly indicators of a place (rows = years). */
function covariance(rows, means) {
  const k = means.length;
  const out = Array.from({ length: k }, () => new Array(k).fill(0));
  for (const row of rows) {
    for (let i = 0; i < k; i++) {
      for (let j = 0; j < k; j++) out[i][j] += (row[i] - means[i]) * (row[j] - means[j]);
    }
  }
  return out.map((line) => line.map((v) => v / (rows.length - 1)));
}

/**
 * @param {number[][]} targetRows yearly indicators of the target climate
 * @param {number[][]} placeRows  yearly indicators observed at the place
 * @returns {number} sigmas (Infinity when the climates do not overlap at all)
 */
export function sigmaDissimilarity(targetRows, placeRows) {
  const placeMeans = columnMeans(placeRows);
  const gap = columnMeans(targetRows).map((v, i) => v - placeMeans[i]);
  const weighted = solveCovariance(covariance(placeRows, placeMeans), gap);
  const squared = gap.reduce((s, g, i) => s + g * weighted[i], 0);
  return chiOneQuantile(chiCdf(gap.length, Math.sqrt(Math.max(0, squared))));
}
