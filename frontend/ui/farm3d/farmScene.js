/**
 * The 3D farm (three.js): every section is a slab of soil in its real shape, sown with small
 * plants of the crop of the year. The farmer turns the farm by dragging, zooms with the wheel,
 * and touches a section (or its label) to select it: the selected section rises.
 *
 * This module is loaded only when the dashboard shows (see index.js): three.js stays out of the
 * first load of the app. The scene draws a frame only when something moves.
 *
 *   const scene = new FarmScene({ onSelect, reducedMotion });
 *   slot.append(scene.element);
 *   scene.update({ sections, boundary, crops, selectedId });   // as often as the state changes
 *   scene.dispose();
 */
import * as THREE from 'three';
import { translateText } from '../../../data/i18n/index.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { lookOf } from './cropLooks.js';
import { SCENE_SIZE, farmLayout, sowingPoints } from './geometry.js';

/** Thickness of the slab of soil of a section, and how far the selected one rises. */
const SLAB_HEIGHT = 0.6;
const SELECTED_LIFT = 1.1;
const LIFT_MS = 260;
/** Time the plants take to come up when the crop of a section changes. */
const GROW_MS = 520;
const SEEDLING_SCALE = 0.02;
/** Most plants on one section (a big section is sown wider). */
const MAX_PLANTS = 2600;
/** Plants differ a little in size and shade, so that a field does not look printed. */
const SIZE_JITTER = 0.35;
const SHADE_JITTER = 0.16;

const SOIL_SIDE = '#6B4F35';
const PLATE_COLOR = '#D3DCC6';
const GROUND_COLOR = '#D9E3CB';
const SKY_LIGHT = '#FFFFFF';
const GROUND_LIGHT = '#B9C4A6';
const SUN_COLOR = '#FFF3D6';

const CAMERA = {
  fov: 32,
  /** Where the farmer looks from at first: from the south-east, above. */
  azimuth: Math.PI / 4.5,
  polar: Math.PI / 3.4,
  minPolar: Math.PI / 9,
  /** Never so low that the sections hide each other. */
  maxPolar: Math.PI / 2.9,
  /** The farm (SCENE_SIZE wide) seen whole, with a little room around it. */
  fitRadius: SCENE_SIZE * 0.6,
  /** The farm sits a little left of the middle (share of the width): the pie chart of the crops
   *  is in the top right corner of the view. */
  shiftLeft: 0.07,
  zoomIn: 0.55,
  zoomOut: 1.5,
};
const SUN_POSITION = new THREE.Vector3(-SCENE_SIZE * 0.7, SCENE_SIZE * 1.3, SCENE_SIZE * 0.5);
const SHADOW_MAP_SIZE = 2048;
const MAX_PIXEL_RATIO = 2;
/** A pointer that moved less than this between down and up is a touch, not a turn of the farm. */
const CLICK_SLOP_PX = 6;
/** The label of a section floats this far above its plants. */
const LABEL_CLEARANCE = 0.9;

/** The shape of a plant, as a geometry standing on the ground (y from 0 to its height). */
const PLANT_SHAPES = {
  blade: ({ radius, height }) => new THREE.ConeGeometry(radius, height, 4),
  stalk: ({ radius, height }) => new THREE.ConeGeometry(radius, height, 6),
  tuft: ({ radius, height }) => new THREE.ConeGeometry(radius, height, 5),
  bush: ({ radius, height }) =>
    new THREE.IcosahedronGeometry(radius, 1).scale(1, height / (2 * radius), 1),
};
/** Share of the height from which a plant takes the colour of its top (ears, flowers). */
const TIP_FROM = 0.55;

