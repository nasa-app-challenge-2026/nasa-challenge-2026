/**
 * Suite de tests de vérification de bout en bout de `algo-rendement` :
 * 1) Extraction satellite régionale sur Saint-Hyacinthe, Québec (45.60, -72.90)
 * 2) Prévision du rendement futur par Jumeaux Climatiques & CMIP6 (ssp126, ssp245, ssp370)
 * 3) Tests de sécurité & robustesse (anti-Path Traversal, bornes cycleYears, garde-fous binaires, frontière US/Canada)
 * 4) Tests des invariants statistiques (moyenne toujours dans son IC, incertitude large à N=1, référence unifiée)
 */
import assert from 'node:assert/strict';
import { parseEnvNumber } from './config.js';
import { fetchNasaPowerSeries } from './sources/nasaPower.js';
import { computeRegionBbox, fetchRegionalNdviSeries } from './sources/nasaModisNdvi.js';
import {
  fetchAafcCanadaBboxTile,
  fetchRegionalCropHistory,
  isBorderStraddlingBbox,
  isLocationInCanada,
  mergeCrossBorderTilesByYear,
} from './sources/cropHistory.js';
import { readCache, writeCache } from './sources/cache.js';
import { parseNpyGrid, parseUncompressedTiffU8 } from './sources/rasterParser.js';
import {
  buildNassQueryParams,
  calibratePairMatrixWithNassYields,
  extractAnnualSurveyYields,
  fetchNassStateYields,
  inferUsStateFromLatLon,
} from './sources/nassQuickStats.js';
import {
  buildTransitionObservations,
  computeRegionalPairMatrix,
} from './engine/pairTransitions.js';
import {
  computeUnobservedPairPenalty,
  evaluateRotationYieldFromPairs,
  findBestMultiCropRotationsForYield,
} from './engine/yieldOptimizer.js';
import {
  classifySeasonAgainstBaseline,
  fetchFutureClimateProjection,
} from './sources/nasaCmip6Projection.js';
import {
  findClimateTwin,
  forecastFutureRotationYield,
  loadReferenceRegionsProfiles,
} from './engine/climateTwins.js';

async function verifyRegion(label, lat, lon) {
  const nasaPower = await fetchNasaPowerSeries({ lat, lon });
  const ndviSeries = await fetchRegionalNdviSeries({ lat, lon });
  const cropHistory = await fetchRegionalCropHistory({
    lat,
    lon,
    bbox: ndviSeries.bbox,
    gridSize: ndviSeries.nrows,
  });

  const observations = buildTransitionObservations({
    ndviSeries,
    cropHistory,
    climateSeasons: nasaPower.seasons,
  });
  const pairMatrix = computeRegionalPairMatrix(observations);
  const best4y = findBestMultiCropRotationsForYield({
    pairMatrix,
    cycleYears: 4,
    currentCrop: 'mais',
    minDistinctCrops: 2,
    topK: 3,
  });
  const best3Crops = findBestMultiCropRotationsForYield({
    pairMatrix,
    cycleYears: 4,
    currentCrop: 'mais',
    minDistinctCrops: 3,
    topK: 3,
  });

  console.log(`\n=== ${label} (${lat}, ${lon}) ===`);
  console.log(
    `Champs physiques distincts détectés : ${pairMatrix.totalDistinctFieldsInRegion} parcelles | ${pairMatrix.totalFieldTransitions} transitions de champs (${pairMatrix.totalPixelTransitions} pixels) sur ${Object.keys(pairMatrix.pairs).length} paires`,
  );
  for (const [k, v] of Object.entries(pairMatrix.pairs)) {
    const taxTag = v.sameSpecies
      ? '[même espèce]'
      : v.sameBotanicalFamily
        ? `[même famille: ${v.currFamily}]`
        : `[${v.prevFamily}→${v.currFamily}]`;
    const vsMonoStr = v.sameSpecies
      ? '(réf monoculture)'
      : `(vs mono: ${v.gainVsMonoculturePct >= 0 ? '+' : ''}${v.gainVsMonoculturePct}%)`;
    console.log(
      `  • ${k.padEnd(14)} ${taxTag.padEnd(26)} : ${v.meanEffectPct >= 0 ? '+' : ''}${v.meanEffectPct}% ${vsMonoStr.padEnd(20)} | IC: [${v.intervalPct[0]}%, ${v.intervalPct[1]}%] | champs=${v.distinctFieldsCount}, N=${v.sampleCount} (${v.effectiveYearsCount} ans), conf=${v.confidence}`,
    );

    // Invariant statistique #1 : la moyenne est toujours à l'intérieur de son intervalle de confiance
    assert.ok(
      v.meanEffectPct >= v.intervalPct[0] && v.meanEffectPct <= v.intervalPct[1],
      `La moyenne de ${k} (${v.meanEffectPct}%) doit être dans son IC [${v.intervalPct}]`,
    );
  }

  // Invariant statistique #2 : une paire à N=1 a obligatoirement un IC plus large qu'une paire à N >= 50
  const pairsList = Object.values(pairMatrix.pairs);
  const n1Pairs = pairsList.filter((p) => p.sampleCount === 1);
  const n50Pairs = pairsList.filter((p) => p.sampleCount >= 50);
  for (const p1 of n1Pairs) {
    const width1 = p1.intervalPct[1] - p1.intervalPct[0];
    for (const p50 of n50Pairs) {
      const width50 = p50.intervalPct[1] - p50.intervalPct[0];
      assert.ok(
        width1 > width50,
        `Incertitude à N=1 (${p1.pairKey}: largeur=${width1.toFixed(1)}%) doit être > N>=50 (${p50.pairKey}: largeur=${width50.toFixed(1)}%)`,
      );
    }
  }

  console.log('Meilleure rotation (≥ 2 cultures, 4 ans, après maïs) :');
  for (const r of best4y) {
    console.log(
      `  → ${r.cropsSequence.join(' → ')} | score=${r.rankingScore}% | gain cycle (réf unifiée)=${r.meanYieldGainPct}% (gain vs monoculture=+${r.gainVsMonocultureCyclePct}%) | IC=[${r.yieldGainRangePct.join('%, ')}%] | confiance=${r.confidence}`,
    );
    assert.ok(
      r.meanYieldGainPct >= r.yieldGainRangePct[0] && r.meanYieldGainPct <= r.yieldGainRangePct[1],
    );
  }
  console.log('Meilleure rotation (≥ 3 cultures différentes, 4 ans, après maïs) :');
  for (const r of best3Crops) {
    console.log(
      `  → ${r.cropsSequence.join(' → ')} | score=${r.rankingScore}% | gain cycle (réf unifiée)=${r.meanYieldGainPct}% (gain vs monoculture=+${r.gainVsMonocultureCyclePct}%) | IC=[${r.yieldGainRangePct.join('%, ')}%] | observé=${r.observedShare * 100}%`,
    );
  }

  assert.ok(pairMatrix.totalObservations > 0);
  assert.ok(best4y.length > 0);
  return pairMatrix;
}

