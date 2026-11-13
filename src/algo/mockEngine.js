/**
 * Demo engine. It respects the contract exactly, so the whole UI works before
 * the real algorithm exists. Every number here is illustrative (meta.demo = true):
 * the shapes matter, not the values.
 *
 * Do not add real agronomy here: the real algorithm replaces this file's role
 * through src/algo/remoteEngine.js (or a local module with the same interface).
 */
import { CROPS } from '../data/crops.js';
import { buildCalendar, cycleLength, rotationErrors, toSlots } from '../lib/rotation.js';
import { soilByCalendar, countTrue } from '../lib/soil.js';

/** Illustrative effect of "previous → next" on yield, in %. Inspired by the studies, not calibrated. */
const PAIR_EFFECT = {
  'mais>soya': 8,
  'soya>ble': 8,
  'soya>mais': 2.5,
  'ble>mais': 0.9,
  'soya>orge': 6,
  'luzerne>mais': 10,
  'luzerne>ble': 6,
  'patate>ble': 3,
  'ble>soya': 2,
  'orge>soya': 2,
  'mais>patate': 1,
  'patate>soya': 2,
};
const PAIR_TEXT = {
  'soya>ble': 'Le blé après le soya profite de l’azote laissé par le soya.',
  'mais>soya': 'Le soya après le maïs donne un bon gain de rendement.',
  'soya>mais': 'Le maïs après le soya gagne un peu de rendement grâce à l’azote.',
  'luzerne>mais': 'Après la luzerne, le maïs trouve un sol riche en azote et bien structuré.',
  'soya>orge': 'L’orge après le soya profite de l’azote laissé dans le sol.',
};
/** Illustrative gross revenue per hectare and year, in $. */
const BASE_REV = { mais: 1100, soya: 980, ble: 820, orge: 720, patate: 1650, luzerne: 760 };
const MONO_SCORES = { eau: 58, sol: 52, resilience: 48, revenu: 64 };
const MS_SCORES = { eau: 64, sol: 62, resilience: 60, revenu: 67 };

const clamp = (v) => Math.max(5, Math.min(98, Math.round(v)));
const round1 = (v) => Math.round(v * 10) / 10;
const seedOf = (s) => [...String(s)].reduce((a, c) => a + c.charCodeAt(0), 0) % 7;
const wait = (ms) => (ms > 0 ? new Promise((r) => setTimeout(r, ms)) : Promise.resolve());

