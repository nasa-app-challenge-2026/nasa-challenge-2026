import { describe, expect, it } from 'vitest';
import {
  alertAdvice,
  assessSection,
  buildEvents,
  burnWindow,
  burntYears,
  classifyDnbr,
  clearFraction,
  clusterHotspots,
  cropHistory,
  dangerOf,
  distanceKm,
  fieldFuel,
  fieldSeason,
  fireCoverAdvice,
  fireStatus,
  fireSummary,
  fmtDay,
  fmtKm,
  fmtPeriod,
  fuelInfo,
  isMajorFire,
  isRecent,
  isVegetationFire,
  majorityClass,
  medianFromStats,
  nbrExpression,
  normalizeBurns,
  normalizeHotspots,
  outerRings,
  pointInPolygon,
  rotationAdvice,
  samplePoints,
  searchBbox,
  sectionKm,
  soilFromSoilGrids,
  splitByAge,
  textureOf,
} from '../src/lib/wildfire.js';
import { aciClass } from '../src/data/cropInventory.js';

const SQUARE = [
  [45.01, -73.01],
  [45.01, -72.99],
  [44.99, -72.99],
  [44.99, -73.01],
];
const farm = {
  id: 'farm',
  location: { lat: 45, lon: -73 },
  boundary: SQUARE,
  sections: [
    {
      id: 'A',
      polygon: [
        [45.01, -73.01],
        [45.01, -73.0],
        [44.99, -73.0],
        [44.99, -73.01],
      ],
      rotation: [
        { crop: 'mais', years: 1, cover: null },
        { crop: 'soya', years: 1, cover: null },
        { crop: 'ble', years: 1, cover: null },
      ],
      offset: 0,
    },
    {
      id: 'B',
      polygon: [
        [45.01, -73.0],
        [45.01, -72.99],
        [44.99, -72.99],
        [44.99, -73.0],
      ],
      rotation: [
        { crop: 'ble', years: 1, cover: null },
        { crop: 'mais', years: 1, cover: null },
        { crop: 'soya', years: 1, cover: null },
      ],
      offset: 0,
    },
  ],
};
const hs = (id, lat, lon, date, fuel = 'farm') => ({
  type: 'Feature',
  id,
  geometry: { type: 'Point', coordinates: [lon, lat] },
  properties: { rep_date: date, fuel, frp: 3, sensor: 'VIIRS-I', satellite: 'NOAA-20' },
});

describe('geometry', () => {
  it('measures distances and finds points in polygons', () => {
    expect(distanceKm([45, -73], [46, -73])).toBeCloseTo(111.2, 0);
    expect(pointInPolygon([45, -73], SQUARE)).toBe(true);
    expect(pointInPolygon([45.02, -73], SQUARE)).toBe(false);
  });

  it('grows the farm box by the search radius', () => {
    const [minLon, minLat, maxLon, maxLat] = searchBbox(
      [
        [45, -73],
        [45, -73],
      ],
      10,
    );
    expect(maxLat - minLat).toBeCloseTo(20 / 111.32, 3);
    expect(maxLon - minLon).toBeGreaterThan(maxLat - minLat);
  });

  it('samples five points inside a section', () => {
    const pts = samplePoints(SQUARE);
    expect(pts).toHaveLength(5);
    pts.forEach((p) => expect(pointInPolygon(p, SQUARE)).toBe(true));
    expect(samplePoints([])).toEqual([]);
  });
});

