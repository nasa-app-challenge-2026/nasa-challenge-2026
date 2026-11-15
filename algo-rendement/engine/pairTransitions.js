/**
 * Moteur de calcul empirique des effets de transition (A -> B) par région.
 *
 * ZÉRO valeur agronomique de transition codée en dur : toutes les valeurs proviennent du croisement
 * entre l'historique satellite des cultures (CDL / AAFC), le pic estival de vigueur (MODIS)
 * et la normalisation agro-météorologique annuelle (NASA POWER).
 *
 * Rigueur statistique et méthodologique :
 * 1) Indice de vigueur homogène (`selectConsistentVigorIndex`) : utilise exclusivement l'EVI
 *    (si disponible sur la tuile MODIS) ou exclusivement le NDVI, sans jamais mélanger les deux échelles.
 * 2) Segmentation spatiale en CHAMPS DISTINCTS (`clusterPixelsIntoDistinctFields`, BFS 4-connexe)
 *    avec contrôle de borne sur `gridSize` + pondération accrue des pixels intérieurs purs.
 * 3) Correction météo inter-annuelle par régression Ridge L2 (`computeWeatherAdjustedNdvi`).
 * 4) Traitement 100 % symétrique entre rotations et monocultures sur une Référence Unifiée
 *    (`unifiedBaseline`) par culture B et année t.
 * 5) Régularisation bayésienne hiérarchique des sous-régimes (`normal`, `sec`, `chaud`) vers la
 *    moyenne globale de la paire (évitant qu'un sous-régime à N=1 ou N=2 n'amplifie du bruit).
 * 6) Erreur-type bayésienne clusterisée par année (`computeClusterRobustStdError`) prenant en compte
 *    que tous les champs d'une même année partagent le même été ($T_{\text{eff}} \le 6$ années indépendantes).
 */
import { CONFIG, CROP_TAXONOMY } from '../config.js';
import { sameBbox, validateBbox } from '../sources/cache.js';
import {
  physicalEffectInterval,
  relativeGainPct,
  validatePhysicalEffectPct,
} from './modelUtils.js';

function selectConsistentVigorIndex(gridsByYear) {
  let eviValid = 0;
  let ndviValid = 0;
  for (const grid of Object.values(gridsByYear || {})) {
    for (const v of grid?.eviPixels || []) {
      if (Number.isFinite(v) && v > 0.05 && v <= 1) eviValid += 1;
    }
    for (const v of grid?.pixels || []) {
      if (Number.isFinite(v) && v > 0.05 && v <= 1) ndviValid += 1;
    }
  }
  return eviValid > 0 && eviValid >= ndviValid * 0.5 ? 'EVI' : 'NDVI';
}

/**
 * Regroupe les pixels adjacents (connexité 4 sur la grille `gridSize x gridSize`)
 * qui partagent exactement la même séquence pluriannuelle de cultures en **champs agricoles distincts**.
 */
export function clusterPixelsIntoDistinctFields({ cropIdsByYear, gridSize = 64, years }) {
  const gSize = Number(gridSize);
  if (!Number.isInteger(gSize) || gSize < 4 || gSize > 128) {
    throw new RangeError(
      `gridSize invalide dans clusterPixelsIntoDistinctFields (${gridSize}) : entier attendu entre 4 et 128.`,
    );
  }
  const nPixels = gSize * gSize;
  const signatures = new Array(nPixels);

  for (let p = 0; p < nPixels; p++) {
    const seq = years.map((y) => cropIdsByYear[y]?.[p] || '_');
    const hasCrop = seq.some((c) => c !== '_');
    signatures[p] = hasCrop ? seq.join('|') : null;
  }

  const visited = new Uint8Array(nPixels);
  const fields = [];

  const dirs = [
    [-1, 0],
    [1, 0],
    [0, -1],
    [0, 1],
  ];

  for (let p = 0; p < nPixels; p++) {
    const sig = signatures[p];
    if (!sig || visited[p]) continue;

    const pixels = [p];
    visited[p] = 1;
    let head = 0;

    while (head < pixels.length) {
      const curr = pixels[head++];
      const r = Math.floor(curr / gSize);
      const c = curr % gSize;

      for (const [dr, dc] of dirs) {
        const nr = r + dr;
        const nc = c + dc;
        if (nr < 0 || nr >= gSize || nc < 0 || nc >= gSize) continue;
        const np = nr * gSize + nc;
        if (!visited[np] && signatures[np] === sig) {
          visited[np] = 1;
          pixels.push(np);
        }
      }
    }

    fields.push({
      fieldId: fields.length + 1,
      pixelIndices: pixels,
      pixelCount: pixels.length,
      areaHa: Number((pixels.length * 6.25).toFixed(2)),
      signature: sig,
    });
  }

  return fields;
}