/** A number between 0 and 1 that is always the same for the same `n` (no flicker on redraw). */
function steady(n) {
  const x = Math.sin(n * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
}

/** The geometry of one plant of a look, coloured from its foot to its top. */
function plantGeometry(plant) {
  const geometry = PLANT_SHAPES[plant.shape](plant).translate(0, plant.height / 2, 0);
  const foot = new THREE.Color(plant.color);
  const tip = new THREE.Color(plant.tip);
  const position = geometry.getAttribute('position');
  const colors = new Float32Array(position.count * 3);
  const mixed = new THREE.Color();
  for (let i = 0; i < position.count; i++) {
    const share = THREE.MathUtils.smoothstep(position.getY(i) / plant.height, TIP_FROM, 1);
    mixed
      .copy(foot)
      .lerp(tip, share)
      .toArray(colors, i * 3);
  }
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  return geometry;
}

/** The plants of a section: one instanced mesh, standing on its slab. */
function sowPlants(ring, plant) {
  const points = sowingPoints(ring, {
    spacing: plant.spacing,
    rowGap: plant.rowGap,
    limit: MAX_PLANTS,
  });
  if (!points.length) return null;
  const material = new THREE.MeshLambertMaterial({ vertexColors: true });
  const plants = new THREE.InstancedMesh(plantGeometry(plant), material, points.length);
  const matrix = new THREE.Matrix4();
  const turn = new THREE.Quaternion();
  const up = new THREE.Vector3(0, 1, 0);
  const shade = new THREE.Color();
  points.forEach((point, i) => {
    const size = 1 - SIZE_JITTER / 2 + SIZE_JITTER * steady(i);
    turn.setFromAxisAngle(up, steady(i + 0.5) * Math.PI * 2);
    matrix.compose(
      new THREE.Vector3(point.x, 0, point.y),
      turn,
      new THREE.Vector3(size, size, size),
    );
    plants.setMatrixAt(i, matrix);
    plants.setColorAt(i, shade.setScalar(1 - SHADE_JITTER * steady(i + 0.25)));
  });
  plants.position.y = SLAB_HEIGHT;
  plants.castShadow = true;
  return plants;
}

/** A flat shape of the ground from a ring of ground points (see geometry.js). */
function groundShape(ring) {
  const shape = new THREE.Shape();
  ring.forEach((p, i) => (i ? shape.lineTo(p.x, -p.y) : shape.moveTo(p.x, -p.y)));
  shape.closePath();
  return shape;
}

/** Lays a geometry drawn in the plane of a shape flat on the ground. */
const laidFlat = (geometry) => geometry.rotateX(-Math.PI / 2);

function disposeMesh(mesh) {
  mesh.geometry.dispose();
  for (const material of [mesh.material].flat()) material.dispose();
}

/** One section of the farm: its slab, its plants, its label. */
class SectionModel {
  constructor({ id, ring, centre }) {
    this.id = id;
    this.ring = ring;
    this.centre = centre;
    this.texture = undefined;
    this.plantHeight = 0;
    this.lift = 0;
    this.liftTarget = 0;
    this.growth = 1;
    this.group = new THREE.Group();

    this.topMaterial = new THREE.MeshLambertMaterial();
    const geometry = laidFlat(
      new THREE.ExtrudeGeometry(groundShape(ring), { depth: SLAB_HEIGHT, bevelEnabled: false }),
    );
    // An extruded shape has two groups of faces: its two flat faces, then its sides.
    this.slab = new THREE.Mesh(geometry, [
      this.topMaterial,
      new THREE.MeshLambertMaterial({ color: SOIL_SIDE }),
    ]);
    this.slab.castShadow = true;
    this.slab.receiveShadow = true;
    this.slab.userData.sectionId = id;
    this.group.add(this.slab);
    this.plants = null;

    this.label = document.createElement('button');
    this.label.type = 'button';
    this.label.className = 'farm3d__label';
    this.label.dataset.action = 'select-section';
    this.label.dataset.id = id;
    this.badge = document.createElement('span');
    this.badge.className = 'farm3d__badge';
    this.badge.textContent = id;
    this.cropName = document.createElement('span');
    this.label.append(this.badge, this.cropName);
  }

  /** Sows the crop of the year. Returns true when the crop changed. */
  dress({ texture, name }) {
    this.cropName.textContent = name;
    if (texture === this.texture) return false;
    this.texture = texture;
    const look = lookOf(texture);
    this.topMaterial.color.set(look.ground);
    this.removePlants();
    this.plants = look.plant ? sowPlants(this.ring, look.plant) : null;
    this.plantHeight = look.plant?.height ?? 0;
    if (this.plants) this.group.add(this.plants);
    return true;
  }

  removePlants() {
    if (!this.plants) return;
    this.group.remove(this.plants);
    disposeMesh(this.plants);
    this.plants = null;
  }

  /** Moves the rise and the growth one step on. Returns true while something still moves. */
  step(elapsedMs) {
    const liftStep = (SELECTED_LIFT * elapsedMs) / LIFT_MS;
    const before = this.lift;
    this.lift =
      this.lift < this.liftTarget
        ? Math.min(this.liftTarget, this.lift + liftStep)
        : Math.max(this.liftTarget, this.lift - liftStep);
    this.group.position.y = this.lift;

    const growing = this.growth < 1;
    if (growing) this.growth = Math.min(1, this.growth + elapsedMs / GROW_MS);
    if (this.plants) {
      // Ease out: the plants shoot up, then settle.
      const eased = 1 - (1 - this.growth) ** 3;
      this.plants.scale.y = SEEDLING_SCALE + (1 - SEEDLING_SCALE) * eased;
    }
    return growing || this.lift !== before;
  }

  /** The point its label floats at. */
  labelAnchor(target) {
    return target.set(
      this.centre.x,
      SLAB_HEIGHT + this.lift + this.plantHeight + LABEL_CLEARANCE,
      this.centre.y,
    );
  }

  dispose() {
    this.removePlants();
    disposeMesh(this.slab);
    this.label.remove();
  }
}

export class FarmScene {
  /**
   * onSelect       called with the id of the section the farmer touched in the scene
   * reducedMotion  true: nothing rises or grows, things are simply in place
   */
  constructor({ onSelect, reducedMotion = false }) {
    this.onSelect = onSelect;
    this.reducedMotion = reducedMotion;
    this.models = new Map();
    this.layoutKey = null;
    this.frame = 0;
    this.lastFrameAt = 0;

    this.element = document.createElement('div');
    this.element.className = 'farm3d__host';
    this.labels = document.createElement('div');
    this.labels.className = 'farm3d__labels';

    // Throws when the browser has no WebGL: index.js then keeps the flat view.
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, MAX_PIXEL_RATIO));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFShadowMap;
    this.canvas = this.renderer.domElement;
    this.canvas.setAttribute('role', 'img');
    this.canvas.setAttribute('aria-label', '3D farm view');
    this.element.append(this.canvas, this.labels);

    this.scene = new THREE.Scene();
    this.farm = new THREE.Group();
    this.scene.add(this.farm);
    this.addLights();
    this.addGround();

    this.camera = new THREE.PerspectiveCamera(CAMERA.fov, 1, 0.1, SCENE_SIZE * 20);
    this.controls = new OrbitControls(this.camera, this.canvas);
    this.controls.enablePan = false;
    this.controls.enableDamping = !reducedMotion;
    this.controls.minPolarAngle = CAMERA.minPolar;
    this.controls.maxPolarAngle = CAMERA.maxPolar;
    this.controls.addEventListener('change', () => this.requestFrame());
    this.placeCamera(1);

    this.raycaster = new THREE.Raycaster();
    this.pointer = new THREE.Vector2();
    this.pressedAt = null;
    this.canvas.addEventListener('pointerdown', (e) => {
      this.pressedAt = { x: e.clientX, y: e.clientY };
    });
    this.canvas.addEventListener('pointerup', (e) => this.touch(e));
    this.canvas.addEventListener('pointermove', (e) => {
      this.canvas.style.cursor = this.sectionAt(e) ? 'pointer' : 'grab';
    });

    this.resizes = new ResizeObserver(() => this.resize());
    this.resizes.observe(this.element);
  }

  addLights() {
    this.scene.add(new THREE.HemisphereLight(SKY_LIGHT, GROUND_LIGHT, 1.25));
    const sun = new THREE.DirectionalLight(SUN_COLOR, 2);
    sun.position.copy(SUN_POSITION);
    sun.castShadow = true;
    sun.shadow.mapSize.set(SHADOW_MAP_SIZE, SHADOW_MAP_SIZE);
    const reach = SCENE_SIZE;
    Object.assign(sun.shadow.camera, { left: -reach, right: reach, top: reach, bottom: -reach });
    sun.shadow.camera.far = SCENE_SIZE * 4;
    sun.shadow.bias = -0.0005;
    this.scene.add(sun);
  }

  /** A round piece of land under the farm: it catches the shadows. */
  addGround() {
    const ground = new THREE.Mesh(
      laidFlat(new THREE.CircleGeometry(SCENE_SIZE * 1.05, 64)),
      new THREE.MeshLambertMaterial({ color: GROUND_COLOR }),
    );
    ground.position.y = -0.02;
    ground.receiveShadow = true;
    this.scene.add(ground);
  }

  /** The camera where the farmer looks from at first, far enough to see the whole farm. */
  placeCamera(aspect) {
    const halfFov = THREE.MathUtils.degToRad(CAMERA.fov / 2);
    // A narrow view needs more distance for the same width.
    const distance = CAMERA.fitRadius / Math.sin(halfFov) / Math.min(1, aspect);
    this.camera.position.setFromSphericalCoords(distance, CAMERA.polar, CAMERA.azimuth);
    this.controls.minDistance = distance * CAMERA.zoomIn;
    this.controls.maxDistance = distance * CAMERA.zoomOut;
    this.controls.target.set(0, 0, 0);
    this.controls.update();
  }

  resize() {
    const { clientWidth: width, clientHeight: height } = this.element;
    if (!width || !height) return;
    const firstSize = !this.sized;
    this.sized = true;
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / height;
    this.camera.setViewOffset(width, height, width * CAMERA.shiftLeft, 0, width, height);
    this.camera.updateProjectionMatrix();
    if (firstSize) this.placeCamera(this.camera.aspect);
    this.requestFrame();
  }

  /**
   * What the scene shows now.
   *
   * sections    [{ id, polygon }] of the farm (polygon: [[lat, lon], …] or null)
   * boundary    the outline of the farm, or null
   * crops       id of a section → { texture, name } of what it grows this year
   * selectedId  the section that rises
   */
  update({ sections, boundary, crops, selectedId }) {
    this.canvas.setAttribute('aria-label', translateText('Vue 3D de la ferme'));
    const layoutKey = JSON.stringify([boundary, sections.map((s) => [s.id, s.polygon])]);
    const rebuilt = layoutKey !== this.layoutKey;
    if (rebuilt) {
      this.layoutKey = layoutKey;
      this.build(farmLayout(sections, boundary));
    }
    for (const model of this.models.values()) {
      const changed = model.dress(crops[model.id]);
      // The plants come up when the year changes, not when the farm is first shown.
      if (changed && !rebuilt && !this.reducedMotion) model.growth = 0;
      const selected = model.id === selectedId;
      model.liftTarget = selected ? SELECTED_LIFT : 0;
      model.label.classList.toggle('is-selected', selected);
      if (rebuilt || this.reducedMotion) model.lift = model.liftTarget;
    }
    this.requestFrame();
  }

  build({ plate, sections }) {
    this.clearFarm();
    if (plate) {
      this.plate = new THREE.Mesh(
        laidFlat(new THREE.ShapeGeometry(groundShape(plate))),
        new THREE.MeshLambertMaterial({ color: PLATE_COLOR }),
      );
      this.plate.receiveShadow = true;
      this.farm.add(this.plate);
    }
    for (const section of sections) {
      const model = new SectionModel(section);
      this.models.set(section.id, model);
      this.farm.add(model.group);
      this.labels.append(model.label);
    }
  }

  clearFarm() {
    for (const model of this.models.values()) {
      this.farm.remove(model.group);
      model.dispose();
    }
    this.models.clear();
    if (this.plate) {
      this.farm.remove(this.plate);
      disposeMesh(this.plate);
      this.plate = null;
    }
  }

  /** The id of the section under the pointer, or null. */
  sectionAt(event) {
    const box = this.canvas.getBoundingClientRect();
    this.pointer.set(
      ((event.clientX - box.left) / box.width) * 2 - 1,
      -((event.clientY - box.top) / box.height) * 2 + 1,
    );
    this.raycaster.setFromCamera(this.pointer, this.camera);
    const slabs = [...this.models.values()].map((model) => model.slab);
    return this.raycaster.intersectObjects(slabs)[0]?.object.userData.sectionId ?? null;
  }

  touch(event) {
    const pressed = this.pressedAt;
    this.pressedAt = null;
    if (!pressed) return;
    const moved = Math.hypot(event.clientX - pressed.x, event.clientY - pressed.y);
    const id = moved < CLICK_SLOP_PX ? this.sectionAt(event) : null;
    if (id) this.onSelect(id);
  }

  requestFrame() {
    if (!this.frame) this.frame = requestAnimationFrame((now) => this.draw(now));
  }

  draw(now) {
    this.frame = 0;
    const elapsed = this.lastFrameAt ? Math.min(now - this.lastFrameAt, 64) : 16;
    this.lastFrameAt = now;
    const turning = this.controls.update();
    let moving = false;
    for (const model of this.models.values()) moving = model.step(elapsed) || moving;
    this.renderer.render(this.scene, this.camera);
    this.placeLabels();
    if (turning || moving) this.requestFrame();
    else this.lastFrameAt = 0;
  }

  /** Puts every label over its section, where the camera sees it. */
  placeLabels() {
    const { clientWidth: width, clientHeight: height } = this.element;
    const anchor = new THREE.Vector3();
    for (const model of this.models.values()) {
      model.labelAnchor(anchor).project(this.camera);
      const x = (anchor.x * 0.5 + 0.5) * width;
      const y = (-anchor.y * 0.5 + 0.5) * height;
      model.label.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px) translate(-50%, -50%)`;
    }
  }

  dispose() {
    cancelAnimationFrame(this.frame);
    this.resizes.disconnect();
    this.controls.dispose();
    this.clearFarm();
    this.renderer.dispose();
    this.element.remove();
  }
}
