/**
 * Types of the front ↔ algorithm contract, version 2.0 (JSDoc only, for editor hints). The source
 * of truth is backend/contract/field-shift.schema.json; the explanation is docs/ALGO_CONTRACT.md;
 * the server that implements it is backend/server.
 *
 * @typedef {object} FarmInput   what the screens send: the farm, its settings (cycle, frequency,
 *   horizon, priorities, seeds) and one entry per section (crop in place, harvest month, history,
 *   current rotation, diseases…)
 * @typedef {object} FarmPlan    what the algorithm returns: one plan per section, cycle by cycle
 *   (decision, chosen chain, reference, alternatives, climate, twins)
 *
 * @typedef {object} Engine
 * @property {string} name
 * @property {(input: FarmInput) => Promise<FarmPlan>} planFarm
 */
export {};