describe('fire events', () => {
  it('reads hotspots and burned areas, swapping lon/lat and thinning big outlines', () => {
    const [h] = normalizeHotspots({ features: [hs('h1', 45, -73, '2025-05-01T18:00:00Z')] });
    expect(h).toMatchObject({ lat: 45, lon: -73, day: '2025-05-01', fuel: 'farm' });

    const big = Array.from({ length: 500 }, (_, i) => [
      -73 + Math.cos(i / 80),
      45 + Math.sin(i / 80),
    ]);
    const rings = outerRings({
      type: 'MultiPolygon',
      coordinates: [
        [
          [
            [-73, 45],
            [-72, 45],
            [-72, 46],
            [-73, 45],
          ],
        ],
        [big],
      ],
    });
    expect(rings[0]).toHaveLength(80);
    expect(rings[0][0]).toEqual([45, -72]);
    expect(rings[1]).toHaveLength(4);
  });

  it('groups hotspots of the same fire, splits distant or later ones', () => {
    const pts = normalizeHotspots({
      features: [
        hs('a', 45, -73, '2025-05-01T10:00:00Z'),
        hs('b', 45.005, -73.005, '2025-05-02T10:00:00Z'),
        hs('c', 45.5, -73, '2025-05-01T10:00:00Z'),
        hs('d', 45, -73, '2025-06-20T10:00:00Z'),
      ],
    });
    expect(clusterHotspots(pts).map((g) => g.points.length)).toEqual([2, 1, 1]);
  });

  it('merges hotspots into the burned area they fall in, which gives it a date', () => {
    const burns = normalizeBurns({
      features: [
        {
          id: 'nbac.1',
          properties: { year: 2025, adj_ha: 40, firecaus: 'Human', hs_sdate: null, ag_sdate: null },
          geometry: {
            type: 'Polygon',
            coordinates: [
              [
                [-73.02, 44.98],
                [-73.0, 44.98],
                [-73.0, 45.02],
                [-73.02, 45.02],
                [-73.02, 44.98],
              ],
            ],
          },
        },
      ],
    });
    const hotspots = normalizeHotspots({
      features: [
        hs('in', 45, -73.005, '2025-04-28T18:00:00Z'),
        hs('far', 45.3, -73, '2025-08-01T18:00:00Z', 'D2'),
        hs('city', 45.0, -72.995, '2024-07-29T18:00:00Z', 'urban'),
      ],
    });
    const events = buildEvents({ hotspots, burns }, farm, Date.parse('2026-11-14'));
    const burn = events.find((e) => e.kind === 'burn');
    expect(burn).toMatchObject({ day: '2025-04-28', hotspots: 1, km: 0, sections: ['A'] });
    expect(events.filter((e) => e.kind === 'hotspots')).toHaveLength(2);
    expect(events[0].sections.length).toBeGreaterThan(0);
    expect(events[events.length - 1].km).toBeGreaterThan(30);

    const city = events.find((e) => e.fuel === 'urban');
    expect(city.sections).toEqual(['B']);
    expect(isVegetationFire(city)).toBe(false);
    expect(isVegetationFire(burn)).toBe(true);
    expect(fireSummary(events)).toMatchObject({ total: 3, onFarm: 2, active: 0 });
  });

  it('sees a long fire as one event, from its first to its last hotspot', () => {
    const perimeters = [
      {
        id: 'm3.1',
        first: '2026-05-02',
        last: '2026-05-20',
        ha: 13222,
        rings: [
          [
            [45.05, -73.05],
            [45.05, -72.95],
            [44.95, -72.95],
            [44.95, -73.05],
          ],
        ],
      },
    ];
    const hotspots = normalizeHotspots({
      features: [
        hs('early', 45.04, -73.04, '2026-05-02T18:00:00Z'),
        hs('late', 45, -73, '2026-05-27T18:00:00Z'),
        hs('next-year', 45, -73, '2027-05-02T18:00:00Z'),
      ],
    });
    const events = buildEvents({ hotspots, perimeters }, farm, Date.parse('2026-11-14'));
    const fire = events.find((e) => e.kind === 'perimeter');
    expect(fire).toMatchObject({ day: '2026-05-02', lastDay: '2026-05-27', hotspots: 2 });
    expect(fire.sections).toEqual(['A', 'B']);
    expect(events.filter((e) => e.kind === 'hotspots')).toHaveLength(1);
    expect(fmtPeriod(fire.day, fire.lastDay)).toBe('du 2 mai 2026 au 27 mai 2026');
    // Only the late hotspot is within 2 km of the farm: it frames the burn of the sections.
    expect(burnWindow(fire)).toEqual(['2026-05-27', '2026-05-27']);
    expect(burnWindow({ day: '2026-05-02' })).toEqual(['2026-05-02', '2026-05-02']);
    expect(fmtPeriod('2026-05-02', '2026-05-02')).toBe('2 mai 2026');
  });

  it('describes fuels in plain words', () => {
    expect(fuelInfo('farm')).toMatchObject({ agricultural: true, vegetation: true });
    expect(fuelInfo('C2').label).toBe('Forêt de conifères');
    expect(fuelInfo('urban').vegetation).toBe(false);
  });
});

