/**
 * Steps 3 to 7 for one cycle: the target climate of the farm (step 3), its twins
 * (step 4), then what the twins grow and how well (steps 5 to 7). The planner only
 * sees `cycleData(firstYear, lastYear)`; where the data come from (real or demo) is
 * decided when the provider is built.
 */
export class CycleDataProvider {
  /**
   * @param {object} p
   * @param {import('../climate/TargetClimateProjector.js').TargetClimateProjector} p.projector
   * @param {import('../twins/ClimateTwinFinder.js').ClimateTwinFinder} p.twinFinder
   * @param {(firstYear: number, lastYear: number, twins: object[]) =>
   *          import('../twins/TwinEvidence.js').TwinEvidence} p.evidenceFor steps 5 to 7
   */
  constructor({ projector, twinFinder, evidenceFor }) {
    this.projector = projector;
    this.twinFinder = twinFinder;
    this.evidenceFor = evidenceFor;
    this.cache = new Map();
  }

  cycleData(firstYear, lastYear) {
    const key = `${firstYear}-${lastYear}`;
    if (!this.cache.has(key)) {
      const { targets, climate } = this.projector.project(firstYear, lastYear);
      const twins = this.twinFinder.twinsOf(targets);
      this.cache.set(key, { climate, evidence: this.evidenceFor(firstYear, lastYear, twins) });
    }
    return this.cache.get(key);
  }
}