function isInteriorPurePixel(p, currArr, currCrop, gridSize) {
  const r = Math.floor(p / gridSize);
  const c = p % gridSize;
  if (r <= 0 || r >= gridSize - 1 || c <= 0 || c >= gridSize - 1) return false;
  return (
    currArr[(r - 1) * gridSize + c] === currCrop &&
    currArr[(r + 1) * gridSize + c] === currCrop &&
    currArr[r * gridSize + (c - 1)] === currCrop &&
    currArr[r * gridSize + (c + 1)] === currCrop
  );
}

/**
 * Construit le tableau d'observations (champ distinct f, année t) en utilisant un indice
 * de vigueur strictement homogène (`EVI` ou `NDVI`) sur toute la région.
 */
export function buildTransitionObservations({ ndviSeries, cropHistory, climateSeasons }) {
  const climateByYear = new Map((climateSeasons || []).map((s) => [s.year, s]));
  const gridsByYear = ndviSeries?.gridsByYear || {};
  const vigorIndexUsed = selectConsistentVigorIndex(gridsByYear);
  const observations = [];

  if (cropHistory?.cropIdsByYear) {
    validateBbox(ndviSeries?.bbox);
    validateBbox(cropHistory.bbox);
    if (
      !sameBbox(ndviSeries.bbox, cropHistory.bbox) ||
      ndviSeries.nrows !== cropHistory.gridSize ||
      ndviSeries.ncols !== cropHistory.gridSize
    ) {
      throw new RangeError('Grilles de cultures et de vigueur désalignées (bbox ou dimensions).');
    }
    const years = Object.keys(cropHistory.cropIdsByYear)
      .map(Number)
      .sort((a, b) => a - b);
    const gridSize = Number(cropHistory.gridSize || ndviSeries?.nrows || 64);
    const coords = ndviSeries?.pixelCoordinates || [];

    const distinctFields = clusterPixelsIntoDistinctFields({
      cropIdsByYear: cropHistory.cropIdsByYear,
      gridSize,
      years,
    });

    for (let i = 1; i < years.length; i++) {
      const prevYear = years[i - 1];
      const currYear = years[i];
      if (currYear !== prevYear + 1) continue;

      const prevArr = cropHistory.cropIdsByYear[prevYear] || [];
      const currArr = cropHistory.cropIdsByYear[currYear] || [];
      const ndviGrid = gridsByYear[currYear];
      if (!ndviGrid) continue;
      // Une année satellite absente n'est pas une grille décalée : aucune paire ne la traverse.
      if (prevArr.length === 0 || currArr.length === 0) continue;
      if (prevArr.length !== gridSize ** 2 || currArr.length !== gridSize ** 2) {
        throw new RangeError('Grille de cultures incomplète.');
      }

      const bandArray = vigorIndexUsed === 'EVI' ? ndviGrid.eviPixels : ndviGrid.pixels;
      if (!bandArray) continue;
      if (bandArray.length !== gridSize ** 2) throw new RangeError('Grille de vigueur incomplète.');

      const climate = climateByYear.get(currYear) || null;
      if (!climate) throw new RangeError(`Saison climatique manquante pour ${currYear}.`);

      for (const field of distinctFields) {
        const repPixel = field.pixelIndices[0];
        const prevCrop = prevArr[repPixel];
        const currCrop = currArr[repPixel];
        if (!prevCrop || !currCrop) continue;

        let sumWeightedVigor = 0;
        let sumWeights = 0;
        let interiorCount = 0;

        for (const p of field.pixelIndices) {
          const v = bandArray[p] ?? null;
          if (Number.isFinite(v) && v > 0.08 && v <= 1) {
            const pure = isInteriorPurePixel(p, currArr, currCrop, gridSize);
            const weight = pure ? 2.0 : 1.0;
            if (pure) interiorCount += 1;
            sumWeightedVigor += v * weight;
            sumWeights += weight;
          }
        }
        if (sumWeights === 0) continue;

        const fieldNdvi = Number((sumWeightedVigor / sumWeights).toFixed(4));
        const prevFamily = CROP_TAXONOMY[prevCrop]?.family || null;
        const currFamily = CROP_TAXONOMY[currCrop]?.family || null;

        observations.push({
          fieldId: field.fieldId,
          pixelCount: field.pixelCount,
          interiorPixelCount: interiorCount,
          areaHa: field.areaHa,
          vigorIndexUsed,
          lat: coords[repPixel]?.lat ?? null,
          lon: coords[repPixel]?.lon ?? null,
          prevYear,
          currYear,
          prevCrop,
          currCrop,
          pairKey: `${prevCrop}>${currCrop}`,
          isMonoculture: prevCrop === currCrop,
          sameSpecies: prevCrop === currCrop,
          sameBotanicalFamily: prevFamily !== null && prevFamily === currFamily,
          prevFamily,
          currFamily,
          ndvi: fieldNdvi,
          climate,
        });
      }
    }
    return observations;
  }

  // Format point-par-point historique (fallback)
  const points = cropHistory?.historyByPoint || [];
  for (const pt of points) {
    const years = Object.keys(pt.cropsByYear || {})
      .map(Number)
      .sort((a, b) => a - b);

    for (let i = 1; i < years.length; i++) {
      const prevYear = years[i - 1];
      const currYear = years[i];
      if (currYear !== prevYear + 1) continue;

      const prevCrop = pt.cropsByYear[prevYear]?.cropId;
      const currCrop = pt.cropsByYear[currYear]?.cropId;
      if (!prevCrop || !currCrop) continue;

      const ndviGrid = gridsByYear[currYear];
      const bandArray = vigorIndexUsed === 'EVI' ? ndviGrid?.eviPixels : ndviGrid?.pixels;
      const ndvi = bandArray?.[pt.pixelIndex] ?? null;
      if (!Number.isFinite(ndvi) || ndvi <= 0.08 || ndvi > 1) continue;

      const climate = climateByYear.get(currYear) || null;
      const prevFamily = CROP_TAXONOMY[prevCrop]?.family || null;
      const currFamily = CROP_TAXONOMY[currCrop]?.family || null;

      observations.push({
        fieldId: pt.pixelIndex + 1,
        pixelCount: 1,
        interiorPixelCount: 0,
        areaHa: 6.25,
        vigorIndexUsed,
        lat: pt.lat,
        lon: pt.lon,
        prevYear,
        currYear,
        prevCrop,
        currCrop,
        pairKey: `${prevCrop}>${currCrop}`,
        isMonoculture: prevCrop === currCrop,
        sameSpecies: prevCrop === currCrop,
        sameBotanicalFamily: prevFamily !== null && prevFamily === currFamily,
        prevFamily,
        currFamily,
        ndvi,
        climate,
      });
    }
  }

  return observations;
}