describe('recent fires, archives and alarms', () => {
  const now = Date.parse('2026-11-14');
  const ev = (o) => ({
    kind: 'hotspots',
    sections: [],
    km: 10,
    hotspots: 1,
    frpMax: 2,
    fuel: 'farm',
    ...o,
  });

  it('puts fires older than 12 months in the archives', () => {
    const fresh = ev({ day: '2026-03-01' });
    const longFire = ev({ day: '2025-10-01', lastDay: '2025-11-20' });
    const old = ev({ day: '2023-05-01' });
    expect(isRecent(fresh, now)).toBe(true);
    expect(isRecent(longFire, now)).toBe(true);
    expect(isRecent(old, now)).toBe(false);
    expect(isRecent(ev({ day: null }), now)).toBe(false);
    const { recent, archived } = splitByAge([old, fresh, longFire], now);
    expect(recent).toEqual([fresh, longFire]);
    expect(archived).toEqual([old]);
  });

  it('keeps the alarm for big fires', () => {
    expect(isMajorFire(ev({}))).toBe(false);
    expect(isMajorFire(ev({ hotspots: 3 }))).toBe(true);
    expect(isMajorFire(ev({ frpMax: 40 }))).toBe(true);
    expect(isMajorFire(ev({ kind: 'perimeter', hotspots: 0 }))).toBe(true);
  });

  it('sees no risk in a lone weak hotspot on farmland', () => {
    const st = fireStatus([ev({ active: true, km: 18.2, day: '2026-11-12' })]);
    expect(st).toMatchObject({ tone: 'calm', title: 'Aucun risque pour le moment' });
  });

  it('warns when today’s fire danger is high, not when it is low', () => {
    expect(fireStatus([], dangerOf(2))).toMatchObject({
      tone: 'warn',
      title: 'Danger d’incendie élevé aujourd’hui',
    });
    expect(fireStatus([], dangerOf(0)).tone).toBe('calm');
    expect(fireStatus([], null).tone).toBe('calm');
  });

  it('alerts for a big fire burning this week, the closest one', () => {
    const st = fireStatus([
      ev({ active: true, km: 3, day: '2026-11-12' }),
      ev({ kind: 'perimeter', active: true, km: 12, day: '2026-11-01', lastDay: '2026-11-13' }),
      ev({ kind: 'perimeter', active: false, km: 1, day: '2026-07-01' }),
    ]);
    expect(st).toMatchObject({ tone: 'alert', title: 'Feu actif à 12 km' });
    expect(st.text).toMatch(/13 nov\. 2026/);
  });

  it('says nothing to worry about otherwise, and ignores buildings', () => {
    expect(fireStatus([]).tone).toBe('calm');
    expect(fireStatus([ev({ active: false })]).tone).toBe('calm');
    expect(fireStatus([ev({ active: true, hotspots: 9, fuel: 'urban' })]).tone).toBe('calm');
  });
});

