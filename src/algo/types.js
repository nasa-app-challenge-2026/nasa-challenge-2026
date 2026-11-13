/**
 * Types of the front ↔ algorithm contract (JSDoc only, for editor hints).
 * The source of truth is contract/field-shift.schema.json; the explanation is
 * docs/ALGO_CONTRACT.md.
 *
 * @typedef {'mais'|'soya'|'ble'|'orge'|'patate'|'luzerne'} CropId
 * @typedef {'seigle'|'trefle'|'radis'|null} CoverId
 * @typedef {{ crop: CropId, years: number, cover?: CoverId }} RotationEntry
 * @typedef {{ id: string, areaHa: number, offset: number, note?: string,
 *             polygon?: number[][], rotation: RotationEntry[] }} Section
 * @typedef {{ version: '1.0', farm: object, options?: { stressYears?: 1|3 },
 *             sections: Section[] }} FarmInput
 * @typedef {{ eau: number, sol: number, resilience: number, revenu: number }} Scores
 * @typedef {object} SectionPlan
 * @typedef {{ version: '1.0', meta: { engine: string, demo: boolean },
 *             farm: { score: number, revenuePerYear: number },
 *             sections: SectionPlan[] }} FarmPlan
 *
 * @typedef {object} Engine
 * @property {string} name
 * @property {(input: FarmInput) => Promise<FarmPlan>} evaluateFarm
 * @property {(req: { farm: FarmInput, sectionId: string, cycleYears: number })
 *   => Promise<{ rotation: RotationEntry[], reasons: string[] }>} proposeRotation
 * @property {(req: { farm: FarmInput, sectionId: string })
 *   => Promise<{ sectionId: string, demo?: boolean, metrics: object[] }>} getFieldData
 */
export {};
