import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve, sep } from 'node:path';
import { test } from 'node:test';
import { CONFIG, SATELLITE_CROP_MAPPING_VERSION } from '../config.js';
import {
  fetchAafcCanadaBboxTile,
  fetchRegionalCropHistory,
  fetchUsdaCdlBboxTile,
} from '../sources/cropHistory.js';
import { bboxCacheKey, regionCellKey, writeCache } from '../sources/cache.js';
import { computeRegionBbox } from '../sources/nasaModisNdvi.js';

function isolateSources(t, fetchImpl) {
  const tempRoot = resolve(tmpdir());
  const dir = mkdtempSync(join(tempRoot, 'fieldshift-forage-'));
  const previous = { cacheDir: CONFIG.cacheDir, fetch: globalThis.fetch };
  CONFIG.cacheDir = dir;
  globalThis.fetch = fetchImpl;
  t.after(() => {
    CONFIG.cacheDir = previous.cacheDir;
    globalThis.fetch = previous.fetch;
    const target = resolve(dir);
    assert.ok(target.startsWith(tempRoot + sep) && target !== tempRoot);
    rmSync(target, { recursive: true, force: true });
  });
}

// Minimal valid U8 TIFF and NumPy responses keep these source tests independent of the network.
function tiff(pixels) {
  const tags = [
    [256, 4, 4],
    [257, 4, 4],
    [258, 3, 8],
    [259, 3, 1],
    [262, 3, 1],
    [273, 4, 110],
    [277, 3, 1],
    [279, 4, 16],
  ];
  const buf = Buffer.alloc(126);
  buf.write('II');
  buf.writeUInt16LE(42, 2);
  buf.writeUInt32LE(8, 4);
  buf.writeUInt16LE(tags.length, 8);
  tags.forEach(([tag, type, value], i) => {
    const offset = 10 + 12 * i;
    buf.writeUInt16LE(tag, offset);
    buf.writeUInt16LE(type, offset + 2);
    buf.writeUInt32LE(1, offset + 4);
    buf.writeUInt32LE(value, offset + 8);
  });
  Buffer.from(pixels).copy(buf, 110);
  return buf;
}

function npy(pixels) {
  const header = "{'descr': '|u1', 'fortran_order': False, 'shape': (1, 4, 4), }\n";
  const prefix = Buffer.alloc(10);
  prefix[0] = 0x93;
  prefix.write('NUMPY', 1);
  prefix[6] = 1;
  prefix.writeUInt16LE(Buffer.byteLength(header), 8);
  return Buffer.concat([prefix, Buffer.from(header), Buffer.from(pixels)]);
}

const canada = { lat: 45.6, lon: -72.9, gridSize: 4, startYear: 2024, endYear: 2024 };

test('AAFC 122 reste inconnu, tandis que les cultures identifiées sont conservées', async (t) => {
  isolateSources(t, async () => new Response(tiff([122, 147, ...Array(14).fill(122)])));
  const tile = await fetchAafcCanadaBboxTile({
    bbox: computeRegionBbox(canada.lat, canada.lon),
    year: 2024,
    gridSize: 4,
  });
  assert.deepEqual(tile[0], { rawCode: 122, cropId: null });
  assert.deepEqual(tile[1], { rawCode: 147, cropId: 'mais' });
  assert.ok(tile.every((cell) => cell.cropId !== 'luzerne'));
});

test('la vraie luzerne USDA 36 reste reconnue et les autres foins ne le deviennent pas', async (t) => {
  isolateSources(t, async (url) =>
    url === CONFIG.endpoints.planetaryComputerStac
      ? Response.json({ features: [{ id: 'cdl-2024', assets: { cropland: {} } }] })
      : new Response(npy([36, 37, ...Array(14).fill(0)])),
  );
  const tile = await fetchUsdaCdlBboxTile({
    lat: 42,
    lon: -93,
    bbox: computeRegionBbox(42, -93),
    year: 2024,
    gridSize: 4,
  });
  assert.deepEqual(tile[0], { rawCode: 36, cropId: 'luzerne' });
  assert.deepEqual(tile[1], { rawCode: 37, cropId: null });
});

test('tous les anciens caches contenant une luzerne ambiguë sont recalculés, fusion comprise', async (t) => {
  let requests = 0;
  isolateSources(t, async () => {
    requests++;
    return new Response(tiff([...Array(8).fill(122), ...Array(8).fill(147)]));
  });
  const bbox = computeRegionBbox(canada.lat, canada.lon);
  const suffix = `${regionCellKey(canada.lat, canada.lon, 0.05)}_2024_2024_4x4_8km`;
  for (const provider of ['MERGED', 'AAFC_CANADA', 'USDA_CDL']) {
    for (const ending of [suffix, `${suffix}_${bboxCacheKey(bbox)}`]) {
      writeCache('crop-history', `bbox_${provider}_${ending}`, {
        provider,
        gridSize: 4,
        bbox,
        cropIdsByYear: { 2024: Array(16).fill('luzerne') },
      });
    }
  }
  const result = await fetchRegionalCropHistory(canada);
  assert.equal(requests, 1);
  assert.equal(result.fromCache, undefined);
  assert.deepEqual(result.cropIdsByYear[2024], [...Array(8).fill(null), ...Array(8).fill('mais')]);
  assert.deepEqual(result.cropCountsByYear[2024], { mais: 8 });
  assert.equal(result.cropMappingVersion, SATELLITE_CROP_MAPPING_VERSION);
  assert.equal(result.excludedSatelliteClasses[0].rawCode, 122);

  globalThis.fetch = async () => {
    throw new Error('network-disabled');
  };
  const cached = await fetchRegionalCropHistory(canada);
  assert.equal(cached.fromCache, true);
  assert.deepEqual(cached.cropIdsByYear, result.cropIdsByYear);
});

test('une fusion transfrontalière conserve la luzerne USDA et son cache versionné', async (t) => {
  const request = { ...canada, lat: 45, lon: -73 };
  isolateSources(t, async (url) => {
    if (url === CONFIG.endpoints.planetaryComputerStac) {
      return Response.json({ features: [{ id: 'cdl-2024', assets: { cropland: {} } }] });
    }
    if (url.startsWith(CONFIG.endpoints.aafcCropInventoryRest)) {
      return new Response(tiff([...Array(8).fill(147), ...Array(8).fill(0)]));
    }
    return new Response(npy([...Array(8).fill(0), ...Array(8).fill(36)]));
  });
  const result = await fetchRegionalCropHistory(request);
  assert.equal(result.borderStraddling, true);
  assert.equal(result.provider, 'AAFC_CANADA+USDA_CDL');
  assert.deepEqual(result.cropCountsByYear[2024], { mais: 8, luzerne: 8 });

  globalThis.fetch = async () => {
    throw new Error('network-disabled');
  };
  const cached = await fetchRegionalCropHistory(request);
  assert.equal(cached.fromCache, true);
  assert.deepEqual(cached.cropIdsByYear, result.cropIdsByYear);
});