describe('burn severity', () => {
  it('counts clear pixels from the HLS cloud mask', () => {
    const hist = [
      [22, 3, 328, 14, 18, 1, 36, 3],
      [64, 80, 128, 144, 160, 176, 192, 224],
    ];
    expect(clearFraction(hist)).toBeCloseTo((425 - 18) / 425, 5);
    expect(clearFraction([[10], [2]])).toBe(0);
    expect(clearFraction(null)).toBe(0);
  });

  it('classifies dNBR on the international thresholds', () => {
    expect(classifyDnbr(-0.2).id).toBe('repousse');
    expect(classifyDnbr(0.007).id).toBe('intact');
    expect(classifyDnbr(0.188)).toMatchObject({ id: 'faible', level: 1 });
    expect(classifyDnbr(0.3).id).toBe('moderee');
    expect(classifyDnbr(0.5).id).toBe('elevee');
    expect(classifyDnbr(0.9)).toMatchObject({ id: 'tres-elevee', level: 3 });
    expect(classifyDnbr(null)).toBeNull();
  });

  it('uses the right bands per sensor and reads the median', () => {
    expect(nbrExpression('hls2-s30')).toBe('(B8A-B12)/(B8A+B12)');
    expect(nbrExpression('hls2-l30')).toBe('(B05-B07)/(B05+B07)');
    const stats = (median, valid) => ({
      properties: { statistics: { nbr: { median, valid_percent: valid } } },
    });
    expect(medianFromStats(stats(0.21, 100))).toBe(0.21);
    expect(medianFromStats(stats(0.21, 20))).toBeNull();
    expect(medianFromStats({})).toBeNull();
  });
});

describe('soil and crops', () => {
  const layer = (name, values, d = 10) => ({
    name,
    unit_measure: { d_factor: d },
    depths: values.map((mean) => ({ values: { mean } })),
  });

  it('reads SoilGrids and names the texture', () => {
    const soil = soilFromSoilGrids({
      properties: {
        layers: [
          layer('clay', [264, 268]),
          layer('sand', [390, 387]),
          layer('silt', [346, 345]),
          layer('soc', [513, 359]),
          layer('phh2o', [67, 68]),
        ],
      },
    });
    expect(soil).toEqual({ clay: 26.6, sand: 38.9, silt: 34.6, soc: 43.6, ph: 6.8 });
    expect(textureOf(soil).id).toBe('loam');
    expect(textureOf({ clay: 5, sand: 80, silt: 15 })).toMatchObject({
      erosion: 'vent',
      fragile: true,
    });
    expect(textureOf({ clay: 10, sand: 20, silt: 70 }).id).toBe('limoneux');
    expect(soilFromSoilGrids({ properties: { layers: [layer('clay', [null])] } })).toBeNull();
  });

  it('builds the crop history per section and finds burnt years', () => {
    expect(majorityClass(['147', '147', '158', '10', 'NoData'])).toMatchObject({
      code: 147,
      crop: 'mais',
      share: 2 / 3,
    });
    expect(majorityClass(['10'])).toBeNull();
    const h = cropHistory(
      [
        [2023, ['60', '60', '153', '146', '146', '146']],
        [2022, ['136', '136', '136', '146', '146', '146']],
        [2024, null],
      ],
      ['A', 'A', 'A', 'B', 'B', 'B'],
    );
    expect(h.A.map((y) => y.year)).toEqual([2022, 2023, 2024]);
    expect(h.A[1].class.label).toBe('Zone brûlée');
    expect(h.A[2].class).toBeNull();
    expect(burntYears(h.A)).toEqual([2023]);
    expect(burntYears(h.B)).toEqual([]);
    expect(aciClass('158').label).toBe('Soya');
  });
});