/**
 * Ajuste log(vigueur) par Ridge L2 avec intercept : les covariables sont centrées
 * sur les observations de la culture. La correction multiplicative conserve une
 * vigueur de référence strictement positive, sans tronquer les observations.
 */
function computeWeatherAdjustedNdvi(obsForCropB) {
  const withClimate = obsForCropB.filter((o) => o.climate != null);
  if (withClimate.length < 6) {
    return obsForCropB.map((o) => ({ ...o, adjustedNdvi: o.ndvi }));
  }

  const climateValue = (o, key) => o.climate[key] ?? 0;
  const meanY = withClimate.reduce((s, o) => s + Math.log(o.ndvi), 0) / withClimate.length;
  const meanRain =
    withClimate.reduce((s, o) => s + climateValue(o, 'rainZScore'), 0) / withClimate.length;
  const meanTemp =
    withClimate.reduce((s, o) => s + climateValue(o, 'tempZScore'), 0) / withClimate.length;
  const lambda = CONFIG.hyperparameters.ridgeLambda;
  let sRR = lambda;
  let sTT = lambda;
  let sRT = 0;
  let sRY = 0;
  let sTY = 0;

  for (const o of withClimate) {
    const r = climateValue(o, 'rainZScore') - meanRain;
    const t = climateValue(o, 'tempZScore') - meanTemp;
    const y = Math.log(o.ndvi) - meanY;
    sRR += r * r;
    sTT += t * t;
    sRT += r * t;
    sRY += r * y;
    sTY += t * y;
  }

  const det = sRR * sTT - sRT * sRT;
  if (!Number.isFinite(det) || det <= 0) {
    throw new RangeError('Ajustement météo impossible : système Ridge non fini ou singulier.');
  }
  const betaRain = (sTT * sRY - sRT * sTY) / det;
  const betaTemp = (sRR * sTY - sRT * sRY) / det;

  return obsForCropB.map((o) => {
    if (!o.climate) return { ...o, adjustedNdvi: o.ndvi };
    const weatherEffect =
      betaRain * climateValue(o, 'rainZScore') + betaTemp * climateValue(o, 'tempZScore');
    const adjustedNdvi = Math.exp(Math.log(o.ndvi) - weatherEffect);
    if (!Number.isFinite(adjustedNdvi) || adjustedNdvi <= 0) {
      throw new RangeError(
        'Ajustement météo impossible : vigueur corrigée non positive ou non finie.',
      );
    }
    return {
      ...o,
      adjustedNdvi,
    };
  });
}

