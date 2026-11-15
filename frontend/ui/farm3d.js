/**
 * Real Three.js 3D isometric-style farm component.
 *
 * Replaces the 2D SVG isometric farm with an interactive 3D model:
 *   - Sections extruded into raised prisms, colored by crop.
 *   - Ground plane from closed boundary or bounding rectangle.
 *   - HTML badges for section ID and crop name via CSS2DRenderer.
 *   - Soft shadows, warm sunlight, gentle orbiting controls.
 *   - Floating ambient dust motes / pollen particles for life.
 *   - Selected section elevated with a glowing outline.
 */
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { CSS2DObject, CSS2DRenderer } from 'three/addons/renderers/CSS2DRenderer.js';
import { isClosed } from '../../application/rules/geo.js';
import { colorOf, nameOf } from '../../data/reference/crops.js';

const PRISM_HEIGHT = 0.8;
const LIFT_HEIGHT = 1.3;
const TARGET_SCENE_SIZE = 22;

/**
 * Injects CSS rules for the 2D HTML labels over 3D sections.
 */
function ensureLabelStyles() {
  if (typeof document === 'undefined') return;
  if (document.getElementById('farm3d-styles')) return;

  const style = document.createElement('style');
  style.id = 'farm3d-styles';
  style.textContent = `
    .farm3d-css2d-container {
      pointer-events: none;
      user-select: none;
    }
    .farm3d-label {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px 4px 6px;
      background: rgba(255, 255, 255, 0.94);
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
      border: 1.5px solid rgba(0, 0, 0, 0.1);
      border-radius: 999px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12), 0 1px 3px rgba(0, 0, 0, 0.08);
      pointer-events: auto;
      cursor: pointer;
      user-select: none;
      font-family: var(--font-body, system-ui, -apple-system, sans-serif);
      font-size: 13px;
      line-height: 1;
      transform: translate(-50%, -50%);
      transition: transform 0.2s cubic-bezier(0.2, 0.8, 0.3, 1), box-shadow 0.2s ease, border-color 0.2s ease;
      white-space: nowrap;
    }
    .farm3d-label:hover {
      transform: translate(-50%, -54%) scale(1.06);
      box-shadow: 0 6px 18px rgba(0, 0, 0, 0.22);
      border-color: rgba(0, 0, 0, 0.25);
    }
    .farm3d-label.is-selected {
      background: #ffffff;
      border: 2px solid #18211b;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.26);
      transform: translate(-50%, -52%) scale(1.08);
    }
    .farm3d-label__badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 20px;
      height: 20px;
      border-radius: 50%;
      background: #18211b;
      color: #ffffff;
      font-weight: 700;
      font-size: 11px;
    }
    .farm3d-label.is-selected .farm3d-label__badge {
      background: #0072b2;
    }
    .farm3d-label__crop {
      font-weight: 600;
      color: #1e293b;
      letter-spacing: -0.01em;
    }
  `;
  document.head.appendChild(style);
}

/** Check if two [coord0, coord1] points are identical within small epsilon. */
function isSameCoord(a, b) {
  if (!a || !b || a.length < 2 || b.length < 2) return false;
  return Math.abs(a[0] - b[0]) < 1e-6 && Math.abs(a[1] - b[1]) < 1e-6;
}

/**
 * A boundary is considered a closed polygon if it has >= 4 points and first == last point.
 */
function isClosedPolygon(poly) {
  if (!Array.isArray(poly) || poly.length < 4) return false;
  return isSameCoord(poly[0], poly[poly.length - 1]);
}

/**
 * Normalizes a point into [lon, lat], whether input is [lat, lon] or [lon, lat].
 */
function toLonLat(p) {
  if (!p || p.length < 2) return [0, 0];
  const [a, b] = p;
  // If |a| > 90, a is longitude
  if (Math.abs(a) > 90) return [a, b];
  // If |b| > 90, b is longitude
  if (Math.abs(b) > 90) return [b, a];
  // Western hemisphere: lon < 0 and lat > 0
  if (a < 0 && b > 0) return [a, b];
  if (a > 0 && b < 0) return [b, a];
  // Synthetic coordinates [x, y]
  return [a, b];
}

/**
 * Builds projection mapping geographic [lon, lat] points to local 3D X/Z coordinates.
 */
