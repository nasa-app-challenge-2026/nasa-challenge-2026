/**
 * The chi distribution, needed by the sigma dissimilarity of step 4
 * (Fitzpatrick & Dunn 2019): a Mahalanobis distance in k dimensions is turned into
 * a percentile (chi with k degrees of freedom), then into the distance that has the
 * same percentile in one dimension (chi with 1 degree of freedom) = "sigmas".
 */
const CONVERGENCE = 1e-16;
const MAX_ITERATIONS = 500;
const TINY = 1e-300;

const LANCZOS_G = 7;
const LANCZOS = [
  0.99999999999980993, 676.5203681218851, -1259.1392167224028, 771.32342877765313,
  -176.61502916214059, 12.507343278686905, -0.13857109526572012, 9.9843695780195716e-6,
  1.5056327351493116e-7,
];

/** ln Γ(z) for z > 0 (Lanczos approximation). */
export function logGamma(z) {
  if (z < 0.5) return Math.log(Math.PI / Math.sin(Math.PI * z)) - logGamma(1 - z);
  const x = z - 1;
  let a = LANCZOS[0];
  const t = x + LANCZOS_G + 0.5;
  for (let i = 1; i < LANCZOS.length; i++) a += LANCZOS[i] / (x + i);
  return 0.5 * Math.log(2 * Math.PI) + (x + 0.5) * Math.log(t) - t + Math.log(a);
}

const prefactor = (a, x) => Math.exp(-x + a * Math.log(x) - logGamma(a));

function lowerSeries(a, x) {
  let term = 1 / a;
  let total = term;
  for (let n = 1; n < MAX_ITERATIONS; n++) {
    term *= x / (a + n);
    total += term;
    if (Math.abs(term) < Math.abs(total) * CONVERGENCE) break;
  }
  return total * prefactor(a, x);
}

function upperContinuedFraction(a, x) {
  let b = x + 1 - a;
  let c = 1 / TINY;
  let d = 1 / b;
  let h = d;
  for (let i = 1; i < MAX_ITERATIONS; i++) {
    const an = -i * (i - a);
    b += 2;
    d = an * d + b;
    if (Math.abs(d) < TINY) d = TINY;
    c = b + an / c;
    if (Math.abs(c) < TINY) c = TINY;
    d = 1 / d;
    const delta = d * c;
    h *= delta;
    if (Math.abs(delta - 1) < CONVERGENCE) break;
  }
  return h * prefactor(a, x);
}

/** Regularized lower incomplete gamma P(a, x). */
export function gammaP(a, x) {
  if (x <= 0) return 0;
  return x < a + 1 ? lowerSeries(a, x) : 1 - upperContinuedFraction(a, x);
}

/** Regularized upper incomplete gamma Q(a, x) = 1 − P(a, x), accurate in the tail. */
export function gammaQ(a, x) {
  if (x <= 0) return 1;
  return x < a + 1 ? 1 - lowerSeries(a, x) : upperContinuedFraction(a, x);
}

/** Cumulative distribution of the chi distribution with k degrees of freedom. */
export const chiCdf = (k, x) => gammaP(k / 2, (x * x) / 2);

// Acklam's approximation of the standard normal quantile (relative error < 1.2e-9).
const A = [
  -39.69683028665376, 220.9460984245205, -275.9285104469687, 138.357751867269, -30.66479806614716,
  2.506628277459239,
];
const B = [
  -54.47609879822406, 161.5858368580409, -155.6989798598866, 66.80131188771972, -13.28068155288572,
];
const C = [
  -0.007784894002430293, -0.3223964580411365, -2.400758277161838, -2.549732539343734,
  4.374664141464968, 2.938163982698783,
];
const D = [0.007784695709041462, 0.3224671290700398, 2.445134137142996, 3.754408661907416];
const P_LOW = 0.02425;

function normalQuantile(p) {
  if (p < P_LOW) {
    const q = Math.sqrt(-2 * Math.log(p));
    return (
      (((((C[0] * q + C[1]) * q + C[2]) * q + C[3]) * q + C[4]) * q + C[5]) /
      ((((D[0] * q + D[1]) * q + D[2]) * q + D[3]) * q + 1)
    );
  }
  if (p > 1 - P_LOW) return -normalQuantile(1 - p);
  const q = p - 0.5;
  const r = q * q;
  return (
    ((((((A[0] * r + A[1]) * r + A[2]) * r + A[3]) * r + A[4]) * r + A[5]) * q) /
    (((((B[0] * r + B[1]) * r + B[2]) * r + B[3]) * r + B[4]) * r + 1)
  );
}

/**
 * Quantile of the chi distribution with 1 degree of freedom (the absolute value of a
 * standard normal): Acklam's guess refined by Newton steps on the exact tail.
 */
export function chiOneQuantile(p) {
  if (!(p > 0)) return 0;
  if (p >= 1) return Infinity;
  const tail = 1 - p;
  let x = normalQuantile(1 - tail / 2);
  for (let i = 0; i < MAX_ITERATIONS; i++) {
    const density = Math.sqrt(2 / Math.PI) * Math.exp((-x * x) / 2);
    const step = (tail - gammaQ(0.5, (x * x) / 2)) / density;
    x -= step;
    if (Math.abs(step) <= Math.abs(x) * CONVERGENCE) break;
  }
  return x;
}