const stHyacintheMatrix = await verifyRegion('Saint-Hyacinthe, Québec (Canada)', 45.6, -72.9);

// --- Vérification de la prévision du rendement futur par Jumeaux Climatiques & CMIP6 ---
console.log('\n====================================================================');
console.log('TEST PRÉVISION RENDEMENT FUTUR : JUMEAUX CLIMATIQUES & CMIP6 (SSP)');
console.log('====================================================================');

const referenceRegions = await loadReferenceRegionsProfiles({ startYear: 2018, endYear: 2024 });
assert.ok(referenceRegions.length >= 2, 'Au moins 2 régions de référence doivent être chargées');

// Cas 1 : Ferme nordique à Sacré-Cœur, QC (48.0, -70.0) projetée à l'horizon 2027–2042
const nordPower = await fetchNasaPowerSeries({
  lat: 48.0,
  lon: -70.0,
  startYear: 2018,
  endYear: 2024,
});
const nordProj245 = await fetchFutureClimateProjection({
  lat: 48.0,
  lon: -70.0,
  historicalSeasons: nordPower.seasons,
  startYear: 2027,
  endYear: 2042,
  scenario: 'ssp245',
});
const nordTwin = findClimateTwin({
  projectedSeasons: nordProj245.projectedSeasons,
  localBaselineStats: nordProj245.baselineStats,
  candidateRegions: referenceRegions,
  farmCoordinates: { lat: 48.0, lon: -70.0 },
});
console.log(
  `\n[Cas 1] Ferme boréale (Sacré-Cœur QC, GDD actuel=${nordProj245.baselineStats.means.gddBase10} °C·j) sous SSP2-4.5 (2027-2042) :`,
);
console.log(
  `  → GDD futur projeté : ${nordTwin.targetFutureClimate.gddBase10} °C·j (+${nordTwin.warmingDeltaGdd} °C·j, +${nordTwin.warmingDeltaTempC} °C)`,
);
console.log(
  `  → Jumeau Climatique identifié : ${nordTwin.bestTwin.name} (GDD réf=${nordTwin.bestTwin.baselineMeans.gddBase10} °C·j, distance d=${nordTwin.bestTwin.distance}, similarité=${nordTwin.bestTwin.similarityPct}%)`,
);
assert.equal(nordTwin.bestTwin.id, 'qc_sud_monteregie');

// Cas 2 : Ferme à Saint-Hyacinthe, QC (45.6, -72.9) sous les 3 scénarios CMIP6 (ssp126, ssp245, ssp370)
const stHyaPower = await fetchNasaPowerSeries({
  lat: 45.6,
  lon: -72.9,
  startYear: 2018,
  endYear: 2024,
});

