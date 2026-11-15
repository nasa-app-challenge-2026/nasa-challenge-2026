/**
 * How each crop looks in the 3D farm: the colour of its ground and the small plants sown on it.
 * One look per field texture of data/reference/crops.js (`texture`), so that the 3D farm, the
 * field strips and the wheels speak of the same crops.
 *
 * A plant: `shape` (see PLANT_SHAPES in farmScene.js), its `height` and `radius` in scene units,
 * its colour at the foot (`color`) and at the top (`tip`), and how densely it is sown.
 */

/** Bare soil: fallow, and the ground between the rows. */
const SOIL = '#8A6845';
const GREEN_GROUND = '#5C7F3F';

const cereal = (color, tip, ground) => ({
  ground,
  plant: { shape: 'blade', height: 0.42, radius: 0.05, color, tip, spacing: 0.2, rowGap: 0.26 },
});

export const CROP_LOOKS = {
  mais: {
    ground: '#6B5236',
    plant: {
      shape: 'stalk',
      height: 0.95,
      radius: 0.1,
      color: '#3F7A33',
      tip: '#E9D27A',
      spacing: 0.36,
      rowGap: 0.5,
    },
  },
  soya: {
    ground: '#6B4E31',
    plant: {
      shape: 'bush',
      height: 0.3,
      radius: 0.17,
      color: '#6FA044',
      tip: '#93C25F',
      spacing: 0.36,
      rowGap: 0.46,
    },
  },
  ble: cereal('#B98F3A', '#EDCF7E', '#A9802D'),
  orge: cereal('#BFA45C', '#EFE2B0', '#B79C5A'),
  seigle: cereal('#6F8F45', '#D8CD94', '#6C8748'),
  canola: {
    ground: GREEN_GROUND,
    plant: {
      shape: 'bush',
      height: 0.42,
      radius: 0.15,
      color: '#5C8A3A',
      tip: '#F2DC4B',
      spacing: 0.3,
      rowGap: 0.34,
    },
  },
  sarrasin: {
    ground: '#62803F',
    plant: {
      shape: 'bush',
      height: 0.36,
      radius: 0.14,
      color: '#6E8F45',
      tip: '#F4E6EC',
      spacing: 0.3,
      rowGap: 0.34,
    },
  },
  luzerne: {
    ground: '#3F7A45',
    plant: {
      shape: 'tuft',
      height: 0.3,
      radius: 0.12,
      color: '#3F7A45',
      tip: '#8FBF7A',
      spacing: 0.24,
      rowGap: 0.26,
    },
  },
  foin: {
    ground: '#6E9350',
    plant: {
      shape: 'tuft',
      height: 0.34,
      radius: 0.1,
      color: '#7EA35A',
      tip: '#C9DDA0',
      spacing: 0.22,
      rowGap: 0.24,
    },
  },
  patate: {
    ground: '#7A5634',
    plant: {
      shape: 'bush',
      height: 0.26,
      radius: 0.2,
      color: '#5F8A3B',
      tip: '#7DA850',
      spacing: 0.42,
      rowGap: 0.56,
    },
  },
  legume: {
    ground: '#6F5233',
    plant: {
      shape: 'bush',
      height: 0.24,
      radius: 0.16,
      color: '#7DB35A',
      tip: '#9CCB74',
      spacing: 0.4,
      rowGap: 0.5,
    },
  },
  sol: { ground: SOIL, plant: null },
};

/** The look of a field texture; bare soil when nothing grows or the texture is unknown. */
export const lookOf = (texture) => CROP_LOOKS[texture] ?? CROP_LOOKS.sol;