function analyseSection(farmInput, section) {
  const { startYear, horizonYears } = farmInput.farm;
  const slots = toSlots(section.rotation);
  const L = slots.length;
  const crops = slots.map((s) => s.crop);
  const distinct = new Set(crops).size;
  let rep = 0;
  let pairSum = 0;
  let known = 0;
  const explanations = [];
  for (let i = 0; i < L && L > 1; i++) {
    const a = crops[i];
    const b = crops[(i + 1) % L];
    if (a === b && CROPS[a].years === 1) {
      rep++;
      pairSum -= 4.3;
      continue;
    }
    if (a === b) continue;
    const key = `${a}>${b}`;
    if (key in PAIR_EFFECT) {
      pairSum += PAIR_EFFECT[key];
      known++;
    } else pairSum += 1;
    if (PAIR_TEXT[key] && !explanations.some((e) => e.code === key)) {
      explanations.push({ code: key, message: PAIR_TEXT[key] });
    }
  }
  const pairs = Math.max(1, L);
  const avgPair = pairSum / pairs;
  const cal = buildCalendar(section.rotation, {
    offset: section.offset ?? 0,
    startYear,
    horizonYears,
  });
  const soil = soilByCalendar(cal);
  const frac = (role) => countTrue(soil[role]) / Math.max(1, cal.length);
  const seed = seedOf(section.id);

  const scores = {
    eau: clamp(52 + distinct * 4 + frac('couverture') * 12 + frac('racines') * 8 - rep * 8 + seed),
    sol: clamp(
      44 +
        distinct * 5 +
        frac('azote') * 22 +
        frac('couverture') * 14 +
        frac('racines') * 10 -
        rep * 10,
    ),
    resilience: clamp(46 + distinct * 7 + frac('sec') * 10 + avgPair - rep * 9),
    revenu: clamp(
      38 + (crops.reduce((a, c) => a + BASE_REV[c], 0) / L - 700) / 22 + avgPair * 1.5 - seed,
    ),
  };

  const lo = Math.max(-5, Math.round(avgPair * 0.6 + distinct * 0.8));
  const hi = lo + 3;
  const mid = (lo + hi) / 2;
  const meanRev = crops.reduce((a, c) => a + BASE_REV[c], 0) / L;
  const perHaYear = Math.round(meanRev * (1 + mid / 100) * 0.92);
  const monoPerHa = Math.round(1100 * 0.957 * 0.92);
  const msPerHa = Math.round(((1100 + 980) / 2) * 1.04 * 0.92);

  const series = cal.map((y, t) => {
    const v = BASE_REV[y.crop] * (1 + mid / 100) * 0.92 * (1 + 0.06 * Math.sin(t * 1.7 + seed));
    return {
      year: y.year,
      value: Math.round(v),
      low: Math.round(v * 0.9),
      high: Math.round(v * 1.07),
    };
  });
  const baseline = (base, drift) =>
    cal.map((y, t) => ({
      year: y.year,
      value: Math.round(base * (1 + 0.05 * Math.sin(t * 1.3 + 1)) - t * drift),
    }));

  const diversity = Math.min(1, distinct / 5);
  const k = farmInput.options?.stressYears === 3 ? 1.6 : 1;
  const shock = (rot, base, deltas) => ({
    yieldPct: rot.map((v) => Math.round(v * k)),
    baselineYieldPct: base.map((v) => Math.round(v * k)),
    scores: Object.fromEntries(
      Object.entries(scores).map(([key, v]) => [
        key,
        clamp(v + deltas[key] * k * (1 - diversity * 0.4)),
      ]),
    ),
  });
  const secGain = frac('sec') * 5;
  const stress = {
    normal: shock([0, 0], [0, 0], { eau: 0, sol: 0, resilience: 0, revenu: 0 }),
    sec: shock([-(16 - distinct * 1.4 - secGain), -(22 - distinct * 1.6 - secGain)], [-22, -30], {
      eau: -18,
      sol: -6,
      resilience: -9,
      revenu: -14,
    }),
    chaud: shock([-(10 - distinct), -(14 - distinct)], [-14, -19], {
      eau: -12,
      sol: -4,
      resilience: -8,
      revenu: -11,
    }),
    ravageurs: shock([-(9 - distinct), -(13 - distinct)], [-15, -24], {
      eau: 0,
      sol: -3,
      resilience: -5,
      revenu: -7,
    }),
  };

  const suggestions = [];
  if (countTrue(soil.racines) === 0) {
    suggestions.push({
      code: 'ADD_DEEP_ROOTS',
      message: 'Aucune racine profonde : un radis fourrager l’hiver casserait le sol tassé.',
    });
  }
  if (countTrue(soil.sec) === 0 && crops.includes('mais')) {
    const s = stress.sec.yieldPct;
    suggestions.push({
      code: 'SWAP_MAIS_ORGE',
      scenario: 'sec',
      message: 'De l’orge à la place du maïs réduirait la perte des années sèches.',
      yieldPctAfter: [s[0] + 3, s[1] + 4],
    });
  }
  if (countTrue(soil.couverture) === 0) {
    suggestions.push({
      code: 'ADD_COVER',
      message:
        'Aucune couverture d’hiver : un trèfle après le blé protégerait le sol et ajouterait de l’azote.',
    });
  }

  const ratio = known / pairs;
  let confidence = ratio >= 0.75 ? 'elevee' : ratio >= 0.4 ? 'moyenne' : 'faible';
  if (horizonYears >= 15) confidence = confidence === 'elevee' ? 'moyenne' : 'faible';

  return {
    id: section.id,
    scores,
    confidence,
    comparisons: {
      'mais-continu': {
        yieldGainPct: [lo, hi],
        revenueDeltaPerHaYear: perHaYear - monoPerHa,
        scores: MONO_SCORES,
      },
      'mais-soya': {
        yieldGainPct: [Math.max(-5, lo - 4), Math.max(-2, hi - 5)],
        revenueDeltaPerHaYear: perHaYear - msPerHa,
        scores: MS_SCORES,
      },
    },
    revenue: {
      perHaYear,
      series,
      baselines: { 'mais-continu': baseline(monoPerHa, 4), 'mais-soya': baseline(msPerHa, 1) },
    },
    workload: distinct >= 5 ? 'elevee' : distinct === 4 ? 'moyenne' : 'faible',
    stress,
    suggestions,
    explanations,
    warnings: rotationErrors(section.rotation).map((message) => ({ code: 'ROTATION', message })),
  };
}

const PRIORITY_KEY = { revenu: 'revenu', resilience: 'resilience', sol: 'sol', eau: 'eau' };
const WORKLOAD_SCORE = { faible: 85, moyenne: 65, elevee: 45 };
const WEIGHTS = [0.35, 0.25, 0.18, 0.13, 0.09];

const PROPOSALS = {
  1: [{ crop: 'mais', years: 1, cover: 'seigle' }],
  2: [
    { crop: 'mais', years: 1, cover: null },
    { crop: 'soya', years: 1, cover: 'seigle' },
  ],
  3: [
    { crop: 'mais', years: 1, cover: 'seigle' },
    { crop: 'soya', years: 1, cover: null },
    { crop: 'ble', years: 1, cover: 'trefle' },
  ],
  4: [
    { crop: 'soya', years: 1, cover: null },
    { crop: 'ble', years: 1, cover: 'trefle' },
    { crop: 'mais', years: 1, cover: 'seigle' },
    { crop: 'patate', years: 1, cover: null },
  ],
  5: [
    { crop: 'mais', years: 1, cover: 'seigle' },
    { crop: 'soya', years: 1, cover: null },
    { crop: 'luzerne', years: 3, cover: null },
  ],
  6: [
    { crop: 'soya', years: 1, cover: null },
    { crop: 'ble', years: 1, cover: 'trefle' },
    { crop: 'mais', years: 1, cover: 'seigle' },
    { crop: 'luzerne', years: 3, cover: null },
  ],
};