for (const scenario of ['ssp126', 'ssp245', 'ssp370']) {
  const proj = await fetchFutureClimateProjection({
    lat: 45.6,
    lon: -72.9,
    historicalSeasons: stHyaPower.seasons,
    startYear: 2027,
    endYear: 2042,
    scenario,
  });
  const twin = findClimateTwin({
    projectedSeasons: proj.projectedSeasons,
    localBaselineStats: proj.baselineStats,
    candidateRegions: referenceRegions,
    farmCoordinates: { lat: 45.6, lon: -72.9 },
  });
  const futureBest = findBestMultiCropRotationsForYield({
    pairMatrix: stHyacintheMatrix,
    cycleYears: 4,
    currentCrop: 'mais',
    minDistinctCrops: 3,
    topK: 2,
    projectedSeasons: proj.projectedSeasons,
    twinMatch: twin,
    localBaselineStats: proj.baselineStats,
  });

  const topRot = futureBest[0];
  const f = topRot.futureForecast;
  console.log(
    `\n[Cas 2 — Scénario ${scenario.toUpperCase()}] Saint-Hyacinthe (2027–2042, 16 ans) :`,
  );
  console.log(
    `  • Climat projeté fin d'horizon : GDD=${twin.targetFutureClimate.gddBase10} °C·j (+${twin.warmingDeltaGdd}), T_été=${twin.targetFutureClimate.meanTempC} °C (+${twin.warmingDeltaTempC} °C)`,
  );
  console.log(
    `  • Jumeau Climatique : ${twin.bestTwin.name} (d=${twin.bestTwin.distance}, similarité=${twin.bestTwin.similarityPct}%)`,
  );
  console.log(
    `  • Glissement alpha(y) vers le jumeau : ${f.alphaTrajectory.startYearAlpha} (2027) → ${f.alphaTrajectory.endYearAlpha} (2042) | Régimes futurs : normal=${f.futureRegimeDistribution.normal}, chaud=${f.futureRegimeDistribution.chaud}, sec=${f.futureRegimeDistribution.sec}`,
  );
  console.log(
    `  • Meilleure rotation future (≥ 3 cultures) : ${topRot.cropsSequence.join(' → ')} | Gain futur moyen : +${f.meanFutureYieldGainPct}% (IC: [${f.futureYieldGainRangePct[0]}%, ${f.futureYieldGainRangePct[1]}%], confiance=${f.confidence})`,
  );

  assert.equal(f.yearlyForecast.length, 16);
  assert.ok(f.yearlyForecast.every((y) => y.alphaTwin >= 0 && y.alphaTwin <= 1));
  // Invariant statistique #3 : la moyenne future est TOUJOURS comprise dans son intervalle de confiance
  assert.ok(
    f.meanFutureYieldGainPct >= f.futureYieldGainRangePct[0] &&
      f.meanFutureYieldGainPct <= f.futureYieldGainRangePct[1],
    `Gain futur moyen (${f.meanFutureYieldGainPct}%) hors de son IC [${f.futureYieldGainRangePct}]`,
  );
  for (const yr of f.yearlyForecast) {
    assert.ok(
      yr.expectedYieldGainPct >= yr.intervalPct[0] && yr.expectedYieldGainPct <= yr.intervalPct[1],
      `Année ${yr.year} : gain (${yr.expectedYieldGainPct}%) hors de son IC [${yr.intervalPct}]`,
    );
  }
  assert.notEqual(f.confidence, 'elevee');
}

// --- Tests unitaires de sécurité, robustesse et frontières ---
console.log('\n====================================================================');
console.log('TESTS DE SÉCURITÉ, ROBUSTESSE ET GÉOMÉTRIE FRONTALIÈRE');
console.log('====================================================================');

// 1. Protection Path Traversal dans cache.js, nasaCmip6Projection.js et nassQuickStats.js
assert.throws(
  () => readCache('cmip6-projection', '../../../../Users/evil'),
  /Clé ou espace de cache invalide/,
);
assert.throws(() => writeCache('../evil', 'test', {}), /Clé ou espace de cache invalide/);
await assert.rejects(
  () =>
    fetchFutureClimateProjection({
      lat: 45.6,
      lon: -72.9,
      historicalSeasons: stHyaPower.seasons,
      scenario: '../../../../evil',
    }),
  /Scénario CMIP6 invalide/,
);
await assert.rejects(
  () => fetchNassStateYields({ stateAlpha: '../IA' }),
  /Code d'État NASS invalide/,
);
console.log('  ✓ Protection Path Traversal (cache, scenario, model, stateAlpha) vérifiée.');

