/**
 * FICTITIOUS steps 5 to 7: what the twin fields grow and the value of each previous
 * crop (field_shift.py, donnees_cycle of the demo). Real values come from the crop
 * maps (USDA Crop Sequence Boundaries, AAFC inventory) and NASA HLS greenness of the
 * twin fields, after the soil filter (TwinEvidenceBuilder).
 *
 * Near twins still grow canola; once the cycle is 1.5 °C warmer than 2015, the twins
 * look like Ohio, with double-cropped soybean after winter wheat.
 */
import { TwinEvidence } from '../twins/TwinEvidence.js';
import { mean } from '../math/numbers.js';

const WARMING_C_PER_YEAR = 0.07;
const WARMING_REFERENCE_YEAR = 2015;
const OHIO_LIKE_WARMING_C = 1.5;

const CROPS = ['mais', 'soya', 'ble-automne', 'orge', 'luzerne', 'foin', 'sarrasin'];
/** [previous, next, yield gain %]; null = seen in fewer than 20 fields. */
const SUCCESSIONS = [
  ['soya', 'mais', 8],
  ['ble-automne', 'mais', 6],
  ['luzerne', 'mais', 9],
  ['foin', 'mais', 7],
  ['mais', 'soya', 5],
  ['ble-automne', 'soya', 4],
  ['soya', 'ble-automne', 6],
  ['mais', 'orge', 3],
  ['orge', 'luzerne', null],
  ['orge', 'foin', null],
  ['ble-automne', 'luzerne', null],
  ['ble-automne', 'foin', null],
  ['soya', 'orge', 4],
  ['orge', 'mais', 5],
  ['mais', 'luzerne', null],
  ['soya', 'luzerne', null],
  ['sarrasin', 'ble-automne', null],
  ['ble-automne', 'sarrasin', null],
  ['sarrasin', 'mais', 3],
  ['soya', 'sarrasin', null],
];
const NORTHERN = {
  crops: ['canola'],
  successions: [
    ['canola', 'ble-automne', 5],
    ['ble-automne', 'canola', null],
    ['orge', 'canola', null],
    ['canola', 'mais', 4],
  ],
};
const SOUTHERN = {
  crops: ['soya-2e'],
  successions: [
    ['ble-automne', 'soya-2e', null],
    ['soya-2e', 'mais', 6],
    ['soya-2e', 'ble-automne', null],
  ],
};

/** Fictitious warming of a cycle compared with 2015. */
export const demoWarming = (firstYear, lastYear) =>
  Math.max(0, WARMING_C_PER_YEAR * ((firstYear + lastYear) / 2 - WARMING_REFERENCE_YEAR));

/**
 * @param {number} firstYear @param {number} lastYear the cycle
 * @param {{ cell: object, sigma: number, sources: string[] }[]} twins cells found at step 4
 */
export function demoTwinEvidence(firstYear, lastYear, twins) {
  const band = demoWarming(firstYear, lastYear) < OHIO_LIKE_WARMING_C ? NORTHERN : SOUTHERN;
  const finite = twins.map((t) => t.sigma).filter(Number.isFinite);
  return new TwinEvidence({
    crops: [...CROPS, ...band.crops],
    successions: [...SUCCESSIONS, ...band.successions],
    sigmaMean: finite.length ? mean(finite) : Infinity,
    twins,
  });
}