/**
 * @param {{ latencyMs?: number }} [options]
 * @returns {import('./types.js').Engine}
 */
export function createMockEngine({ latencyMs = 0 } = {}) {
  return {
    name: 'mock',

    async evaluateFarm(input) {
      await wait(latencyMs);
      const sections = input.sections.map((s) => analyseSection(input, s));
      const totalHa = input.sections.reduce((a, s) => a + s.areaHa, 0) || 1;
      const weighted = (plan) =>
        input.farm.priorities.reduce((acc, p, i) => {
          const v = p === 'travail' ? WORKLOAD_SCORE[plan.workload] : plan.scores[PRIORITY_KEY[p]];
          return acc + v * WEIGHTS[i];
        }, 0);
      const score = clamp(
        sections.reduce((a, p, i) => a + weighted(p) * input.sections[i].areaHa, 0) / totalHa,
      );
      const revenuePerYear = sections.reduce(
        (a, p, i) => a + p.revenue.perHaYear * input.sections[i].areaHa,
        0,
      );
      return {
        version: '1.0',
        meta: { engine: 'mock', demo: true, generatedAt: new Date().toISOString() },
        farm: { score, revenuePerYear },
        sections,
      };
    },

    async proposeRotation({ cycleYears }) {
      await wait(latencyMs);
      const rotation = structuredClone(PROPOSALS[cycleYears] ?? PROPOSALS[4]);
      return {
        rotation,
        reasons: [
          'Une légumineuse avant les cultures gourmandes en azote.',
          'Aucune culture ne revient avant son délai de retour.',
          'Une couverture d’hiver quand le sol resterait nu.',
        ],
      };
    },

    async getFieldData({ farm, sectionId }) {
      await wait(latencyMs);
      const seed = seedOf(sectionId);
      const sensors = !!farm.farm.sensors;
      const spark = (base, amp, phase) =>
        Array.from({ length: 10 }, (_, i) => round1(base + amp * Math.sin(i * 0.9 + phase)));
      return {
        sectionId,
        demo: true,
        metrics: [
          {
            id: 'rain',
            label: 'Pluie de la saison',
            value: 520 + seed * 10,
            unit: 'mm',
            source: 'NASA GPM IMERG',
            series: spark(540, 40, seed),
            explain:
              'Total de pluie de mai à septembre. Plus il pleut, plus la rotation profite à certaines cultures.',
          },
          {
            id: 'soilMoisture',
            label: 'Humidité du sol',
            value: sensors ? 0.31 : round1(0.26 + seed / 100),
            unit: 'm³/m³',
            source: sensors ? 'Vos capteurs · mesure' : 'NASA SMAP · estimation',
            fromSensors: sensors,
            series: spark(0.28, 0.03, seed + 1),
            explain:
              'La part d’eau dans le sol en surface. Avec des capteurs, l’appli remplace l’estimation du satellite par vos mesures.',
          },
          {
            id: 'temperature',
            label: 'Température moyenne',
            value: round1(18 + seed / 5),
            unit: '°C',
            source: 'NASA POWER',
            series: spark(18, 0.8, seed + 2),
            explain:
              'Moyenne de la saison de croissance. La tendance monte : les années chaudes deviennent plus fréquentes.',
          },
          {
            id: 'et',
            label: 'Évapotranspiration',
            value: round1(3.4 + seed / 10),
            unit: 'mm/jour',
            source: 'NASA ECOSTRESS',
            series: spark(3.6, 0.3, seed + 3),
            explain:
              'L’eau que les plantes et le sol perdent dans l’air chaque jour : ce que les cultures consomment.',
          },
          {
            id: 'ndvi',
            label: 'Vigueur des plantes',
            value: round1(0.68 + seed / 50),
            unit: 'NDVI',
            source: 'NASA HLS',
            series: spark(0.6, 0.15, seed + 4),
            explain:
              'Un indice de 0 à 1 qui mesure à quel point la végétation est verte et en santé, calculé à partir des images satellites.',
          },
          {
            id: 'soil',
            label: 'Type de sol',
            value: seed % 2 ? 'Loam sableux' : 'Loam argileux',
            unit: `${(2.6 + seed / 10).toFixed(1).replace('.', ',')} % MO`,
            source: 'SoilGrids',
            explain:
              'La texture du sol et sa matière organique (MO). Un sol argileux garde mieux l’eau.',
          },
        ],
      };
    },
  };
}

export { cycleLength };