describe('impact and rotation', () => {
  const sandy = { clay: 5, sand: 80, silt: 15, soc: 9 };

  it('says nothing burned when nothing was measured', () => {
    const a = assessSection({ nearestKm: 4 });
    expect(a).toMatchObject({ level: 0, burnLevel: 0 });
    expect(a.impacts[0]).toMatch(/moins de 10 km/);
  });

  it('rates a measured burn and adds soil and rain warnings', () => {
    const a = assessSection({ severity: classifyDnbr(0.3), soil: sandy, rain7: 32, ageYears: 0.2 });
    expect(a).toMatchObject({ level: 2, tone: 'bad' });
    expect(a.impacts.join(' ')).toMatch(/sableux/);
    expect(a.impacts.join(' ')).toMatch(/32 mm/);
    expect(a.actions.join(' ')).toMatch(/légumineuse/);
    expect(a.actions.join(' ')).toMatch(/fumier/);
  });

  it('lowers the effect of a fire 3 years old or more, without hiding that it burned', () => {
    const a = assessSection({ severity: classifyDnbr(0.19), ageYears: 3.5 });
    expect(a).toMatchObject({ level: 0, burnLevel: 1 });
    expect(a.impacts[0]).toMatch(/brûlé faiblement/);
    expect(assessSection({ burnt: true }).level).toBe(1);
  });

  it('adds a winter cover after a light burn', () => {
    const adv = rotationAdvice(farm.sections[1], 1);
    expect(adv.changes).toEqual([{ kind: 'cover', to: 'seigle' }]);
    expect(adv.rotation[0]).toMatchObject({ crop: 'ble', cover: 'seigle' });
  });

  it('swaps a demanding crop for a lighter one after a moderate burn (legume if the delay allows)', () => {
    const adv = rotationAdvice(farm.sections[0], 2);
    expect(adv.changes[0]).toEqual({ kind: 'crop', from: 'mais', to: 'orge' });
    expect(adv.changes[1]).toEqual({ kind: 'cover', to: 'trefle' });
  });

  it('respects return delays and the section offset', () => {
    const sec = {
      rotation: [
        { crop: 'ble', years: 1, cover: null },
        { crop: 'mais', years: 1, cover: null },
        { crop: 'orge', years: 1, cover: null },
        { crop: 'patate', years: 1, cover: null },
      ],
      offset: 1,
    };
    const adv = rotationAdvice(sec, 2);
    expect(adv.index).toBe(1);
    expect(adv.changes[0]).toEqual({ kind: 'crop', from: 'mais', to: 'soya' });
    expect(rotationAdvice(sec, 0)).toBeNull();
  });
});