// 2. Protection anti-DoS sur cycleYears (NaN, < 2, > 6) et sur les sources historiques (startYear, endYear, gridSize)
assert.throws(
  () => findBestMultiCropRotationsForYield({ pairMatrix: stHyacintheMatrix, cycleYears: NaN }),
  RangeError,
);
assert.throws(
  () => findBestMultiCropRotationsForYield({ pairMatrix: stHyacintheMatrix, cycleYears: 12 }),
  RangeError,
);
assert.throws(
  () => findBestMultiCropRotationsForYield({ pairMatrix: stHyacintheMatrix, cycleYears: 'abc' }),
  RangeError,
);
await assert.rejects(
  () => fetchNasaPowerSeries({ lat: 45.6, lon: -72.9, startYear: 1000, endYear: 9999 }),
  RangeError,
);
await assert.rejects(
  () => fetchRegionalNdviSeries({ lat: 45.6, lon: -72.9, gridSize: 10000 }),
  RangeError,
);
await assert.rejects(
  () => fetchRegionalCropHistory({ lat: 45.6, lon: -72.9, halfWindowKm: 500 }),
  RangeError,
);
console.log(
  '  ✓ Bornes strictes sur cycleYears (2..6), startYear/endYear (max 20 ans), gridSize (4..128) et halfWindowKm (1..25) vérifiées.',
);

// 2b. Pénalité de prudence sur les paires non observées (< 0 %, jamais 0 %)
const unobsPenalty = computeUnobservedPairPenalty(stHyacintheMatrix);
assert.ok(
  unobsPenalty <= -1.5,
  `La pénalité pour paire non observée (${unobsPenalty}%) doit être <= -1.5%`,
);
const evalWithUnobserved = evaluateRotationYieldFromPairs({
  rotation: [
    { crop: 'mais', years: 1 },
    { crop: 'soya', years: 1 },
  ],
  pairMatrix: { pairs: { 'mais>soya': stHyacintheMatrix.pairs['mais>soya'] } },
});
const unobsTransition = evalWithUnobserved.transitions.find((t) => !t.observed);
assert.ok(
  unobsTransition.meanEffectPct <= -1.5,
  `Une paire non observée doit recevoir une pénalité <= -1.5% (reçu ${unobsTransition.meanEffectPct}%)`,
);
console.log(
  `  ✓ Pénalité de prudence pour paire non observée (${unobsPenalty}% sur Saint-Hyacinthe, ${unobsTransition.meanEffectPct}% plancher) vérifiée.`,
);

// 2c. Alignement des régimes entre la ferme locale et le Jumeau Climatique (19.3°C = chaud à St-Hyacinthe, normal en Iowa)
const iowaRegion = referenceRegions.find((r) => r.id === 'us_midwest_iowa');
const sampleSummer193 = { meanTempC: 19.3, precipMm: 420 };
assert.equal(
  classifySeasonAgainstBaseline(
    sampleSummer193,
    stHyaPower.seasons ? nordProj245.baselineStats : null,
  ),
  'chaud',
);
assert.equal(
  classifySeasonAgainstBaseline(sampleSummer193, iowaRegion.baselineStats),
  'normal',
  'Un été à 19.3 °C est normal en Iowa, pas un été chaud extrême',
);
console.log(
  '  ✓ Alignement des régimes du Jumeau Climatique (19.3 °C = chaud au Québec, normal en Iowa) vérifié.',
);

// 3. Garde-fous binaires dans rasterParser.js (.npy 1D/4D/Fortran/v3 et GeoTIFF RGB / 16-bit / tags SHORT en ligne)
assert.throws(() => parseNpyGrid(Buffer.from('not_a_npy')), /Format \.npy invalide/);

function buildSyntheticNpyBuffer({
  major = 1,
  descr = '|u1',
  fortranOrder = false,
  shapeStr = '(4, 4)',
  payloadBytes = 16,
}) {
  const dict = `{'descr': '${descr}', 'fortran_order': ${fortranOrder ? 'True' : 'False'}, 'shape': ${shapeStr}, }`;
  const headerOffset = major === 1 ? 10 : 12;
  const paddedLen = Math.ceil((headerOffset + dict.length + 1) / 16) * 16 - headerOffset;
  const header = dict.padEnd(paddedLen - 1, ' ') + '\n';
  const buf = Buffer.alloc(headerOffset + paddedLen + payloadBytes);
  buf[0] = 0x93;
  buf.write('NUMPY', 1, 'ascii');
  buf[6] = major;
  buf[7] = 0;
  if (major === 1) {
    buf.writeUInt16LE(paddedLen, 8);
  } else {
    buf.writeUInt32LE(paddedLen, 8);
  }
  buf.write(header, headerOffset, 'latin1');
  return buf;
}

assert.throws(
  () => parseNpyGrid(buildSyntheticNpyBuffer({ shapeStr: '(16,)' })),
  /Dimensions \.npy invalides/,
  'Une forme 1-D doit être rejetée proprement',
);
assert.throws(
  () => parseNpyGrid(buildSyntheticNpyBuffer({ shapeStr: '(1, 1, 4, 4)' })),
  /Dimensions \.npy invalides/,
  'Une forme 4-D doit être rejetée proprement',
);
assert.throws(
  () => parseNpyGrid(buildSyntheticNpyBuffer({ fortranOrder: true })),
  /fortran_order=True/,
  'fortran_order=True doit être rejeté',
);
assert.throws(
  () => parseNpyGrid(buildSyntheticNpyBuffer({ major: 3 })),
  /Version d'en-tête \.npy non supportée/,
  'Une version majeure .npy != 1 et != 2 doit être rejetée',
);

