/**
 * After the last cycle, the robustness of each adopted chain: it is played again in
 * each of the following cycles (their climate, their twins, their return delays)
 * and its worst score is kept. If it becomes impossible in a future cycle, the app
 * shows "becomes infeasible later".
 */
import { delaysRespected } from '../chain/ChainSearch.js';
import { replayChain } from '../chain/ChainReplayer.js';
import { scoreChain } from '../chain/ChainScorer.js';
import { sheetIds } from '../chain/ChainStep.js';

import { DECISION } from './decisions.js';

/** Adds `robustness` and `becomesInfeasibleLater` to every adopted cycle (mutates the cycles). */
export function addRobustness(cycles) {
  cycles.forEach((cycle, i) => {
    cycle.robustness = null;
    cycle.becomesInfeasibleLater = false;
    if (!cycle.chosen || (cycle.decision === DECISION.KEEP && i > 0)) return;
    const ids = sheetIds(cycle.chosen.chain);
    const scores = [cycle.chosen.score];
    for (const later of cycles.slice(i + 1)) {
      let chain = replayChain(ids, later.context);
      if (chain && !delaysRespected(chain, later.context, true)) chain = null;
      scores.push(chain ? scoreChain(chain, later.context).score : NaN);
    }
    cycle.becomesInfeasibleLater = scores.some(Number.isNaN);
    cycle.robustness = cycle.becomesInfeasibleLater ? null : Math.min(...scores);
  });
  return cycles;
}