describe('active fire nearby: advice per section', () => {
  // Hotspots 3 km west of section A (A is the west half of the farm, B the east half).
  const fire = {
    kind: 'hotspots',
    km: 3,
    sections: [],
    points: [
      [45.0, -73.05],
      [45.002, -73.049],
    ],
  };
  const withCrops = (a, b) => [
    { ...farm.sections[0], currentCrop: a },
    { ...farm.sections[1], currentCrop: b },
  ];
  const august = Date.parse('2026-08-20');

  it('knows the farm season and how the crop in the field burns', () => {
    expect(fieldSeason(Date.parse('2026-05-02'))).toBe('semis');
    expect(fieldSeason(Date.parse('2026-07-15'))).toBe('pousse');
    expect(fieldSeason(august)).toBe('recolte');
    expect(fieldSeason(Date.parse('2026-11-14'))).toBe('dormance');
    expect(fieldFuel('ble', 'recolte').level).toBe('eleve');
    expect(fieldFuel('soya', 'pousse').level).toBe('faible');
    expect(fieldFuel('inconnue', 'pousse')).toBeNull();
  });

  it('measures each section’s distance to the fire', () => {
    expect(sectionKm(farm.sections[0], fire)).toBeCloseTo(3.1, 1);
    expect(sectionKm(farm.sections[1], fire)).toBeGreaterThan(3.8);
    expect(sectionKm(farm.sections[1], { ...fire, sections: ['B'] })).toBe(0);
    expect(sectionKm(farm.sections[0], { kind: 'burn', rings: [SQUARE] })).toBe(0);
  });

  it('puts the section on the fire side first, with field work and a winter cover', () => {
    const adv = alertAdvice(fire, withCrops('ble', 'soya'), { now: august });
    expect(adv.season).toBe('recolte');
    expect(adv.sections.map((r) => [r.id, r.front])).toEqual([
      ['A', true],
      ['B', false],
    ]);
    const [a, b] = adv.sections;
    expect(a.fuel.level).toBe('eleve');
    expect(a.tips.join(' ')).toMatch(/récoltez cette section en premier/);
    expect(a.tips.join(' ')).toMatch(/disque/);
    // First year of A's plan is corn: rye after it, return delays untouched.
    expect(a.change.changes).toEqual([{ kind: 'cover', to: 'seigle' }]);
    expect(a.change.rotation[0]).toMatchObject({ crop: 'mais', cover: 'seigle' });
    expect(a.change.rotation.map((e) => e.crop)).toEqual(['mais', 'soya', 'ble']);
    expect(b.change).toBeNull();
    expect(b.tips.join(' ')).toMatch(/Plus loin du feu/);
    expect(adv.general.join(' ')).toMatch(/moissonneuse/);
    expect(adv.general.join(' ')).toMatch(/Le reste de la rotation ne change pas/);
  });

  it('takes the cover from the farmer’s seed reserve, and says when it is missing', () => {
    const sections = withCrops('ble', 'soya');
    const clover = alertAdvice(fire, sections, { now: august, seeds: { covers: ['trefle'] } });
    expect(clover.sections[0].change.changes[0].to).toBe('trefle');
    expect(clover.sections[0].change.missingSeeds).toEqual([]);
    const none = fireCoverAdvice(sections[0], { covers: ['radis'] });
    expect(none.changes[0].to).toBe('seigle');
    expect(none.missingSeeds).toEqual(['seigle']);
  });

  it('leaves green crops alone and keeps a cover or alfalfa already planned', () => {
    const july = Date.parse('2026-07-10');
    const green = alertAdvice(fire, withCrops('soya', 'mais'), { now: july }).sections[0];
    expect(green.tips).toEqual([
      'Culture verte ou peu de résidus : elle brûle mal, pas de travail du sol à faire.',
    ]);
    const covered = {
      ...farm.sections[0],
      rotation: [
        { crop: 'mais', years: 1, cover: 'seigle' },
        ...farm.sections[0].rotation.slice(1),
      ],
    };
    expect(alertAdvice(fire, [covered], { now: july }).sections[0]).toMatchObject({
      change: null,
      keep: 'cover',
    });
    const alfalfa = {
      ...farm.sections[0],
      rotation: [
        { crop: 'luzerne', years: 3, cover: null },
        { crop: 'mais', years: 1, cover: null },
      ],
    };
    expect(alertAdvice(fire, [alfalfa], { now: july }).sections[0].keep).toBe('luzerne');
  });

  it('leaves a section on fire to the burn measurement; the next one is on the fire side', () => {
    const adv = alertAdvice({ ...fire, sections: ['A'] }, withCrops('ble', 'ble'), { now: august });
    const [a, b] = adv.sections;
    expect(a).toMatchObject({ id: 'A', km: 0, onFire: true, change: null });
    expect(a.tips.join(' ')).toMatch(/pompiers/);
    expect(b).toMatchObject({ id: 'B', front: true });
    expect(b.change).not.toBeNull();
  });

  it('trusts the event for “on fire”: a section that only grazes the outline is beside it', () => {
    const burn = { kind: 'burn', km: 0, sections: ['A'], rings: [SQUARE] };
    const [a, b] = alertAdvice(burn, withCrops(null, null), {
      now: Date.parse('2023-05-02'),
    }).sections;
    expect(a).toMatchObject({ id: 'A', onFire: true });
    expect(b).toMatchObject({ id: 'B', onFire: false, front: true, km: 0 });
    expect(b.tips.join(' ')).toMatch(/disque/);
  });
});

describe('formatting', () => {
  it('writes dates and distances in French', () => {
    expect(fmtDay('2023-05-01')).toBe('1 mai 2023');
    expect(fmtDay(null)).toBe('date inconnue');
    expect(fmtKm(0)).toBe('sur la ferme');
    expect(fmtKm(0.35)).toBe('à 350 m');
    expect(fmtKm(4.24)).toBe('à 4,2 km');
  });
});
