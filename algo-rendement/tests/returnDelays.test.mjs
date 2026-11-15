import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  currentCropConflict,
  firstYear,
  lockReason,
  rotationErrors,
  toSlots,
} from '../../src/lib/rotation.js';
import {
  evaluateRotationYieldFromPairs,
  findBestMultiCropRotationsForYield,
} from '../engine/yieldOptimizer.js';

const rotationOf = (...crops) => crops.map((crop) => ({ crop, years: crop === 'luzerne' ? 3 : 1 }));

const stat = (meanEffectPct = 0) => ({
  meanEffectPct,
  intervalPct: [meanEffectPct - 1, meanEffectPct + 1],
  sampleCount: 30,
  effectiveYearsCount: 6,
  confidence: 'elevee',
});

function matrixFor(crops) {
  return {
    pairs: Object.fromEntries(
      crops.flatMap((from) => crops.map((to) => [`${from}>${to}`, stat()])),
    ),
  };
}

test('la patate actuelle attend les quatre ans du délai, pas seulement une année différente', () => {
  for (const crops of [
    ['mais', 'patate', 'soya', 'ble'],
    ['mais', 'soya', 'patate', 'ble'],
  ]) {
    const rotation = rotationOf(...crops);
    assert.deepEqual(rotationErrors(rotation), []);
    assert.match(currentCropConflict({ rotation, currentCrop: 'patate' }), /Délai de retour/);
  }
  assert.equal(
    currentCropConflict({
      rotation: rotationOf('mais', 'soya', 'ble', 'patate'),
      currentCrop: 'patate',
    }),
    null,
  );
});

test('les offsets négatifs et décalés de plusieurs cycles conservent les mêmes contrôles', () => {
  const section = {
    rotation: rotationOf('mais', 'soya', 'ble', 'patate'),
    currentCrop: 'patate',
  };
  for (let offset = -9; offset <= 9; offset++) {
    const normalized = ((offset % 4) + 4) % 4;
    assert.deepEqual(firstYear(section, offset), firstYear(section, normalized));
    assert.equal(currentCropConflict(section, offset), currentCropConflict(section, normalized));
  }
  assert.equal(currentCropConflict(section, -4), null);
  assert.match(currentCropConflict(section, -3), /année 3/);
  assert.match(currentCropConflict(section, -1), /deux ans de suite/);
});

test('une céréale peut revenir en année deux et une culture absente ne crée pas de conflit', () => {
  assert.equal(
    currentCropConflict({
      rotation: rotationOf('soya', 'mais', 'ble'),
      currentCrop: 'mais',
    }),
    null,
  );
  assert.equal(
    currentCropConflict({ rotation: rotationOf('mais', 'soya'), currentCrop: 'patate' }),
    null,
  );
});

test('le délai de la luzerne porte sur les implantations et distingue leurs continuations', () => {
  const rotation = rotationOf('luzerne', 'mais');
  assert.deepEqual(rotationErrors(rotation), []);
  assert.equal(lockReason(rotation, 0, 'luzerne'), null);
  assert.match(rotationErrors(rotationOf('luzerne')).join(' '), /revient trop tôt/);
  assert.match(rotationErrors(rotationOf('luzerne', 'luzerne')).join(' '), /revient trop tôt/);
  assert.match(currentCropConflict({ rotation, currentCrop: 'mais', offset: 1 }), /cours de bloc/);
  assert.equal(currentCropConflict({ rotation, currentCrop: 'luzerne', offset: 1 }), null);
  assert.match(
    currentCropConflict({ rotation, currentCrop: 'luzerne', offset: 0 }),
    /Délai de retour/,
  );
});

test('une continuation initiale ne masque pas la prochaine implantation au cycle suivant', () => {
  const rotation = rotationOf('luzerne', 'mais');
  // The current stand's age is unavailable. Year 0 is the only known history;
  // no earlier planting date is inferred to approve this new block in year 3.
  assert.match(currentCropConflict({ rotation, currentCrop: 'luzerne', offset: 2 }), /année 3/);
  assert.equal(
    currentCropConflict({
      rotation: rotationOf('luzerne', 'mais', 'soya'),
      currentCrop: 'luzerne',
      offset: 2,
    }),
    null,
  );
});

test('l’optimiseur filtre même les meilleurs scores dont la patate revient trop tôt', () => {
  const crops = ['mais', 'soya', 'patate', 'ble'];
  const pairMatrix = matrixFor(crops);
  pairMatrix.pairs['patate>mais'] = stat(20);
  pairMatrix.pairs['mais>patate'] = stat(20);
  for (const offset of [0, 1, -1, 5]) {
    const candidates = findBestMultiCropRotationsForYield({
      pairMatrix,
      currentCrop: 'patate',
      availableCrops: crops,
      cycleYears: 4,
      minDistinctCrops: 4,
      topK: 50,
      offset,
    });
    assert.equal(candidates.length, 6);
    for (const candidate of candidates) {
      const slots = toSlots(candidate.rotation);
      const start = ((offset % slots.length) + slots.length) % slots.length;
      const calendar = slots.map((_, year) => slots[(start + year) % slots.length].crop);
      assert.equal(calendar.indexOf('patate'), 3);
      assert.deepEqual(rotationErrors(candidate.rotation), []);
    }
  }
});

test('les évaluations de référence monoculture restent possibles sans devenir des propositions', () => {
  const pairMatrix = matrixFor(['patate', 'luzerne']);
  for (const crop of ['patate', 'luzerne']) {
    const evaluation = evaluateRotationYieldFromPairs({
      rotation: rotationOf(crop),
      pairMatrix,
      currentCrop: crop,
    });
    assert.equal(evaluation.meanYieldGainPct, 0);
    assert.ok(evaluation.transitions.length > 0);
  }
  assert.deepEqual(
    findBestMultiCropRotationsForYield({
      pairMatrix,
      availableCrops: ['luzerne'],
      cycleYears: 3,
      minDistinctCrops: 1,
    }),
    [],
  );
});