function createProjector(allPolygons, targetSize = TARGET_SCENE_SIZE) {
  const allPts = allPolygons
    .flat()
    .filter((p) => Array.isArray(p) && p.length >= 2)
    .map(toLonLat);

  if (!allPts.length) {
    return {
      project: ([x = 0, y = 0]) => ({ x, z: y }),
      bounds: { minX: -5, maxX: 5, minZ: -5, maxZ: 5 },
    };
  }

  const meanLat = allPts.reduce((acc, p) => acc + p[1], 0) / allPts.length;
  // Cosine factor for longitude east-west meters per degree
  const kx =
    Math.abs(meanLat) > 0.1 && Math.abs(meanLat) <= 89
      ? Math.cos((meanLat * Math.PI) / 180)
      : 1;

  const eastNorthPts = allPts.map(([lon, lat]) => ({
    east: lon * kx,
    north: lat,
  }));

  const easts = eastNorthPts.map((p) => p.east);
  const norths = eastNorthPts.map((p) => p.north);

  const minEast = Math.min(...easts);
  const maxEast = Math.max(...easts);
  const minNorth = Math.min(...norths);
  const maxNorth = Math.max(...norths);

  const cEast = (minEast + maxEast) / 2;
  const cNorth = (minNorth + maxNorth) / 2;

  const spanEast = maxEast - minEast || 1e-4;
  const spanNorth = maxNorth - minNorth || 1e-4;
  const maxSpan = Math.max(spanEast, spanNorth) || 1;

  const scale = targetSize / maxSpan;

  function project(rawPoint) {
    const [lon, lat] = toLonLat(rawPoint);
    const east = lon * kx;
    const north = lat;
    const x = (east - cEast) * scale;
    // North is mapped to -Z in 3D camera convention
    const z = -(north - cNorth) * scale;
    return { x, z };
  }

  const projectedCorners = [
    project([Math.min(...allPts.map((p) => p[0])), Math.min(...allPts.map((p) => p[1]))]),
    project([Math.max(...allPts.map((p) => p[0])), Math.max(...allPts.map((p) => p[1]))]),
  ];

  const bounds = {
    minX: Math.min(...projectedCorners.map((p) => p.x)),
    maxX: Math.max(...projectedCorners.map((p) => p.x)),
    minZ: Math.min(...projectedCorners.map((p) => p.z)),
    maxZ: Math.max(...projectedCorners.map((p) => p.z)),
  };

  return { project, bounds };
}

/**
 * Computes polygon centroid in projected {x, z} coordinates.
 */
function computePolygonCentroid(pts) {
  const n = pts.length;
  if (n < 3) {
    const d = n || 1;
    return {
      x: pts.reduce((sum, p) => sum + p.x, 0) / d,
      z: pts.reduce((sum, p) => sum + p.z, 0) / d,
    };
  }

  let area = 0;
  let cx = 0;
  let cz = 0;

  for (let i = 0; i < n; i++) {
    const p1 = pts[i];
    const p2 = pts[(i + 1) % n];
    const cross = p1.x * p2.z - p2.x * p1.z;
    area += cross;
    cx += (p1.x + p2.x) * cross;
    cz += (p1.z + p2.z) * cross;
  }

  area *= 0.5;
  if (Math.abs(area) < 1e-8) {
    return {
      x: pts.reduce((sum, p) => sum + p.x, 0) / n,
      z: pts.reduce((sum, p) => sum + p.z, 0) / n,
    };
  }

  return {
    x: cx / (6 * area),
    z: cz / (6 * area),
  };
}

/**
 * Creates a soft radial glow texture for dust motes.
 */
function createDustTexture() {
  if (typeof document === 'undefined') return null;
  const canvas = document.createElement('canvas');
  canvas.width = 32;
  canvas.height = 32;
  const ctx = canvas.getContext('2d');
  const gradient = ctx.createRadialGradient(16, 16, 0, 16, 16, 16);
  gradient.addColorStop(0, 'rgba(255, 255, 240, 0.95)');
  gradient.addColorStop(0.3, 'rgba(255, 245, 210, 0.55)');
  gradient.addColorStop(1, 'rgba(255, 235, 180, 0)');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, 32, 32);

  const texture = new THREE.CanvasTexture(canvas);
  return texture;
}

/**
 * Mounts a real Three.js 3D farm into container element.
 *
 * @param {HTMLElement} container
 * @param {Object} options
 * @param {Array} options.sections
 * @param {Function} options.cropOf
 * @param {string} options.selectedId
 * @param {Array|null} options.boundary
 * @returns {{ dispose: Function, update: Function }}
 */
