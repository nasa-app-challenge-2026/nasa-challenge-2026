/**
 * A daily weather series: maximum and minimum temperature (°C) and rain (mm/day),
 * one value per day, in date order. NASA POWER gives it for the farm; the climate
 * models are applied to it (step 3). Immutable: every change returns a new series.
 */
const MS_PER_DAY = 86400000;

export class DailyWeather {
  /**
   * @param {{ year: number[], month: number[], dayOfYear: number[],
   *           tmax: number[], tmin: number[], rain: number[] }} columns
   *        month is 1–12, dayOfYear is 1–366.
   */
  constructor({ year, month, dayOfYear, tmax, tmin, rain }) {
    const n = year.length;
    if ([month, dayOfYear, tmax, tmin, rain].some((c) => c.length !== n))
      throw new Error('DailyWeather : toutes les colonnes doivent avoir la même longueur');
    Object.assign(this, { year, month, dayOfYear, tmax, tmin, rain });
    Object.freeze(this);
  }

  /** Every day from 1 January of `firstYear` to 31 December of `lastYear`. */
  static calendar(firstYear, lastYear) {
    const year = [];
    const month = [];
    const dayOfYear = [];
    const end = Date.UTC(lastYear, 11, 31);
    for (let t = Date.UTC(firstYear, 0, 1); t <= end; t += MS_PER_DAY) {
      const d = new Date(t);
      year.push(d.getUTCFullYear());
      month.push(d.getUTCMonth() + 1);
      dayOfYear.push(Math.round((t - Date.UTC(d.getUTCFullYear(), 0, 1)) / MS_PER_DAY) + 1);
    }
    return { year, month, dayOfYear };
  }

  /** A series on the calendar of `firstYear`…`lastYear` with these daily values. */
  static fromSeries({ firstYear, lastYear, tmax, tmin, rain }) {
    return new DailyWeather({ ...DailyWeather.calendar(firstYear, lastYear), tmax, tmin, rain });
  }

  get length() {
    return this.year.length;
  }

  get firstYear() {
    return this.year[0];
  }

  get lastYear() {
    return this.year[this.length - 1];
  }

  /** The days of the years `firstYear` to `lastYear` (both included). */
  between(firstYear, lastYear) {
    const from = this.year.findIndex((y) => y >= firstYear);
    let to = this.length;
    while (to > 0 && this.year[to - 1] > lastYear) to--;
    const start = from < 0 ? to : from;
    const slice = (c) => c.slice(start, to);
    return new DailyWeather({
      year: slice(this.year),
      month: slice(this.month),
      dayOfYear: slice(this.dayOfYear),
      tmax: slice(this.tmax),
      tmin: slice(this.tmin),
      rain: slice(this.rain),
    });
  }

  /** Same days with other values (columns not given are kept). */
  with({ tmax = this.tmax, tmin = this.tmin, rain = this.rain }) {
    return new DailyWeather({ ...this, tmax, tmin, rain });
  }

  /** Every temperature shifted by `deltaC` °C; the rain is unchanged. */
  shiftedBy(deltaC) {
    return this.with({
      tmax: this.tmax.map((v) => v + deltaC),
      tmin: this.tmin.map((v) => v + deltaC),
    });
  }

  /** Daily mean temperature (tmax + tmin) / 2. */
  dailyMean(i) {
    return (this.tmax[i] + this.tmin[i]) / 2;
  }

  /** Indices of the days, grouped by year (years in order). */
  daysByYear() {
    const groups = new Map();
    for (let i = 0; i < this.length; i++) {
      if (!groups.has(this.year[i])) groups.set(this.year[i], []);
      groups.get(this.year[i]).push(i);
    }
    return groups;
  }
}