/**
 * Calcule le poids d'observation d'une parcelle en fonction du nombre de ses pixels intérieurs purs.
 */
function getFieldReliabilityWeight(item) {
  return Math.min(3.0, 1.0 + 0.5 * (item.interiorPixelCount || 0));
}

/**
 * Calcule l'erreur-type bayésienne clusterisée par année (`computeClusterRobustStdError`) :
 * Combine la dispersion inter-parcelles pondérée (avec les mêmes poids `w` que `rawMean`)
 * sur N champs-années et la dispersion inter-annuelle sur les T_eff années distinctes d'observation.
 */
function computeClusterRobustStdError(items, rawMean, priorStdPct, priorDof = 4) {
  const n = items.length;
  if (n === 0) return priorStdPct;

  let weightedSqDiffSum = 0;
  let weightTotal = 0;
  for (const item of items) {
    const w = getFieldReliabilityWeight(item);
    weightedSqDiffSum += w * (item.deltaPct - rawMean) ** 2;
    weightTotal += w;
  }

  const sampleVar =
    n > 1 && weightTotal > 0 ? (weightedSqDiffSum / weightTotal) * (n / (n - 1)) : 0;
  const fieldComponentVar =
    ((n - 1) * sampleVar + priorDof * priorStdPct ** 2) / (Math.max(1, n + priorDof - 1) * n);

  const byYear = new Map();
  for (const item of items) {
    if (!byYear.has(item.year)) byYear.set(item.year, []);
    byYear.get(item.year).push(item);
  }

  const tEff = byYear.size;
  const yearMeans = [...byYear.values()].map((arr) => {
    let wSum = 0;
    let wTot = 0;
    for (const x of arr) {
      const w = getFieldReliabilityWeight(x);
      wSum += w * x.deltaPct;
      wTot += w;
    }
    return wSum / Math.max(1, wTot);
  });
  const meanOfYears = yearMeans.reduce((a, b) => a + b, 0) / Math.max(1, tEff);
  const betweenYearVar =
    tEff > 1 ? yearMeans.reduce((a, b) => a + (b - meanOfYears) ** 2, 0) / (tEff - 1) : 0;

  const yearPriorStd = priorStdPct * 0.25;
  const yearComponentVar =
    ((tEff - 1) * betweenYearVar + 2 * yearPriorStd ** 2) /
    (Math.max(1, tEff + 1) * Math.max(1, tEff));

  return Math.sqrt(fieldComponentVar + yearComponentVar);
}

