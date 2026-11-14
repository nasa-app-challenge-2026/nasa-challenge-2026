/**
 * Reproducible pseudo-random numbers for the demo data (fictitious weather): the
 * same seed always gives the same farm, in the browser and in the tests.
 */
const UINT32 = 2 ** 32;
const MULBERRY_INCREMENT = 0x6d2b79f5;

export class SeededRandom {
  constructor(seed) {
    this.state = seed >>> 0;
    this.spareNormal = null;
  }

  /** Uniform number in [0, 1) (mulberry32). */
  next() {
    this.state = (this.state + MULBERRY_INCREMENT) >>> 0;
    let t = this.state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / UINT32;
  }

  /** Normal number (Box-Muller). */
  normal(mean = 0, sd = 1) {
    if (this.spareNormal !== null) {
      const z = this.spareNormal;
      this.spareNormal = null;
      return mean + sd * z;
    }
    const u = 1 - this.next();
    const v = this.next();
    const radius = Math.sqrt(-2 * Math.log(u));
    this.spareNormal = radius * Math.sin(2 * Math.PI * v);
    return mean + sd * radius * Math.cos(2 * Math.PI * v);
  }

  /** Gamma number with this shape and scale (Marsaglia and Tsang). */
  gamma(shape, scale) {
    if (shape < 1) return this.gamma(shape + 1, scale) * this.next() ** (1 / shape);
    const d = shape - 1 / 3;
    const c = 1 / Math.sqrt(9 * d);
    for (;;) {
      let x;
      let v;
      do {
        x = this.normal();
        v = 1 + c * x;
      } while (v <= 0);
      v = v * v * v;
      const u = this.next();
      if (Math.log(u) < 0.5 * x * x + d - d * v + d * Math.log(v)) return d * v * scale;
    }
  }
}
