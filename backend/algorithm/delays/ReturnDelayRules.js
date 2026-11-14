/**
 * Which return delays apply when crop `next` follows crop `previous`:
 *   - the same crop: its own delay (minimum / recommended);
 *   - another crop of the same family: never two years in a row (grasses exempted);
 *     the shorter recommended delay of the two counts in the pest criterion;
 *   - a soil disease declared by the farmer that hosts both: its high value,
 *     compulsory (e.g. clubroot: 7 years without a crucifer).
 */
export const RULE_KIND = {
  SAME_CROP: 'meme-culture',
  SAME_FAMILY: 'meme-famille',
  DISEASE: 'maladie',
};

/** Between two crops of a family, the hard constraint stays "not two years in a row". */
const SAME_FAMILY_MINIMUM = 1;

/**
 * @typedef {{ minimum: number, recommended: number,
 *             reason: { kind: string, previous: string, next: string, family?: string, disease?: string } }} DelayRule
 */

/**
 * @param {import('./ReturnDelayCatalog.js').ReturnDelayCatalog} catalog
 * @returns {DelayRule[]}
 */
export function delayRules(catalog, previous, next, declaredDiseases = []) {
  const a = catalog.get(previous);
  const b = catalog.get(next);
  if (!a || !b) return [];
  const rules = [];
  const reason = (kind, extra = {}) => ({ kind, previous: a.id, next: b.id, ...extra });
  if (a.id === b.id) {
    rules.push({
      minimum: a.minimum,
      recommended: a.recommended,
      reason: reason(RULE_KIND.SAME_CROP),
    });
  } else if (a.family === b.family && !catalog.isExemptFamily(a.family)) {
    rules.push({
      minimum: Math.min(SAME_FAMILY_MINIMUM, a.minimum, b.minimum),
      recommended: Math.min(a.recommended, b.recommended),
      reason: reason(RULE_KIND.SAME_FAMILY, { family: a.family }),
    });
  }
  for (const disease of declaredDiseases) {
    const hosts = catalog.diseases[disease]?.hosts ?? [];
    if (hosts.includes(a.id) && hosts.includes(b.id)) {
      const years = catalog.diseases[disease].high;
      rules.push({
        minimum: years,
        recommended: years,
        reason: reason(RULE_KIND.DISEASE, { disease }),
      });
    }
  }
  return rules;
}

/** Same reason, same years: reported once. */
export const reasonKey = (r) => `${r.kind}|${r.disease ?? ''}|${r.previous}|${r.next}`;
