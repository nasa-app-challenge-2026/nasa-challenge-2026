/**
 * The 3D farm of the dashboard, for a screen that is redrawn with innerHTML at every change.
 *
 * The scene (farmScene.js, with three.js) is created once and kept; each render puts a
 * `farm3dSlot()` placeholder in the HTML and `showFarm3d()` (called by the screen's `mount`)
 * moves the scene back into it and tells it what changed. Same idea as the Leaflet maps
 * (leafletMap.js).
 *
 * three.js is loaded on demand, the first time the dashboard shows. Until it is there, and on a
 * browser without WebGL, the slot shows the flat view given as `fallback` (isoFarm.js).
 */
import { html } from '../../lib/html.js';

let scene = null;
let loading = null;
/** True once three.js or WebGL failed: the flat view stays, nothing is tried again. */
let unavailable = false;
/** What the scene must show, and who to tell when a section is touched (the last ones given). */
let latest = null;

const currentSlot = () => document.querySelector('[data-farm3d]');

/**
 * The place of the 3D farm in the page. `fallback()` draws the flat view; it is not even
 * computed once the 3D scene is there.
 */
export const farm3dSlot = (fallback) =>
  html`<div class="farm3d__stage" data-farm3d>${scene ? '' : fallback()}</div>`;

function attach() {
  const slot = currentSlot();
  if (!slot || !scene) return;
  if (scene.element.parentNode !== slot) slot.replaceChildren(scene.element);
  scene.update(latest.view);
}

/**
 * Shows the 3D farm in the slot of the page.
 *
 * view      { sections, boundary, crops, selectedId } (see FarmScene.update)
 * onSelect  called with the id of the section touched in the scene
 */
export function showFarm3d(view, onSelect) {
  latest = { view, onSelect };
  if (scene) return attach();
  if (unavailable || loading) return undefined;
  loading = import('./farmScene.js')
    .then(({ FarmScene }) => {
      scene = new FarmScene({
        onSelect: (id) => latest.onSelect(id),
        reducedMotion: matchMedia('(prefers-reduced-motion: reduce)').matches,
      });
      attach();
    })
    .catch((error) => {
      unavailable = true;
      console.warn('[field-shift] vue 3D indisponible, vue à plat gardée :', error);
    })
    .finally(() => {
      loading = null;
    });
  return undefined;
}

/** Frees the scene (the screen is left). */
export function closeFarm3d() {
  scene?.dispose();
  scene = null;
  latest = null;
}