export function mount3dFarm(container, { sections = [], cropOf = () => null, selectedId = null, boundary = null } = {}) {
  ensureLabelStyles();

  // Container styling
  if (container) {
    container.style.position = container.style.position || 'relative';
    container.style.overflow = 'hidden';
  }

  const initialWidth = container?.clientWidth || 600;
  const initialHeight = container?.clientHeight || 420;

  // 1. Scene setup
  const scene = new THREE.Scene();
  scene.background = null; // transparent background so UI gradient shows through

  // 2. Camera setup: Isometric-ish perspective angle (~40° elevation, ~30° azimuth)
  const camera = new THREE.PerspectiveCamera(34, initialWidth / initialHeight, 0.1, 500);
  const camDistance = 34;
  const elevationRad = (40 * Math.PI) / 180;
  const azimuthRad = (30 * Math.PI) / 180;

  const rXZ = camDistance * Math.cos(elevationRad);
  const camY = camDistance * Math.sin(elevationRad);
  const camX = rXZ * Math.sin(azimuthRad);
  const camZ = rXZ * Math.cos(azimuthRad);

  camera.position.set(camX, camY, camZ);
  camera.lookAt(0, 0, 0);

  // 3. WebGL Renderer
  const renderer = new THREE.WebGLRenderer({
    antialias: true,
    alpha: true,
    powerPreference: 'high-performance',
  });
  renderer.setSize(initialWidth, initialHeight);
  renderer.setPixelRatio(Math.min(window?.devicePixelRatio || 1, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.08;
  renderer.domElement.style.display = 'block';
  renderer.domElement.style.width = '100%';
  renderer.domElement.style.height = '100%';
  container.appendChild(renderer.domElement);

  // 4. CSS2D Renderer for HTML section labels
  const labelRenderer = new CSS2DRenderer();
  labelRenderer.setSize(initialWidth, initialHeight);
  labelRenderer.domElement.className = 'farm3d-css2d-container';
  labelRenderer.domElement.style.position = 'absolute';
  labelRenderer.domElement.style.top = '0px';
  labelRenderer.domElement.style.left = '0px';
  labelRenderer.domElement.style.width = '100%';
  labelRenderer.domElement.style.height = '100%';
  labelRenderer.domElement.style.pointerEvents = 'none';
  container.appendChild(labelRenderer.domElement);

  // 5. OrbitControls
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.autoRotate = true;
  controls.autoRotateSpeed = 0.55;
  controls.maxPolarAngle = Math.PI / 2 - 0.08; // Stay above ground plane
  controls.minDistance = 10;
  controls.maxDistance = 70;
  controls.target.set(0, 0, 0);

  // 6. Lighting setup (Ambient + Directional with soft shadows)
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.75);
  scene.add(ambientLight);

  const hemiLight = new THREE.HemisphereLight(0xf2f7ff, 0x54402b, 0.45);
  scene.add(hemiLight);

  const dirLight = new THREE.DirectionalLight(0xfff7ea, 1.45);
  dirLight.position.set(18, 28, 16);
  dirLight.castShadow = true;
  dirLight.shadow.mapSize.width = 2048;
  dirLight.shadow.mapSize.height = 2048;
  dirLight.shadow.camera.near = 0.5;
  dirLight.shadow.camera.far = 80;
  dirLight.shadow.camera.left = -16;
  dirLight.shadow.camera.right = 16;
  dirLight.shadow.camera.top = 16;
  dirLight.shadow.camera.bottom = -16;
  dirLight.shadow.bias = -0.0004;
  dirLight.shadow.radius = 2.4;
  scene.add(dirLight);

  // Secondary soft fill light from opposite quadrant
  const fillLight = new THREE.DirectionalLight(0xdbeafe, 0.35);
  fillLight.position.set(-15, 14, -14);
  scene.add(fillLight);

  // 7. Atmosphere: Floating dust motes / pollen particles
  const particleCount = 140;
  const particleGeo = new THREE.BufferGeometry();
  const particlePositions = new Float32Array(particleCount * 3);
  const particleSeeds = new Float32Array(particleCount);

  for (let i = 0; i < particleCount; i++) {
    particlePositions[i * 3 + 0] = (Math.random() - 0.5) * 26;
    particlePositions[i * 3 + 1] = 0.3 + Math.random() * 7.0;
    particlePositions[i * 3 + 2] = (Math.random() - 0.5) * 26;
    particleSeeds[i] = Math.random() * 100;
  }

  particleGeo.setAttribute('position', new THREE.BufferAttribute(particlePositions, 3));

  const dustTexture = createDustTexture();
  const particleMat = new THREE.PointsMaterial({
    color: 0xfffae8,
    size: 0.38,
    map: dustTexture,
    transparent: true,
    opacity: 0.65,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });

  const particleSystem = new THREE.Points(particleGeo, particleMat);
  scene.add(particleSystem);

  // State holders
  let currentSections = sections;
  let currentCropOf = cropOf;
  let currentSelectedId = selectedId;
  let currentBoundary = boundary;

  let farmGroup = new THREE.Group();
  scene.add(farmGroup);

  const sectionMeshes = new Map();
  const sectionGlows = new Map();
  const clickableObjects = [];

  /**
   * Helper to recursively dispose geometries, materials, and textures in a group.
   */
  function disposeGroup(group) {
    while (group.children.length > 0) {
      const child = group.children[0];
      group.remove(child);

      child.traverse((node) => {
        if (node.geometry) {
          node.geometry.dispose();
        }
        if (node.material) {
          if (Array.isArray(node.material)) {
            node.material.forEach((mat) => {
              if (mat.map) mat.map.dispose();
              mat.dispose();
            });
          } else {
            if (node.material.map) node.material.map.dispose();
            node.material.dispose();
          }
        }
      });
    }
  }

  /**
   * Builds the 3D ground plane and extruded section prisms.
   */
  function buildFarm() {
    disposeGroup(farmGroup);
    sectionMeshes.clear();
    sectionGlows.clear();
    clickableObjects.length = 0;

    const drawnSections = (currentSections || []).filter((s) => isClosed(s.polygon));
    const missingSections = (currentSections || []).filter((s) => !isClosed(s.polygon));

    // Determine if boundary is provided as a closed polygon (first == last point)
    const hasClosedBoundary = isClosedPolygon(currentBoundary);

    // Collect all polygons for coordinate projection
    const polysToProject = [];
    if (hasClosedBoundary) {
      polysToProject.push(currentBoundary.slice(0, -1));
    }
    drawnSections.forEach((s) => polysToProject.push(s.polygon));

    // Fallback if no polygons have been traced yet
    const useGridFallback = drawnSections.length === 0 && !hasClosedBoundary;

    let projector;
    if (useGridFallback) {
      projector = createProjector([
        [
          [0, 0],
          [10, 0],
          [10, 10],
          [0, 10],
        ],
      ]);
    } else {
      projector = createProjector(polysToProject);
    }

    // --- Ground Plane ---
    let groundMesh;
    const groundMaterial = new THREE.MeshStandardMaterial({
      color: new THREE.Color('#7ba06d'),
      roughness: 0.88,
      metalness: 0.04,
      side: THREE.DoubleSide,
    });

    if (hasClosedBoundary) {
      // Use boundary's shape
      const boundaryPts = currentBoundary.slice(0, -1).map(projector.project);
      const shape = new THREE.Shape();
      const pts2d = boundaryPts.map((p) => new THREE.Vector2(p.x, -p.z));
      if (THREE.ShapeUtils.isClockwise(pts2d)) pts2d.reverse();

      shape.moveTo(pts2d[0].x, pts2d[0].y);
      for (let i = 1; i < pts2d.length; i++) {
        shape.lineTo(pts2d[i].x, pts2d[i].y);
      }
      shape.closePath();

      const groundGeo = new THREE.ShapeGeometry(shape);
      groundMesh = new THREE.Mesh(groundGeo, groundMaterial);
      groundMesh.rotation.x = -Math.PI / 2;
      groundMesh.position.y = -0.01;

      // Add boundary outline line
      const linePts = boundaryPts.map((p) => new THREE.Vector3(p.x, 0.01, p.z));
      const lineGeo = new THREE.BufferGeometry().setFromPoints(linePts);
      const lineMat = new THREE.LineBasicMaterial({
        color: 0xffd27a,
        transparent: true,
        opacity: 0.7,
      });
      const borderLine = new THREE.LineLoop(lineGeo, lineMat);
      groundMesh.add(borderLine);
    } else {
      // Use rectangle that fits all sections
      const pad = 1.2;
      const b = projector.bounds;
      const width = Math.max(b.maxX - b.minX + pad * 2, 8);
      const depth = Math.max(b.maxZ - b.minZ + pad * 2, 8);
      const cx = (b.minX + b.maxX) / 2;
      const cz = (b.minZ + b.maxZ) / 2;

      const groundGeo = new THREE.PlaneGeometry(width, depth);
      groundMesh = new THREE.Mesh(groundGeo, groundMaterial);
      groundMesh.rotation.x = -Math.PI / 2;
      groundMesh.position.set(cx, -0.01, cz);

      // Subtle dashed-style border line
      const hw = width / 2;
      const hd = depth / 2;
      const rectCorners = [
        new THREE.Vector3(-hw, 0.01, -hd),
        new THREE.Vector3(hw, 0.01, -hd),
        new THREE.Vector3(hw, 0.01, hd),
        new THREE.Vector3(-hw, 0.01, hd),
      ];
      const rectGeo = new THREE.BufferGeometry().setFromPoints(rectCorners);
      const rectLineMat = new THREE.LineBasicMaterial({
        color: 0xffd27a,
        transparent: true,
        opacity: 0.65,
      });
      const borderLine = new THREE.LineLoop(rectGeo, rectLineMat);
      groundMesh.add(borderLine);
    }

    groundMesh.receiveShadow = true;
    farmGroup.add(groundMesh);

    // --- Sections ---
    if (useGridFallback) {
      // Grid farm fallback when no polygons are drawn yet
      buildGridSections(currentSections);
    } else {
      // Traced sections as extruded prisms
      drawnSections.forEach((s) => {
        buildExtrudedSection(s, projector);
      });

      // Display missing (untraced) sections in front of farm
      if (missingSections.length > 0) {
        buildMissingSections(missingSections, projector.bounds);
      }
    }
  }

  /**
   * Builds an extruded prism for a traced section.
   */
  function buildExtrudedSection(s, projector) {
    const projectedPts = s.polygon.map(projector.project);
    if (projectedPts.length < 3) return;

    // Convert to 2D shape points for Three.js extrusion
    const pts2d = projectedPts.map((p) => new THREE.Vector2(p.x, -p.z));
    if (THREE.ShapeUtils.isClockwise(pts2d)) pts2d.reverse();

    const shape = new THREE.Shape();
    shape.moveTo(pts2d[0].x, pts2d[0].y);
    for (let i = 1; i < pts2d.length; i++) {
      shape.lineTo(pts2d[i].x, pts2d[i].y);
    }
    shape.closePath();

    const extrudeSettings = {
      depth: PRISM_HEIGHT,
      bevelEnabled: false,
    };

    const geometry = new THREE.ExtrudeGeometry(shape, extrudeSettings);

    const cropId = currentCropOf ? currentCropOf(s.id) : null;
    const cropColorHex = colorOf(cropId);
    const isSelected = s.id === currentSelectedId;

    // Materials: Caps (top/bottom) get crop color, sides get darker brown
    const topMaterial = new THREE.MeshStandardMaterial({
      color: new THREE.Color(cropColorHex),
      roughness: 0.65,
      metalness: 0.06,
      emissive: isSelected ? new THREE.Color('#FFD27A') : new THREE.Color(0x000000),
      emissiveIntensity: isSelected ? 0.22 : 0,
    });

    const sideMaterial = new THREE.MeshStandardMaterial({
      color: new THREE.Color('#54402B'),
      roughness: 0.86,
      metalness: 0.04,
    });

    const sectionMesh = new THREE.Mesh(geometry, [topMaterial, sideMaterial]);
    sectionMesh.userData = { sectionId: s.id };
    sectionMesh.rotation.x = -Math.PI / 2;
    sectionMesh.castShadow = true;
    sectionMesh.receiveShadow = true;

    // Section root group (allows animated lift on Y)
    const sectionGroup = new THREE.Group();
    sectionGroup.userData = {
      sectionId: s.id,
      targetY: isSelected ? LIFT_HEIGHT : 0,
    };
    sectionGroup.position.y = isSelected ? LIFT_HEIGHT : 0;
    sectionGroup.add(sectionMesh);

    // Glow outline for selected section
    const edgesGeo = new THREE.EdgesGeometry(geometry, 28);
    const glowLineMat = new THREE.LineBasicMaterial({
      color: 0xffd27a,
      linewidth: 2,
      transparent: true,
      opacity: isSelected ? 0.95 : 0,
    });
    const edgeLines = new THREE.LineSegments(edgesGeo, glowLineMat);
    edgeLines.rotation.x = -Math.PI / 2;
    sectionGroup.add(edgeLines);

    // Subtle dark footprint under lifted section
    const footprintGeo = new THREE.ShapeGeometry(shape);
    const footprintMat = new THREE.MeshBasicMaterial({
      color: 0x3e2e1f,
      transparent: true,
      opacity: isSelected ? 0.45 : 0,
      depthWrite: false,
    });
    const footprintMesh = new THREE.Mesh(footprintGeo, footprintMat);
    footprintMesh.rotation.x = -Math.PI / 2;
    footprintMesh.position.y = 0.005;
    farmGroup.add(footprintMesh);

    // HTML Section Label via CSS2DRenderer
    const centroid = computePolygonCentroid(projectedPts);
    const labelDiv = document.createElement('div');
    labelDiv.className = `farm3d-label ${isSelected ? 'is-selected' : ''}`;
    labelDiv.dataset.action = 'select-section';
    labelDiv.dataset.id = s.id;
    labelDiv.innerHTML = `
      <span class="farm3d-label__badge">${s.id}</span>
      <span class="farm3d-label__crop">${cropId ? nameOf(cropId) : '—'}</span>
    `;

    labelDiv.addEventListener('click', () => {
      selectSection(s.id, true);
    });

    const labelObj = new CSS2DObject(labelDiv);
    labelObj.position.set(centroid.x, PRISM_HEIGHT + 0.35, centroid.z);
    sectionGroup.add(labelObj);

    sectionMeshes.set(s.id, {
      group: sectionGroup,
      topMat: topMaterial,
      footprint: footprintMesh,
      footprintMat,
      labelDiv,
      edgeLines,
    });

    sectionGlows.set(s.id, glowLineMat);
    clickableObjects.push(sectionMesh);
    farmGroup.add(sectionGroup);
  }

  /**
   * Places missing (untraced) sections in a row in front of the farm model.
   */
  function buildMissingSections(missing, bounds) {
    const size = 1.8;
    const gap = 0.6;
    const totalWidth = missing.length * size + (missing.length - 1) * gap;
    const startX = -totalWidth / 2 + size / 2;
    const rowZ = bounds.maxZ + 2.4;

    missing.forEach((s, i) => {
      const cx = startX + i * (size + gap);
      const cz = rowZ;

      const pts = [
        new THREE.Vector2(-size / 2, -size / 2),
        new THREE.Vector2(size / 2, -size / 2),
        new THREE.Vector2(size / 2, size / 2),
        new THREE.Vector2(-size / 2, size / 2),
      ];

      const shape = new THREE.Shape();
      shape.moveTo(pts[0].x, pts[0].y);
      for (let j = 1; j < pts.length; j++) shape.lineTo(pts[j].x, pts[j].y);
      shape.closePath();

      const geometry = new THREE.ExtrudeGeometry(shape, {
        depth: PRISM_HEIGHT * 0.7,
        bevelEnabled: false,
      });

      const cropId = currentCropOf ? currentCropOf(s.id) : null;
      const cropColorHex = colorOf(cropId);
      const isSelected = s.id === currentSelectedId;

      const topMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(cropColorHex),
        roughness: 0.7,
        metalness: 0.05,
        emissive: isSelected ? new THREE.Color('#FFD27A') : new THREE.Color(0x000000),
        emissiveIntensity: isSelected ? 0.22 : 0,
      });

      const sideMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color('#54402B'),
        roughness: 0.88,
      });

      const mesh = new THREE.Mesh(geometry, [topMat, sideMat]);
      mesh.userData = { sectionId: s.id };
      mesh.rotation.x = -Math.PI / 2;
      mesh.position.set(cx, 0, cz);
      mesh.castShadow = true;
      mesh.receiveShadow = true;

      const group = new THREE.Group();
      group.userData = {
        sectionId: s.id,
        targetY: isSelected ? LIFT_HEIGHT * 0.8 : 0,
      };
      group.position.y = isSelected ? LIFT_HEIGHT * 0.8 : 0;
      group.add(mesh);

      const labelDiv = document.createElement('div');
      labelDiv.className = `farm3d-label ${isSelected ? 'is-selected' : ''}`;
      labelDiv.dataset.action = 'select-section';
      labelDiv.dataset.id = s.id;
      labelDiv.innerHTML = `
        <span class="farm3d-label__badge">${s.id}</span>
        <span class="farm3d-label__crop">${cropId ? nameOf(cropId) : 'non tracée'}</span>
      `;
      labelDiv.addEventListener('click', () => {
        selectSection(s.id, true);
      });

      const labelObj = new CSS2DObject(labelDiv);
      labelObj.position.set(cx, PRISM_HEIGHT * 0.7 + 0.35, cz);
      group.add(labelObj);

      sectionMeshes.set(s.id, {
        group,
        topMat,
        labelDiv,
        edgeLines: null,
      });

      clickableObjects.push(mesh);
      farmGroup.add(group);
    });
  }

  /**
   * Grid layout for sections when none have been traced yet.
   */
  function buildGridSections(allSections) {
    const n = Math.max(1, allSections.length);
    const cols = Math.ceil(Math.sqrt(n));
    const rows = Math.ceil(n / cols);
    const size = 3.6;
    const gap = 0.8;

    const totalW = cols * size + (cols - 1) * gap;
    const totalD = rows * size + (rows - 1) * gap;
    const startX = -totalW / 2 + size / 2;
    const startZ = -totalD / 2 + size / 2;

    allSections.forEach((s, idx) => {
      const col = idx % cols;
      const row = Math.floor(idx / cols);
      const cx = startX + col * (size + gap);
      const cz = startZ + row * (size + gap);

      const pts = [
        new THREE.Vector2(-size / 2, -size / 2),
        new THREE.Vector2(size / 2, -size / 2),
        new THREE.Vector2(size / 2, size / 2),
        new THREE.Vector2(-size / 2, size / 2),
      ];

      const shape = new THREE.Shape();
      shape.moveTo(pts[0].x, pts[0].y);
      for (let j = 1; j < pts.length; j++) shape.lineTo(pts[j].x, pts[j].y);
      shape.closePath();

      const geometry = new THREE.ExtrudeGeometry(shape, {
        depth: PRISM_HEIGHT,
        bevelEnabled: false,
      });

      const cropId = currentCropOf ? currentCropOf(s.id) : null;
      const cropColorHex = colorOf(cropId);
      const isSelected = s.id === currentSelectedId;

      const topMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(cropColorHex),
        roughness: 0.65,
        metalness: 0.05,
        emissive: isSelected ? new THREE.Color('#FFD27A') : new THREE.Color(0x000000),
        emissiveIntensity: isSelected ? 0.22 : 0,
      });

      const sideMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color('#54402B'),
        roughness: 0.85,
      });

      const mesh = new THREE.Mesh(geometry, [topMat, sideMat]);
      mesh.userData = { sectionId: s.id };
      mesh.rotation.x = -Math.PI / 2;
      mesh.position.set(cx, 0, cz);
      mesh.castShadow = true;
      mesh.receiveShadow = true;

      const group = new THREE.Group();
      group.userData = {
        sectionId: s.id,
        targetY: isSelected ? LIFT_HEIGHT : 0,
      };
      group.position.y = isSelected ? LIFT_HEIGHT : 0;
      group.add(mesh);

      const edgesGeo = new THREE.EdgesGeometry(geometry, 28);
      const glowLineMat = new THREE.LineBasicMaterial({
        color: 0xffd27a,
        linewidth: 2,
        transparent: true,
        opacity: isSelected ? 0.95 : 0,
      });
      const edgeLines = new THREE.LineSegments(edgesGeo, glowLineMat);
      edgeLines.rotation.x = -Math.PI / 2;
      edgeLines.position.set(cx, 0, cz);
      group.add(edgeLines);

      const labelDiv = document.createElement('div');
      labelDiv.className = `farm3d-label ${isSelected ? 'is-selected' : ''}`;
      labelDiv.dataset.action = 'select-section';
      labelDiv.dataset.id = s.id;
      labelDiv.innerHTML = `
        <span class="farm3d-label__badge">${s.id}</span>
        <span class="farm3d-label__crop">${cropId ? nameOf(cropId) : '—'}</span>
      `;
      labelDiv.addEventListener('click', () => {
        selectSection(s.id, true);
      });

      const labelObj = new CSS2DObject(labelDiv);
      labelObj.position.set(cx, PRISM_HEIGHT + 0.35, cz);
      group.add(labelObj);

      sectionMeshes.set(s.id, {
        group,
        topMat,
        labelDiv,
        edgeLines,
      });

      sectionGlows.set(s.id, glowLineMat);
      clickableObjects.push(mesh);
      farmGroup.add(group);
    });
  }

  /**
   * Updates selection visuals (lift height, label highlight, glow outline).
   */
  function updateSelectionVisuals() {
    sectionMeshes.forEach((item, id) => {
      const isSelected = id === currentSelectedId;
      item.group.userData.targetY = isSelected ? LIFT_HEIGHT : 0;

      // Update label CSS
      if (item.labelDiv) {
        item.labelDiv.classList.toggle('is-selected', isSelected);
      }

      // Update emissive glow on top material
      if (item.topMat) {
        item.topMat.emissive.set(isSelected ? '#FFD27A' : 0x000000);
        item.topMat.emissiveIntensity = isSelected ? 0.22 : 0;
      }

      // Update footprint visibility
      if (item.footprintMat) {
        item.footprintMat.opacity = isSelected ? 0.45 : 0;
      }

      // Update edge outline glow
      if (item.edgeLines) {
        item.edgeLines.material.opacity = isSelected ? 0.95 : 0;
      }
    });
  }

  /**
   * Section selection handler.
   */
  function selectSection(id, fromLabelClick = false) {
    if (currentSelectedId === id) return;
    currentSelectedId = id;
    updateSelectionVisuals();

    // Dispatch event so parent screens receive standard section change notification
    container.dispatchEvent(
      new CustomEvent('select-section', {
        detail: { id },
        bubbles: true,
        composed: true,
      }),
    );

    // If selected via 3D mesh click, also click the HTML label so app's delegated action handler runs
    if (!fromLabelClick) {
      const label = sectionMeshes.get(id)?.labelDiv;
      if (label) {
        label.click();
      }
    }
  }

  // --- Pointer Click & Hover on 3D Meshes ---
  const raycaster = new THREE.Raycaster();
  const mouse = new THREE.Vector2();
  let pointerDownPos = { x: 0, y: 0 };

  function getMouseCoords(e) {
    const rect = renderer.domElement.getBoundingClientRect();
    return {
      x: ((e.clientX - rect.left) / rect.width) * 2 - 1,
      y: -((e.clientY - rect.top) / rect.height) * 2 + 1,
    };
  }

  function onPointerDown(e) {
    pointerDownPos = { x: e.clientX, y: e.clientY };
  }

  function onPointerUp(e) {
    // Only handle click if mouse didn't drag/orbit
    const dx = e.clientX - pointerDownPos.x;
    const dy = e.clientY - pointerDownPos.y;
    if (Math.hypot(dx, dy) > 5) return;

    const coords = getMouseCoords(e);
    mouse.set(coords.x, coords.y);
    raycaster.setFromCamera(mouse, camera);

    const intersects = raycaster.intersectObjects(clickableObjects, false);
    if (intersects.length > 0) {
      let target = intersects[0].object;
      while (target && !target.userData?.sectionId && target.parent) {
        target = target.parent;
      }
      if (target?.userData?.sectionId) {
        selectSection(target.userData.sectionId);
      }
    }
  }

  function onPointerMove(e) {
    const coords = getMouseCoords(e);
    mouse.set(coords.x, coords.y);
    raycaster.setFromCamera(mouse, camera);

    const intersects = raycaster.intersectObjects(clickableObjects, false);
    renderer.domElement.style.cursor = intersects.length > 0 ? 'pointer' : 'default';
  }

  renderer.domElement.addEventListener('pointerdown', onPointerDown);
  renderer.domElement.addEventListener('pointerup', onPointerUp);
  renderer.domElement.addEventListener('pointermove', onPointerMove);

  // --- Resize Observer ---
  const resizeObserver = new ResizeObserver((entries) => {
    for (const entry of entries) {
      const { width, height } = entry.contentRect;
      if (width > 0 && height > 0) {
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
        renderer.setSize(width, height);
        labelRenderer.setSize(width, height);
      }
    }
  });
  resizeObserver.observe(container);

  // Build initial scene
  buildFarm();

  // --- Animation Loop ---
  let animId = null;
  const clock = new THREE.Clock();

  function animate() {
    animId = requestAnimationFrame(animate);

    clock.getDelta();
    const elapsedTime = clock.getElapsedTime();

    // 1. OrbitControls update
    controls.update();

    // 2. Smooth section elevation lerp
    sectionMeshes.forEach((item) => {
      const targetY = item.group.userData.targetY || 0;
      item.group.position.y += (targetY - item.group.position.y) * 0.15;
    });

    // 3. Subtle pulsing of selected glow outlines
    if (currentSelectedId && sectionGlows.has(currentSelectedId)) {
      const glowMat = sectionGlows.get(currentSelectedId);
      if (glowMat) {
        glowMat.opacity = 0.75 + 0.25 * Math.sin(elapsedTime * 3.5);
      }
    }

    // 4. Atmosphere particles animation (floating dust motes)
    const pos = particleGeo.attributes.position.array;
    for (let i = 0; i < particleCount; i++) {
      const idx = i * 3;
      const seed = particleSeeds[i];

      pos[idx + 1] += 0.003 + Math.sin(elapsedTime * 0.8 + seed) * 0.002;
      pos[idx + 0] += Math.sin(elapsedTime * 0.5 + seed * 2) * 0.0025;
      pos[idx + 2] += Math.cos(elapsedTime * 0.5 + seed * 2) * 0.0025;

      // Wrap back to lower level when drifting too high
      if (pos[idx + 1] > 7.5) {
        pos[idx + 1] = 0.35;
      }
    }
    particleGeo.attributes.position.needsUpdate = true;

    // 5. Render Three.js scene & CSS2D HTML labels
    renderer.render(scene, camera);
    labelRenderer.render(scene, camera);
  }

  animate();

  return {
    /**
     * Updates the 3D farm with new parameters.
     */
    update({ sections: nextSections, cropOf: nextCropOf, selectedId: nextSelectedId, boundary: nextBoundary } = {}) {
      const sectionsChanged = nextSections !== undefined && nextSections !== currentSections;
      const cropOfChanged = nextCropOf !== undefined && nextCropOf !== currentCropOf;
      const boundaryChanged = nextBoundary !== undefined && nextBoundary !== currentBoundary;
      const selectedIdChanged = nextSelectedId !== undefined && nextSelectedId !== currentSelectedId;

      if (sectionsChanged) currentSections = nextSections;
      if (cropOfChanged) currentCropOf = nextCropOf;
      if (boundaryChanged) currentBoundary = nextBoundary;
      if (selectedIdChanged) currentSelectedId = nextSelectedId;

      if (sectionsChanged || cropOfChanged || boundaryChanged) {
        buildFarm();
      } else if (selectedIdChanged) {
        updateSelectionVisuals();
      }
    },

    /**
     * Disposes all geometries, materials, listeners and renderers.
     */
    dispose() {
      if (animId) {
        cancelAnimationFrame(animId);
        animId = null;
      }

      resizeObserver.disconnect();

      renderer.domElement.removeEventListener('pointerdown', onPointerDown);
      renderer.domElement.removeEventListener('pointerup', onPointerUp);
      renderer.domElement.removeEventListener('pointermove', onPointerMove);

      disposeGroup(farmGroup);
      scene.remove(farmGroup);

      // Dispose dust particles
      particleGeo.dispose();
      particleMat.dispose();
      if (dustTexture) dustTexture.dispose();
      scene.remove(particleSystem);

      // Dispose controls & renderers
      controls.dispose();
      renderer.dispose();
      renderer.forceContextLoss();

      if (renderer.domElement?.parentNode) {
        renderer.domElement.parentNode.removeChild(renderer.domElement);
      }
      if (labelRenderer.domElement?.parentNode) {
        labelRenderer.domElement.parentNode.removeChild(labelRenderer.domElement);
      }
    },
  };
}