function buildSyntheticTiffBuffer({
  width = 2,
  height = 2,
  bitsPerSample = [8],
  samplesPerPixel = 1,
  photometric = 1,
}) {
  const entries = [];
  const extraData = [];
  const dataStartOffset = 8 + 2 + 7 * 12 + 4; // 98

  function addTag(tag, type, values) {
    const elemSize = type === 3 ? 2 : 4;
    const count = values.length;
    const entry = Buffer.alloc(12);
    entry.writeUInt16LE(tag, 0);
    entry.writeUInt16LE(type, 2);
    entry.writeUInt32LE(count, 4);
    if (count * elemSize <= 4) {
      for (let i = 0; i < count; i++) {
        if (type === 3) entry.writeUInt16LE(values[i], 8 + i * 2);
        else entry.writeUInt32LE(values[i], 8 + i * 4);
      }
    } else {
      const ptr = dataStartOffset + extraData.reduce((s, b) => s + b.length, 0);
      entry.writeUInt32LE(ptr, 8);
      const arrBuf = Buffer.alloc(count * elemSize);
      for (let i = 0; i < count; i++) {
        if (type === 3) arrBuf.writeUInt16LE(values[i], i * 2);
        else arrBuf.writeUInt32LE(values[i], i * 4);
      }
      extraData.push(arrBuf);
    }
    entries.push(entry);
  }

  addTag(256, 3, [width]); // ImageWidth
  addTag(257, 3, [height]); // ImageLength
  addTag(258, 3, bitsPerSample); // BitsPerSample (inline si count <= 2, pointeur si count == 3)
  addTag(259, 3, [1]); // Compression = NONE
  addTag(262, 3, [photometric]); // PhotometricInterpretation
  addTag(277, 3, [samplesPerPixel]); // SamplesPerPixel

  const pixelBytes = Buffer.from([100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111]);
  const stripOffset = dataStartOffset + extraData.reduce((s, b) => s + b.length, 0);
  addTag(273, 4, [stripOffset]); // StripOffsets
  // Remplacer pour ajouter aussi StripByteCounts (279)
  const header = Buffer.alloc(8);
  header.write('II', 0, 'ascii');
  header.writeUInt16LE(42, 2);
  header.writeUInt32LE(8, 4);

  // Recalcul avec 8 tags
  entries.length = 0;
  extraData.length = 0;
  const baseOff = 8 + 2 + 8 * 12 + 4;
  function addTag8(tag, type, values) {
    const elemSize = type === 3 ? 2 : 4;
    const count = values.length;
    const entry = Buffer.alloc(12);
    entry.writeUInt16LE(tag, 0);
    entry.writeUInt16LE(type, 2);
    entry.writeUInt32LE(count, 4);
    if (count * elemSize <= 4) {
      for (let i = 0; i < count; i++) {
        if (type === 3) entry.writeUInt16LE(values[i], 8 + i * 2);
        else entry.writeUInt32LE(values[i], 8 + i * 4);
      }
    } else {
      const ptr = baseOff + extraData.reduce((s, b) => s + b.length, 0);
      entry.writeUInt32LE(ptr, 8);
      const arrBuf = Buffer.alloc(count * elemSize);
      for (let i = 0; i < count; i++) {
        if (type === 3) arrBuf.writeUInt16LE(values[i], i * 2);
        else arrBuf.writeUInt32LE(values[i], i * 4);
      }
      extraData.push(arrBuf);
    }
    entries.push(entry);
  }
  addTag8(256, 3, [width]);
  addTag8(257, 3, [height]);
  addTag8(258, 3, bitsPerSample);
  addTag8(259, 3, [1]);
  addTag8(262, 3, [photometric]);
  addTag8(277, 3, [samplesPerPixel]);
  const stripOff8 = baseOff + extraData.reduce((s, b) => s + b.length, 0);
  addTag8(273, 4, [stripOff8]);
  addTag8(279, 4, [pixelBytes.length]);

  const ifdCount = Buffer.alloc(2);
  ifdCount.writeUInt16LE(entries.length, 0);
  const nextIfd = Buffer.alloc(4, 0);
  return Buffer.concat([header, ifdCount, ...entries, nextIfd, ...extraData, pixelBytes]);
}

