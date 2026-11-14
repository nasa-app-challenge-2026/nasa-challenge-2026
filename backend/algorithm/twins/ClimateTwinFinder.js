/**
 * Step 4: find the places that already had, between 2011 and 2024, the climate the
 * farm will have. The grid is made of NASA POWER cells (about 0.5°, ~50 km); only
 * cultivated cells covered by crop maps can be twins.
 *
 * Short term: one target climate → the 10 closest cells. Long term: one search per
 * climate model, the twins of all models brought together; a cell found by several
 * models keeps its smallest sigma and the list of those models (one arrow per model
 * on the map of the app).
 */
import { GOOD_TWIN_MAX_SIGMA, TWINS_PER_TARGET, TWIN_PERIOD } from '../config/climate.js';
import { sigmaDissimilarity } from './SigmaDissimilarity.js';

/**
 * A cell of the grid.
 * @typedef {{ id: string, lat: number, lon: number, cultivated: boolean,
 *             indicators: import('../climate/IndicatorTable.js').IndicatorTable }} GridCell
 */

export class ClimateTwinFinder {
  /**
   * @param {GridCell[]} cells observed climate of each cell (computed once for all cycles)
   * @param {{ period?: {first: number, last: number}, twinsPerTarget?: number }} [options]
   */
  constructor(cells, { period = TWIN_PERIOD, twinsPerTarget = TWINS_PER_TARGET } = {}) {
    this.cells = cells;
    this.twinsPerTarget = twinsPerTarget;
    this.observedRows = cells.map((c) => c.indicators.between(period.first, period.last).rows);
  }

  /** The closest cultivated cells to one target climate: [{ cell, sigma }], closest first. */
  closestCells(targetRows) {
    return this.cells
      .map((cell, i) => ({
        cell,
        sigma: cell.cultivated ? sigmaDissimilarity(targetRows, this.observedRows[i]) : Infinity,
        index: i,
      }))
      .sort((a, b) => a.sigma - b.sigma || a.index - b.index)
      .slice(0, this.twinsPerTarget)
      .map(({ cell, sigma }) => ({ cell, sigma }));
  }

  /**
   * Twins of every target climate brought together.
   * @param {{ source: string, indicators: { rows: number[][] } }[]} targets
   * @returns {{ cell: GridCell, sigma: number, sources: string[] }[]} smallest sigma first
   */
  twinsOf(targets) {
    const found = new Map();
    for (const { source, indicators } of targets) {
      for (const { cell, sigma } of this.closestCells(indicators.rows)) {
        const twin = found.get(cell.id);
        if (!twin) found.set(cell.id, { cell, sigma, sources: [source] });
        else {
          twin.sigma = Math.min(twin.sigma, sigma);
          twin.sources.push(source);
        }
      }
    }
    return [...found.values()].sort((a, b) => a.sigma - b.sigma);
  }
}

/** σ ≤ 2: the target climate exists somewhere; beyond, the advice is less reliable. */
export const isGoodTwin = (sigma) => sigma <= GOOD_TWIN_MAX_SIGMA;
