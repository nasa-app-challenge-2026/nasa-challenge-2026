/**
 * The dashboard: the order of the section cards, the pie chart of the crops of the year, and the
 * geometry of the 3D farm (where the sections stand, where their plants are sown).
 */
import { beforeEach, describe, expect, it } from 'vitest';
import { setLanguage } from '../data/i18n/index.js';
beforeEach(() => setLanguage('fr'));
import {
  dashboardOrder,
  defaultOrder,
  isDefaultOrder,
  moveBlock,
} from '../frontend/lib/dashboard.js';
import { pieChart, pieShares } from '../frontend/ui/pieChart.js';
import { CROP_LOOKS, lookOf } from '../frontend/ui/farm3d/cropLooks.js';
import {
  SCENE_SIZE,
  farmLayout,
  insideRing,
  rowDirection,
  sowingPoints,
} from '../frontend/ui/farm3d/geometry.js';
import { CROPS } from '../data/reference/crops.js';
import { DEMO_FARM } from '../data/reference/demoFarm.js';

describe('order of the section cards', () => {
  it('follows the farm by default', () => {
    expect(defaultOrder(['A', 'B', 'C'])).toEqual(['sec:A', 'sec:B', 'sec:C']);
  });

  it('keeps the saved order, drops what is gone and puts new sections last', () => {
    // 'weather', 'farm3d' and 'mix' were blocks of an older version: they have a fixed place now.
    const saved = ['mix', 'sec:B', 'weather', 'sec:A', 'sec:Z', 'farm3d', 'sec:B'];
    expect(dashboardOrder(saved, ['A', 'B', 'C'])).toEqual(['sec:B', 'sec:A', 'sec:C']);
    expect(dashboardOrder(null, ['A'])).toEqual(['sec:A']);
  });

  it('moves a card with the keyboard and knows the default', () => {
    const order = defaultOrder(['A', 'B', 'C']);
    expect(moveBlock(order, 'sec:A', 1)).toEqual(['sec:B', 'sec:A', 'sec:C']);
    expect(moveBlock(order, 'sec:A', -1)).toBe(order);
    expect(isDefaultOrder(order, ['A', 'B', 'C'])).toBe(true);
    expect(isDefaultOrder(moveBlock(order, 'sec:C', -1), ['A', 'B', 'C'])).toBe(false);
  });
});

describe('pie chart of the crops of the year', () => {
  const slices = [
    { label: 'Blé 22 ha', value: 22, color: '#DDB07F' },
    { label: 'Luzerne 8 ha', value: 8, color: '#7FC0B2' },
    { label: 'Rien', value: 0, color: '#000000' },
    { label: 'Soya 6 ha', value: 6, color: '#9CC27A' },
  ];

  it('gives each crop its share of the turn, in order, and leaves empty slices out', () => {
    const shares = pieShares(slices);
    expect(shares.map((s) => s.label)).toEqual(['Blé 22 ha', 'Luzerne 8 ha', 'Soya 6 ha']);
    expect(shares[0].from).toBe(0);
    expect(shares[0].to).toBeCloseTo(22 / 36);
    expect(shares[2].to).toBeCloseTo(1);
  });

  it('draws one slice per crop, and a full disc for a single crop', () => {
    const pie = String(pieChart(slices, { label: 'Cultures en 2027' }));
    expect(pie.match(/class="pie__slice"/g)).toHaveLength(3);
    expect(pie).toContain('aria-label="Cultures en 2027 : Blé 22 ha, Luzerne 8 ha, Soya 6 ha"');
    const single = String(pieChart(slices.slice(0, 1), { label: 'Cultures en 2027' }));
    expect(single).toContain('<circle');
    expect(single).not.toContain('pie__slice');
  });
});

describe('geometry of the 3D farm', () => {
  const square = [
    { x: 0, y: 0 },
    { x: 4, y: 0 },
    { x: 4, y: 2 },
    { x: 0, y: 2 },
  ];

  it('places the drawn sections in their real shape, inside the scene', () => {
    const { plate, sections } = farmLayout(DEMO_FARM.sections, DEMO_FARM.farm.boundary);
    expect(sections.map((s) => s.id)).toEqual(DEMO_FARM.sections.map((s) => s.id));
    const half = SCENE_SIZE / 2 + 1e-6;
    for (const point of [...plate, ...sections.flatMap((s) => s.ring)]) {
      expect(Math.abs(point.x)).toBeLessThanOrEqual(half);
      expect(Math.abs(point.y)).toBeLessThanOrEqual(half);
    }
    for (const section of sections) expect(insideRing(section.centre, section.ring)).toBe(true);
  });

  it('gives a section that is not drawn a square of its own', () => {
    const farm = [...DEMO_FARM.sections, { id: 'Z', polygon: null }];
    const { sections } = farmLayout(farm, DEMO_FARM.farm.boundary);
    const z = sections.at(-1);
    expect(z.ring).toHaveLength(4);
    expect(z.centre.y).toBeGreaterThan(SCENE_SIZE / 2); // in front of the farm
    const alone = farmLayout([{ id: 'A', polygon: null }]);
    expect(alone.plate).toBeNull();
    expect(alone.sections[0].centre).toEqual({ x: 0, y: 0 });
  });

  it('sows the plants in rows along the longest edge, inside the section', () => {
    expect(rowDirection(square)).toBeCloseTo(0);
    const points = sowingPoints(square, { spacing: 0.5, rowGap: 0.5, limit: 1000 });
    expect(points.length).toBeGreaterThan(10);
    for (const point of points) expect(insideRing(point, square)).toBe(true);
    const rows = new Set(points.map((p) => p.y.toFixed(3)));
    expect(rows.size).toBeLessThan(points.length / 2); // several plants share a row
  });

  it('sows a big section wider instead of going over the limit', () => {
    const dense = sowingPoints(square, { spacing: 0.05, rowGap: 0.05, limit: 200 });
    expect(dense.length).toBeLessThanOrEqual(200);
    expect(dense.length).toBeGreaterThan(100);
  });

  it('knows the look of every field texture of the crops', () => {
    for (const crop of Object.values(CROPS)) expect(CROP_LOOKS[crop.texture]).toBeDefined();
    expect(lookOf('sol').plant).toBeNull();
    expect(lookOf(undefined)).toBe(CROP_LOOKS.sol);
  });
});