assert.throws(() => parseUncompressedTiffU8(Buffer.from('not_a_tiff')), /GeoTIFF invalide/);
assert.throws(
  () =>
    parseUncompressedTiffU8(
      buildSyntheticTiffBuffer({ samplesPerPixel: 3, bitsPerSample: [8, 8, 8], photometric: 2 }),
    ),
  /SamplesPerPixel=3/,
  'Un GeoTIFF RGB (SamplesPerPixel=3) doit être rejeté',
);
assert.throws(
  () => parseUncompressedTiffU8(buildSyntheticTiffBuffer({ bitsPerSample: [16] })),
  /BitsPerSample/,
  'Un GeoTIFF 16-bit doit être rejeté',
);
assert.throws(
  () => parseUncompressedTiffU8(buildSyntheticTiffBuffer({ bitsPerSample: [8, 8] })),
  /BitsPerSample/,
  'Un tag SHORT à 2 valeurs en ligne (BitsPerSample=[8,8]) doit être lu en ligne et rejeté',
);
const validTiff2x2 = parseUncompressedTiffU8(buildSyntheticTiffBuffer({ width: 2, height: 2 }));
assert.deepEqual(validTiff2x2.pixels, [100, 101, 102, 103]);
console.log(
  '  ✓ Garde-fous binaires complets (.npy 1D/4D/Fortran/v3 et GeoTIFF RGB / 16-bit / SHORT en ligne) vérifiés.',
);

// 4. Découpage frontalier haute précision Canada / États-Unis (Beauce, Côte-du-Sud, Détroit, Niagara, Sault Ste. Marie)
const canadaCities = [
  ['Toronto (ON)', 43.65, -79.38],
  ['London (ON)', 42.98, -81.24],
  ['Windsor (ON)', 42.31, -83.036],
  ['Sarnia (ON)', 42.97, -82.406],
  ['Niagara Falls (ON)', 43.09, -79.085],
  ['Fort Erie (ON)', 42.9, -78.927],
  ['Sault Ste. Marie (ON)', 46.52, -84.33],
  ['Saint-Hyacinthe (QC)', 45.6, -72.9],
  ['Saint-Georges-de-Beauce (QC)', 46.12, -70.67],
  ['Lac-Mégantic (QC)', 45.58, -70.88],
  ['Montmagny (QC)', 46.98, -70.55],
  ['Saint-Jean-Port-Joli (QC)', 47.21, -70.27],
  ['Edmundston (NB)', 47.37, -68.33],
];
for (const [name, lat, lon] of canadaCities) {
  assert.equal(isLocationInCanada(lat, lon), true, `${name} doit être classé au Canada`);
  assert.equal(
    inferUsStateFromLatLon(lat, lon),
    null,
    `${name} (Canada) ne doit jamais recevoir un État américain NASS`,
  );
}

const usCities = [
  ['Detroit (MI)', 42.33, -83.046, 'MI'],
  ['Port Huron (MI)', 42.97, -82.425, 'MI'],
  ['Sault Ste. Marie (MI)', 46.49, -84.35, 'MI'],
  ['Buffalo (NY)', 42.89, -78.878, 'NY'],
  ['Niagara Falls (NY)', 43.09, -79.038, 'NY'],
  ['Minneapolis (MN)', 45.0, -93.26, 'MN'],
  ['Presque Isle (ME)', 46.68, -68.01, 'ME'],
  ['Fort Kent (ME)', 47.25, -68.59, 'ME'],
  ['Story County (IA)', 42.015, -93.75, 'IA'],
];
for (const [name, lat, lon, expectedState] of usCities) {
  assert.equal(isLocationInCanada(lat, lon), false, `${name} doit être classé aux États-Unis`);
  assert.equal(
    inferUsStateFromLatLon(lat, lon),
    expectedState,
    `${name} doit être rattaché à l'État ${expectedState}`,
  );
}

// Vérification de la détection et de la fusion de boîte transfrontalière (ex. Détroit / Windsor)
const detroitBbox = computeRegionBbox(42.33, -83.046, 8);
assert.equal(
  isBorderStraddlingBbox(detroitBbox),
  true,
  'Une boîte de 16 km centrée sur Détroit/Windsor chevauche la frontière US/Canada',
);
const mergedCrossBorder = mergeCrossBorderTilesByYear(
  {
    2023: [
      { rawCode: 1, cropId: 'mais' },
      { rawCode: 0, cropId: null },
    ],
  },
  {
    2023: [
      { rawCode: 0, cropId: null },
      { rawCode: 158, cropId: 'soya' },
    ],
  },
  [2023],
  2,
);
assert.equal(mergedCrossBorder.primaryCount, 1);
assert.equal(mergedCrossBorder.secondaryAddedCount, 1);
assert.deepEqual(
  mergedCrossBorder.mergedTilesByYear[2023].map((x) => x.cropId),
  ['mais', 'soya'],
);
console.log(
  '  ✓ Polyligne frontalière US/Canada (Beauce, Côte-du-Sud, Détroit, Niagara, Sault Ste. Marie) et fusion transfrontalière vérifiées.',
);