/**
 * Calcule la matrice régionale complète des transitions (A -> B) à partir des champs distincts observés.
 */
export function computeRegionalPairMatrix(observations) {
  for (const observation of observations) {
    if (!Number.isFinite(observation.ndvi) || observation.ndvi <= 0 || observation.ndvi > 1) {
      throw new RangeError('Observation de vigueur invalide : valeur finie dans ]0, 1] attendue.');
    }
    for (const key of ['rainZScore', 'tempZScore']) {
      if (observation.climate?.[key] != null && !Number.isFinite(observation.climate[key])) {
        throw new RangeError(`Covariable météo invalide : ${key}.`);
      }
    }
  }
  const distinctFieldIds = new Set(observations.map((o) => o.fieldId));
  const totalPixelsCovered = observations.reduce((s, o) => s + (o.pixelCount || 1), 0);
  const vigorIndexUsed = observations[0]?.vigorIndexUsed || 'EVI';

  const {
    pairPriorStrengthK,
    regimePriorStrengthK,
    monocultureBaselinePriorK,
    minCropPriorStdPct,
  } = CONFIG.hyperparameters;

  const byTargetCrop = new Map();
  for (const obs of observations) {
    if (!byTargetCrop.has(obs.currCrop)) byTargetCrop.set(obs.currCrop, []);
    byTargetCrop.get(obs.currCrop).push(obs);
  }

  const pairDeltas = new Map();
  const priorStdByCrop = new Map();

  for (const [cropB, cropObs] of byTargetCrop.entries()) {
    const adjustedObs = computeWeatherAdjustedNdvi(cropObs);

    const byYear = new Map();
    for (const o of adjustedObs) {
      if (!byYear.has(o.currYear)) byYear.set(o.currYear, []);
      byYear.get(o.currYear).push(o);
    }

    const globalMeanB =
      adjustedObs.reduce((s, o) => s + o.adjustedNdvi, 0) / Math.max(1, adjustedObs.length);
    const globalMono = adjustedObs.filter((o) => o.isMonoculture);
    const globalRot = adjustedObs.filter((o) => !o.isMonoculture);

    const rawGlobalMonoMean =
      globalMono.length > 0
        ? globalMono.reduce((s, o) => s + o.adjustedNdvi, 0) / globalMono.length
        : globalMeanB;
    const rawGlobalRotMean =
      globalRot.length > 0
        ? globalRot.reduce((s, o) => s + o.adjustedNdvi, 0) / globalRot.length
        : globalMeanB;

    const wGlobalMono = globalMono.length / (globalMono.length + monocultureBaselinePriorK);
    const regGlobalMonoMean = wGlobalMono * rawGlobalMonoMean + (1 - wGlobalMono) * globalMeanB;
    const globalUnifiedBaseline = 0.5 * regGlobalMonoMean + 0.5 * rawGlobalRotMean;

    const cropDeltasForPrior = [];

    for (const [, yearObs] of byYear.entries()) {
      const yearMeanAll =
        yearObs.reduce((s, o) => s + o.adjustedNdvi, 0) / Math.max(1, yearObs.length);
      const monoYear = yearObs.filter((o) => o.isMonoculture);
      const rotYear = yearObs.filter((o) => !o.isMonoculture);

      const rawMonoYearMean =
        monoYear.length > 0
          ? monoYear.reduce((s, o) => s + o.adjustedNdvi, 0) / monoYear.length
          : regGlobalMonoMean;
      const rawRotYearMean =
        rotYear.length > 0
          ? rotYear.reduce((s, o) => s + o.adjustedNdvi, 0) / rotYear.length
          : rawGlobalRotMean;

      const wMonoYear = monoYear.length / (monoYear.length + monocultureBaselinePriorK);
      const regMonoYearMean = wMonoYear * rawMonoYearMean + (1 - wMonoYear) * yearMeanAll;

      const wRotYear = rotYear.length / (rotYear.length + monocultureBaselinePriorK);
      const regRotYearMean = wRotYear * rawRotYearMean + (1 - wRotYear) * yearMeanAll;

      const unifiedBaseline = 0.5 * regMonoYearMean + 0.5 * regRotYearMean || globalUnifiedBaseline;

      for (const o of yearObs) {
        if (!Number.isFinite(unifiedBaseline) || unifiedBaseline <= 0) {
          throw new RangeError('Référence de vigueur non positive ou non finie.');
        }
        const deltaPct = validatePhysicalEffectPct((o.adjustedNdvi / unifiedBaseline - 1) * 100);
        const deltaVsMonoPct =
          regMonoYearMean > 0
            ? ((o.adjustedNdvi - regMonoYearMean) / regMonoYearMean) * 100
            : deltaPct;

        cropDeltasForPrior.push(deltaPct);

        if (!pairDeltas.has(o.pairKey)) {
          pairDeltas.set(o.pairKey, []);
        }
        pairDeltas.get(o.pairKey).push({
          fieldId: o.fieldId,
          pixelCount: o.pixelCount || 1,
          interiorPixelCount: o.interiorPixelCount || 0,
          currCrop: o.currCrop,
          deltaPct,
          deltaVsMonoPct,
          year: o.currYear,
          regime: o.climate?.regime || 'normal',
          ndvi: o.ndvi,
          adjustedNdvi: o.adjustedNdvi,
        });
      }
    }

    const meanD =
      cropDeltasForPrior.reduce((a, b) => a + b, 0) / Math.max(1, cropDeltasForPrior.length);
    const stdD =
      cropDeltasForPrior.length > 1
        ? Math.sqrt(
            cropDeltasForPrior.reduce((a, b) => a + (b - meanD) ** 2, 0) /
              (cropDeltasForPrior.length - 1),
          )
        : minCropPriorStdPct * 2;
    priorStdByCrop.set(cropB, Math.max(minCropPriorStdPct, stdD));
  }

  const pairs = {};

  for (const [pairKey, items] of pairDeltas.entries()) {
    const [prevCrop, currCrop] = pairKey.split('>');
    const n = items.length;
    const uniqueFieldsCount = new Set(items.map((x) => x.fieldId)).size;
    const effectiveYearsCount = new Set(items.map((x) => x.year)).size;
    const totalPixels = items.reduce((s, x) => s + x.pixelCount, 0);
    const priorStdPct = priorStdByCrop.get(currCrop) || 7.5;

    let weightedSum = 0;
    let weightTotal = 0;
    for (const item of items) {
      const w = getFieldReliabilityWeight(item);
      weightedSum += item.deltaPct * w;
      weightTotal += w;
    }

    const rawMean = weightedSum / Math.max(1, weightTotal);
    const shrinkage = n / (n + pairPriorStrengthK);
    const mean = rawMean * shrinkage;

    const stdErr = computeClusterRobustStdError(items, rawMean, priorStdPct, pairPriorStrengthK);

    // Régularisation bayésienne hiérarchique des sous-régimes ('normal', 'sec', 'chaud') :
    // Chaque sous-régime est régularisé vers la moyenne globale `mean` de la paire (et non vers 0 %),
    // avec une force de prior `regimePriorStrengthK = 6`. Ainsi, un sous-régime à N=1 ou N=2
    // reste ancré à la moyenne de la paire et n'injecte pas de bruit dans les projections.
    const byRegime = {};
    for (const regime of ['normal', 'sec', 'chaud']) {
      const subItems = items.filter((x) => x.regime === regime);
      const subN = subItems.length;
      if (subN > 0) {
        let subWSum = 0;
        let subWTot = 0;
        for (const x of subItems) {
          const w = getFieldReliabilityWeight(x);
          subWSum += w * x.deltaPct;
          subWTot += w;
        }
        const subRawMean = subWSum / Math.max(1, subWTot);
        const subShrink = subN / (subN + regimePriorStrengthK);
        const subMean = Number((subShrink * subRawMean + (1 - subShrink) * mean).toFixed(2));
        const subStdErr = computeClusterRobustStdError(
          subItems,
          subRawMean,
          priorStdPct,
          regimePriorStrengthK,
        );
        byRegime[regime] = {
          rawMeanEffectPct: Number(subRawMean.toFixed(2)),
          meanEffectPct: subMean,
          stdErrorPct: Number(subStdErr.toFixed(2)),
          intervalPct: physicalEffectInterval(subMean, [
            Math.min(subMean, Number((subMean - subStdErr).toFixed(1))),
            Math.max(subMean, Number((subMean + subStdErr).toFixed(1))),
          ]),
          sampleCount: subN,
          effectiveYearsCount: new Set(subItems.map((x) => x.year)).size,
        };
      } else {
        byRegime[regime] = null;
      }
    }

    const prevFamily = CROP_TAXONOMY[prevCrop]?.family || null;
    const currFamily = CROP_TAXONOMY[currCrop]?.family || null;

    const confidence =
      n >= CONFIG.sampling.minSamplesHighConfidence && effectiveYearsCount >= 3
        ? 'elevee'
        : n >= CONFIG.sampling.minSamplesMediumConfidence && effectiveYearsCount >= 2
          ? 'moyenne'
          : 'faible';

    const roundedMean = Number(mean.toFixed(2));
    const roundedStdErr = Number(stdErr.toFixed(2));

    pairs[pairKey] = {
      from: prevCrop,
      to: currCrop,
      pairKey,
      prevCrop,
      currCrop,
      prevFamily,
      currFamily,
      sameSpecies: prevCrop === currCrop,
      sameBotanicalFamily: prevFamily !== null && prevFamily === currFamily,
      isMonoculture: prevCrop === currCrop,
      rawMeanEffectPct: Number(rawMean.toFixed(2)),
      meanEffectPct: roundedMean,
      gainVsMonoculturePct: null,
      stdErrorPct: roundedStdErr,
      intervalPct: physicalEffectInterval(roundedMean, [
        Math.min(roundedMean, Number((roundedMean - roundedStdErr).toFixed(1))),
        Math.max(roundedMean, Number((roundedMean + roundedStdErr).toFixed(1))),
      ]),
      sampleCount: n,
      distinctFieldsCount: uniqueFieldsCount,
      effectiveYearsCount,
      pixelObservationsCount: totalPixels,
      confidence,
      byRegime,
    };
  }

  for (const stat of Object.values(pairs)) {
    const mono = pairs[`${stat.to}>${stat.to}`];
    stat.gainVsMonoculturePct = mono
      ? relativeGainPct(stat.meanEffectPct, mono.meanEffectPct)
      : null;
  }

  return {
    referenceBaselineType: 'unified_balanced_regional_baseline',
    effectInterpretation: 'observational_relative_vigor',
    weatherAdjustmentMethod: 'centered_log_ridge',
    fieldSegmentationMethod: 'connected_crop_history_signatures',
    vigorIndexUsed,
    totalDistinctFieldsInRegion: distinctFieldIds.size,
    totalFieldTransitions: observations.length,
    totalPixelTransitions: totalPixelsCovered,
    totalObservations: observations.length,
    observedPairsCount: Object.keys(pairs).length,
    pairs,
  };
}