// 5. Calibration physique USDA NASS QuickStats
const calibrated = calibratePairMatrixWithNassYields(structuredClone(stHyacintheMatrix), {
  available: true,
  stateAlpha: 'IA',
  yieldsByCropYear: {
    mais: { 2022: 200, 2023: 201 },
    soya: { 2022: 58.5, 2023: 58.0 },
  },
});
assert.ok(calibrated.pairs['soya>mais'].calibratedYield.expectedTonnesPerHa > 0);
console.log(
  `  ✓ Calibration physique NASS QuickStats vérifiée (soya>mais : ${calibrated.pairs['soya>mais'].calibratedYield.baselineTonnesPerHa} t/ha → ${calibrated.pairs['soya>mais'].calibratedYield.expectedTonnesPerHa} t/ha).`,
);

// 6. Protection de la chaîne de prototypes (availableCrops), liste blanche regime et normalisation offset (Tour 3)
const protoSafeCandidates = findBestMultiCropRotationsForYield({
  pairMatrix: stHyacintheMatrix,
  cycleYears: 3,
  availableCrops: ['mais', 'soya', 'ble', 'constructor', '__proto__', 'toString'],
  minDistinctCrops: 2,
});
assert.ok(
  protoSafeCandidates.length > 0,
  'availableCrops avec propriétés du prototype ne doit pas planter',
);
assert.throws(
  () =>
    evaluateRotationYieldFromPairs({
      rotation: [
        { crop: 'mais', years: 1 },
        { crop: 'soya', years: 1 },
      ],
      pairMatrix: stHyacintheMatrix,
      regime: 'constructor',
    }),
  RangeError,
);
const negOffsetEval = evaluateRotationYieldFromPairs({
  rotation: [
    { crop: 'mais', years: 1 },
    { crop: 'soya', years: 1 },
  ],
  pairMatrix: stHyacintheMatrix,
  offset: -3,
});
assert.ok(
  Number.isFinite(negOffsetEval.meanYieldGainPct),
  'Un offset entier négatif doit être normalisé proprement',
);
assert.throws(
  () =>
    evaluateRotationYieldFromPairs({
      rotation: [
        { crop: 'mais', years: 1 },
        { crop: 'soya', years: 1 },
      ],
      pairMatrix: stHyacintheMatrix,
      offset: 1.5,
    }),
  RangeError,
);
console.log(
  '  ✓ Protection anti-prototype (availableCrops), liste blanche regime (all/normal/sec/chaud) et normalisation offset vérifiées.',
);

// 7. Héritage de la confiance historique sur horizon par défaut de 14 saisons (2027-2040) et paires N=1
const proj14 = await fetchFutureClimateProjection({
  lat: 45.6,
  lon: -72.9,
  historicalSeasons: stHyaPower.seasons,
  startYear: 2027,
  endYear: 2040,
  scenario: 'ssp245',
});
const twin14 = findClimateTwin({
  projectedSeasons: proj14.projectedSeasons,
  localBaselineStats: proj14.baselineStats,
  candidateRegions: referenceRegions,
  farmCoordinates: { lat: 45.6, lon: -72.9 },
});
const lowSampleRot = [
  { crop: 'patate', years: 1 },
  { crop: 'mais', years: 1 },
  { crop: 'soya', years: 1 },
  { crop: 'ble', years: 1 },
];
const histLowSampleEval = evaluateRotationYieldFromPairs({
  rotation: lowSampleRot,
  pairMatrix: stHyacintheMatrix,
});
const futLowSampleEval = forecastFutureRotationYield({
  rotation: lowSampleRot,
  localPairMatrix: stHyacintheMatrix,
  twinMatch: twin14,
  projectedSeasons: proj14.projectedSeasons,
  localBaselineStats: proj14.baselineStats,
  historicalConfidence: histLowSampleEval.confidence,
});
assert.equal(histLowSampleEval.confidence, 'faible');
assert.equal(
  futLowSampleEval.confidence,
  'faible',
  'Une rotation contenant une paire à N=1 (conf historique faible) ne peut jamais avoir une confiance future élevée',
);
console.log(
  `  ✓ Héritage de la confiance historique sur horizon 14 ans (patate→mais→soya→ble : hist=${histLowSampleEval.confidence}, future=${futLowSampleEval.confidence}) vérifié.`,
);

// 8. Mélange bayésien d'une paire vue uniquement chez le Jumeau Climatique ((1 - alpha) * pénalité + alpha * jumeau)
const twinOnlyEval = forecastFutureRotationYield({
  rotation: [
    { crop: 'mais', years: 1 },
    { crop: 'soya', years: 1 },
  ],
  localPairMatrix: { pairs: { 'soya>mais': stHyacintheMatrix.pairs['soya>mais'] } }, // mais>soya absente localement, présente en Iowa
  twinMatch: twin14,
  projectedSeasons: proj14.projectedSeasons,
  localBaselineStats: proj14.baselineStats,
});
assert.ok(
  twinOnlyEval.observedShare < 0.75,
  `Une paire absente localement et présente seulement chez le jumeau ne doit pas compter comme 100% observée dès 2027 (observedShare=${twinOnlyEval.observedShare})`,
);
console.log(
  `  ✓ Pondération progressive (1-alpha)*pénalité + alpha*jumeau pour paire vue uniquement chez le jumeau (observedShare=${twinOnlyEval.observedShare}) vérifiée.`,
);

// 9. Géographie et filtrage annuel strict NASS QuickStats (SURVEY / ANNUAL / YEAR / ALFALFA)
assert.equal(
  inferUsStateFromLatLon(45.6, -72.9),
  null,
  'Le Québec ne doit pas être associé à un État US',
);
assert.equal(
  inferUsStateFromLatLon(42.015, -93.75),
  'IA',
  'Story County doit être identifié en Iowa (IA)',
);
const qcNass = await fetchNassStateYields({ lat: 45.6, lon: -72.9 });
assert.equal(qcNass.available, false);
assert.equal(qcNass.stateAlpha, null);

const nassLuzerneParams = buildNassQueryParams({
  apiKey: 'TEST_KEY',
  cropId: 'luzerne',
  stateAlpha: 'IA',
  startYear: 2020,
  endYear: 2024,
});
assert.equal(nassLuzerneParams.get('source_desc'), 'SURVEY');
assert.equal(nassLuzerneParams.get('freq_desc'), 'ANNUAL');
assert.equal(nassLuzerneParams.get('reference_period_desc'), 'YEAR');
assert.equal(nassLuzerneParams.get('domain_desc'), 'TOTAL');
assert.equal(nassLuzerneParams.get('class_desc'), 'ALFALFA');

const filteredNassRows = extractAnnualSurveyYields(
  [
    {
      year: '2023',
      reference_period_desc: 'YEAR',
      source_desc: 'SURVEY',
      domain_desc: 'TOTAL',
      freq_desc: 'ANNUAL',
      class_desc: 'ALL CLASSES',
      Value: '201.0',
    },
    {
      year: '2023',
      reference_period_desc: 'YEAR - AUG FORECAST',
      source_desc: 'SURVEY',
      domain_desc: 'TOTAL',
      freq_desc: 'ANNUAL',
      class_desc: 'ALL CLASSES',
      Value: '185.0',
    },
    {
      year: '2023',
      reference_period_desc: 'YEAR',
      source_desc: 'CENSUS',
      domain_desc: 'TOTAL',
      freq_desc: 'ANNUAL',
      class_desc: 'ALL CLASSES',
      Value: '192.0',
    },
  ],
  'mais',
);
assert.equal(
  filteredNassRows[2023],
  201.0,
  'La prévision mensuelle (AUG FORECAST) ou le CENSUS ne doivent jamais écraser le rendement annuel SURVEY/YEAR',
);
console.log(
  '  ✓ Validation géographique NASS et filtrage strict des bilans annuels (SURVEY / YEAR / ALFALFA, rejet des prévisions mensuelles) vérifiés.',
);

// 10. Jumeau Climatique null quand aucune région plus chaude n'existe (ex. Iowa) + Garde-fous Windows / Pôles / Env (Tour 4)
const iowaTwinMatch = findClimateTwin({
  projectedSeasons: iowaRegion.projectedSeasons || [
    { year: 2040, gddBase10: 1790, meanTempC: 22.8, heatStressDays: 38, precipMm: 510 },
  ],
  localBaselineStats: iowaRegion.baselineStats,
  candidateRegions: referenceRegions,
  farmCoordinates: iowaRegion.coordinates,
});
assert.equal(
  iowaTwinMatch.bestTwin,
  null,
  'Une ferme en Iowa (déjà la plus chaude du catalogue) doit recevoir bestTwin=null et non Saint-Hyacinthe (plus froide)',
);
assert.equal(iowaTwinMatch.status, 'no_warmer_twin_in_catalog');

for (const reserved of ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'LPT1', 'con.json']) {
  assert.throws(
    () => writeCache('nasa-power', reserved, {}),
    /nom réservé interdit/,
    `Le nom réservé Windows ${reserved} doit être bloqué par le cache`,
  );
}
assert.throws(
  () => computeRegionBbox(89.9, -72.9, 8),
  RangeError,
  'Les latitudes polaires (> 80°) doivent être rejetées',
);
await assert.rejects(
  () => fetchAafcCanadaBboxTile({ bbox: detroitBbox, year: '2020/../../evil', gridSize: 64 }),
  RangeError,
  'fetchAafcCanadaBboxTile doit valider year',
);
assert.equal(
  parseEnvNumber('abc', 15000, { min: 1000 }),
  15000,
  'parseEnvNumber doit replier NaN sur la valeur par défaut',
);
console.log(
  '  ✓ Jumeau Climatique null au sommet thermique (Iowa), blocage des noms réservés Windows (CON/NUL/COM1), bornes polaires (±80°) et parseEnvNumber vérifiés.',
);
